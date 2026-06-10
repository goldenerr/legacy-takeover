"""Tests for Java analyzer plugin — deep analysis edition."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.java import JavaAnalyzer


class TestJavaAnalyzer:
    # ── detection ───────────────────────────────────────────────────────────

    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = JavaAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_java_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Main.java").write_text("public class Main {}")
            a = JavaAnalyzer(repo_path=repo)
            score = a.detect()
            assert score > 0.0
            assert score <= 1.0

    def test_detect_with_pom_xml(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text("<project></project>")
            a = JavaAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.2

    # ── structure: package-level modules ────────────────────────────────────

    def test_extract_structure_packages_from_java_declaration(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example" / "controller"
            src.mkdir(parents=True)
            (src / "HelloController.java").write_text(
                "package com.example.controller;\n"
                "import org.springframework.web.bind.annotation.*;\n"
                "@RestController\n"
                "public class HelloController {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "java"
            assert any("com.example.controller" in m.name for m in graph.modules), (
                f"Expected com.example.controller in modules: {[m.name for m in graph.modules]}"
            )

    def test_extract_structure_spring_annotation_detection(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "controller").mkdir()
            (src / "service").mkdir()
            (src / "repository").mkdir()

            (src / "controller" / "UserController.java").write_text(
                "package com.example.controller;\n"
                "@RestController\n"
                "public class UserController {}\n"
            )
            (src / "service" / "UserService.java").write_text(
                "package com.example.service;\n"
                "@Service\n"
                "public class UserService {}\n"
            )
            (src / "repository" / "UserRepository.java").write_text(
                "package com.example.repository;\n"
                "@Repository\n"
                "public class UserRepository {}\n"
            )

            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()

            # Find controller module
            ctrl = next(
                (m for m in graph.modules if "controller" in m.name), None
            )
            assert ctrl is not None, f"No controller module: {[m.name for m in graph.modules]}"
            assert "RestController" in ctrl.metadata.get("annotations", [])

            svc = next(
                (m for m in graph.modules if "service" in m.name), None
            )
            assert svc is not None
            assert "Service" in svc.metadata.get("annotations", [])

            repo_mod = next(
                (m for m in graph.modules if "repository" in m.name), None
            )
            assert repo_mod is not None
            assert "Repository" in repo_mod.metadata.get("annotations", [])

            assert "Spring Boot" in graph.summary or "controllers" in graph.summary.lower()

    def test_extract_structure_rest_endpoints(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "ApiController.java").write_text(
                "package com.example;\n"
                "@RestController\n"
                "public class ApiController {\n"
                '  @GetMapping("/users")\n'
                "  public List<User> list() { return null; }\n"
                '  @PostMapping("/users")\n'
                "  public User create() { return null; }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()

            pkg_mod = graph.modules[0]
            endpoints = pkg_mod.metadata.get("endpoints", [])
            assert len(endpoints) >= 2, f"Expected >=2 endpoints, got {endpoints}"
            paths = [e["path"] for e in endpoints]
            assert "/users" in paths

    def test_extract_structure_entry_point_detection(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "Application.java").write_text(
                "package com.example;\n"
                "@SpringBootApplication\n"
                "public class Application {\n"
                "  public static void main(String[] args) {\n"
                "    SpringApplication.run(Application.class, args);\n"
                "  }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            pkg_mod = graph.modules[0]
            assert pkg_mod.metadata.get("is_entry_point") is True

    # ── dependencies: internal imports ──────────────────────────────────────

    def test_extract_dependencies_internal_imports(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            ctrl_dir = src / "controller"
            svc_dir = src / "service"
            ctrl_dir.mkdir(parents=True)
            svc_dir.mkdir(parents=True)

            (svc_dir / "UserService.java").write_text(
                "package com.example.service;\n"
                "public class UserService {}\n"
            )
            (ctrl_dir / "UserController.java").write_text(
                "package com.example.controller;\n"
                "import com.example.service.UserService;\n"
                "public class UserController {\n"
                "  private UserService userService;\n"
                "}\n"
            )

            a = JavaAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()

            # Should have an edge from controller → service
            edges = tree.edges
            assert len(edges) >= 1, f"Expected >=1 internal edge, got {len(edges)}"
            dep = edges[0]
            assert dep.from_module == "com.example.controller", f"from={dep.from_module}"
            assert dep.to_module == "com.example.service", f"to={dep.to_module}"
            assert dep.type.value == "import"

    def test_extract_dependencies_from_pom(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies>"
                "<dependency><artifactId>spring-boot-starter</artifactId></dependency>"
                "<dependency><artifactId>lombok</artifactId></dependency>"
                "</dependencies></project>"
            )
            a = JavaAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_extract_dependencies_ignores_java_imports(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "MyClass.java").write_text(
                "package com.example;\n"
                "import java.util.List;\n"
                "import javax.persistence.Entity;\n"
                "public class MyClass {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            # No internal edges since java.* and javax.* are skipped
            assert len(tree.edges) == 0

    # ── DB schema: full JPA entity parsing ──────────────────────────────────

    def test_extract_db_schema_detects_entity_table_name(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "User.java").write_text(
                "package com.example;\n"
                "import javax.persistence.*;\n"
                "@Entity\n"
                '@Table(name = "users")\n'
                "public class User {\n"
                "  @Id\n"
                "  @GeneratedValue\n"
                "  private Long id;\n"
                '  @Column(name = "email", nullable = false, length = 100)\n'
                "  private String email;\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            diagram = a.extract_db_schema()
            assert len(diagram.tables) >= 1
            assert diagram.orm_framework == "jpa/hibernate"

            table = diagram.tables[0]
            assert table.name == "users"
            assert len(table.columns) >= 2  # id + email
            col_names = [c.name for c in table.columns]
            assert "id" in col_names
            assert "email" in col_names

            email_col = next((c for c in table.columns if c.name == "email"), None)
            assert email_col is not None
            assert email_col.nullable is False

    def test_extract_db_schema_foreign_keys(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "Order.java").write_text(
                "package com.example;\n"
                "import javax.persistence.*;\n"
                "@Entity\n"
                '@Table(name = "orders")\n'
                "public class Order {\n"
                "  @Id @GeneratedValue\n"
                "  private Long id;\n"
                "  @ManyToOne\n"
                '  @JoinColumn(name = "user_id")\n'
                "  private User user;\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            diagram = a.extract_db_schema()
            assert len(diagram.tables) >= 1
            table = diagram.tables[0]
            assert table.name == "orders"

            user_fk = next(
                (c for c in table.columns if c.foreign_key is not None), None
            )
            assert user_fk is not None, f"No FK found in columns: {[(c.name, c.foreign_key) for c in table.columns]}"

    def test_extract_db_schema_no_entities_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "Utils.java").write_text(
                "package com.example;\npublic class Utils {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            diagram = a.extract_db_schema()
            assert len(diagram.tables) == 0

    # ── risks: comprehensive checks ─────────────────────────────────────────

    def test_assess_risks_detects_thread_sleep(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Worker.java").write_text(
                "class Worker { void run() { Thread.sleep(1000); } }"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("Thread.sleep" in r.title for r in risks)

    def test_assess_risks_detects_deprecated(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "OldCode.java").write_text(
                "@Deprecated\n"
                "public class OldCode {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("Deprecated" in r.title for r in risks), (
                f"Expected Deprecated risk, got: {[r.title for r in risks]}"
            )

    def test_assess_risks_detects_god_class(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            lines = ["public class BigClass {"]
            for i in range(510):
                lines.append(f"  int field{i};")
            lines.append("}")
            (repo / "BigClass.java").write_text("\n".join(lines))
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("God class" in r.title for r in risks), (
                f"Expected God class risk, got: {[r.title for r in risks]}"
            )

    def test_assess_risks_detects_hardcoded_password_in_config(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "application.properties").write_text(
                "spring.datasource.password=MySecret123\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(
                "Hardcoded password" in r.title for r in risks
            ), f"Expected password risk, got: {[r.title for r in risks]}"

    def test_assess_risks_detects_missing_tests(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            test_dir = repo / "src" / "test" / "java" / "com" / "example"
            src.mkdir(parents=True)
            test_dir.mkdir(parents=True)

            (src / "UserService.java").write_text(
                "package com.example;\n"
                "@org.springframework.stereotype.Service\n"
                "public class UserService {}\n"
            )
            # No UserServiceTest.java in test dir
            (test_dir / "SomeOtherTest.java").write_text(
                "package com.example;\npublic class SomeOtherTest {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(
                "No test coverage" in r.title for r in risks
            ), f"Expected missing test risk, got: {[r.title for r in risks]}"

    def test_assess_risks_detects_long_method(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            lines = [
                "public class Processor {",
                "  public void process() {",
            ]
            for i in range(60):
                lines.append(f"    int x{i} = {i};")
            lines.append("  }")
            lines.append("}")
            (repo / "Processor.java").write_text("\n".join(lines))
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(
                "Long method" in r.title for r in risks
            ), f"Expected Long method risk, got: {[r.title for r in risks]}"

    def test_assess_risks_missing_transactional(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "UserService.java").write_text(
                "package com.example;\n"
                "import org.springframework.stereotype.Service;\n"
                "import com.example.UserRepository;\n"
                "@Service\n"
                "public class UserService {\n"
                "  private UserRepository userRepository;\n"
                "  public void saveUser() { userRepository.save(null); }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            tx_risk = any(
                "missing @transactional" in r.title.lower()
                for r in risks
            )
            assert tx_risk, f"Expected missing @Transactional risk, got: {[r.title for r in risks]}"

    def test_skip_test_files(self):
        """Verify that files under src/test/ are not analyzed."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src_main = repo / "src" / "main" / "java" / "com" / "example"
            src_test = repo / "src" / "test" / "java" / "com" / "example"
            src_main.mkdir(parents=True)
            src_test.mkdir(parents=True)

            (src_main / "Service.java").write_text(
                "package com.example;\n"
                "@org.springframework.stereotype.Service\n"
                "public class Service {}\n"
            )
            (src_test / "ServiceTest.java").write_text(
                "package com.example;\n"
                "public class ServiceTest {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            # Only the main package should appear
            packages = [m.name for m in graph.modules]
            assert "com.example" in packages
            # Test files should not create their own module
            assert not any("test" in p.lower() and p != "com.example" for p in packages)

    def test_gradle_project_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (repo / "build.gradle").write_text(
                "dependencies {\n"
                "  implementation 'org.springframework.boot:spring-boot-starter:3.0.0'\n"
                "}\n"
            )
            (src / "App.java").write_text(
                "package com.example;\n"
                "public class App {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 1
            # spring-boot-starter should be detected
            assert any("spring-boot-starter" in d for d in tree.external_deps)

    # ── P1-1: Enhanced REST API extraction ──────────────────────────────────

    def test_rest_endpoints_full_extraction(self):
        """Extract method_name, return_type, params, path_vars from @RestController."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "UserController.java").write_text(
                "package com.example;\n"
                "import org.springframework.web.bind.annotation.*;\n"
                "@RestController\n"
                'public class UserController {\n'
                '  @GetMapping("/users/{id}")\n'
                "  public User getUser(@PathVariable Long id, @RequestParam String name) {\n"
                "    return null;\n"
                "  }\n"
                '  @PostMapping("/users")\n'
                "  public User createUser(@RequestBody User user) {\n"
                "    return null;\n"
                "  }\n"
                '  @DeleteMapping("/users/{id}")\n'
                '  public void deleteUser(@PathVariable("id") Long userId) {\n'
                "  }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()

            pkg_mod = graph.modules[0]
            endpoints = pkg_mod.metadata.get("endpoints", [])
            assert len(endpoints) == 3, f"Expected 3 endpoints, got {len(endpoints)}"

            # Check first endpoint (GET /users/{id})
            get_ep = next((e for e in endpoints if e["method"] == "GET"), None)
            assert get_ep is not None
            assert get_ep["path"] == "/users/{id}"
            assert get_ep["method_name"] == "getUser"
            assert get_ep["return_type"] == "User"
            assert "name" in get_ep["params"]
            assert "id" in get_ep["path_vars"]

            # Check POST /users
            post_ep = next((e for e in endpoints if e["method"] == "POST"), None)
            assert post_ep is not None
            assert post_ep["path"] == "/users"
            assert post_ep["method_name"] == "createUser"

    def test_rest_endpoints_requestmapping_with_method(self):
        """Extract @RequestMapping with explicit method= attribute."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "LegacyController.java").write_text(
                "package com.example;\n"
                "import org.springframework.web.bind.annotation.*;\n"
                "@RestController\n"
                'public class LegacyController {\n'
                '  @RequestMapping(value = "/legacy", method = RequestMethod.PUT)\n'
                "  public String handleLegacy() {\n"
                '    return "ok";\n'
                "  }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()

            pkg_mod = graph.modules[0]
            endpoints = pkg_mod.metadata.get("endpoints", [])
            assert len(endpoints) == 1
            assert endpoints[0]["method"] == "PUT"
            assert endpoints[0]["path"] == "/legacy"

    # ── P1-3: Module role inference ─────────────────────────────────────────

    def test_module_role_inference_controller(self):
        """Controller package gets REST_API_LAYER role."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example" / "controller"
            src.mkdir(parents=True)
            (src / "UserController.java").write_text(
                "package com.example.controller;\n"
                "@RestController\n"
                "public class UserController {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            pkg_mod = graph.modules[0]
            assert pkg_mod.metadata.get("role") == "REST_API_LAYER"

    def test_module_role_inference_service(self):
        """Service package gets BUSINESS_LOGIC role."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example" / "service"
            src.mkdir(parents=True)
            (src / "UserService.java").write_text(
                "package com.example.service;\n"
                "@Service\n"
                "public class UserService {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            pkg_mod = graph.modules[0]
            assert pkg_mod.metadata.get("role") == "BUSINESS_LOGIC"

    def test_module_role_inference_repository(self):
        """Repository/dao/mapper package gets DATA_ACCESS role."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example" / "dao"
            src.mkdir(parents=True)
            (src / "UserDao.java").write_text(
                "package com.example.dao;\n"
                "public class UserDao {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            pkg_mod = graph.modules[0]
            assert pkg_mod.metadata.get("role") == "DATA_ACCESS"

    def test_module_role_unknown(self):
        """Unknown package gets UNKNOWN role."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example" / "mystuff"
            src.mkdir(parents=True)
            (src / "Foo.java").write_text(
                "package com.example.mystuff;\n"
                "public class Foo {}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            pkg_mod = graph.modules[0]
            assert pkg_mod.metadata.get("role") == "UNKNOWN"

    # ── P1-4: Layer violation checks ────────────────────────────────────────

    def test_layer_violation_controller_direct_repo(self):
        """Controller directly importing Repository should trigger layer violation."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java"
            ctrl_dir = src / "com" / "example" / "controller"
            repo_dir = src / "com" / "example" / "repository"
            ctrl_dir.mkdir(parents=True)
            repo_dir.mkdir(parents=True)

            (repo_dir / "UserRepository.java").write_text(
                "package com.example.repository;\n"
                "public class UserRepository {}\n"
            )
            (ctrl_dir / "UserController.java").write_text(
                "package com.example.controller;\n"
                "import com.example.repository.UserRepository;\n"
                "@org.springframework.web.bind.annotation.RestController\n"
                "public class UserController {\n"
                "  private UserRepository repo;\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            layer_risks = [
                r for r in risks
                if "Controller directly accesses" in r.title
            ]
            assert len(layer_risks) >= 1, (
                f"Expected layer violation risk, got: {[r.title for r in risks]}"
            )

    # ── P1-5: Circular dependency detection ─────────────────────────────────

    def test_circular_dependency_detection(self):
        """Two modules importing each other should trigger circular dep risk."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java"
            mod_a = src / "com" / "example" / "a"
            mod_b = src / "com" / "example" / "b"
            mod_a.mkdir(parents=True)
            mod_b.mkdir(parents=True)

            (mod_a / "A.java").write_text(
                "package com.example.a;\n"
                "import com.example.b.B;\n"
                "public class A { B b; }\n"
            )
            (mod_b / "B.java").write_text(
                "package com.example.b;\n"
                "import com.example.a.A;\n"
                "public class B { A a; }\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            cycle_risks = [
                r for r in risks
                if "Circular dependency" in r.title
            ]
            assert len(cycle_risks) >= 1, (
                f"Expected circular dependency risk, got: {[r.title for r in risks]}"
            )

    def test_no_circular_dependency_false_positive(self):
        """Acyclic modules should not trigger circular dep risk."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java"
            mod_a = src / "com" / "example" / "a"
            mod_b = src / "com" / "example" / "b"
            mod_a.mkdir(parents=True)
            mod_b.mkdir(parents=True)

            (mod_a / "A.java").write_text(
                "package com.example.a;\n"
                "public class A {}\n"
            )
            (mod_b / "B.java").write_text(
                "package com.example.b;\n"
                "import com.example.a.A;\n"
                "public class B { A a; }\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            cycle_risks = [
                r for r in risks
                if "Circular dependency" in r.title
            ]
            assert len(cycle_risks) == 0, (
                f"Expected no circular dep, got: {[r.title for r in risks]}"
            )

    # ── P1-6: DB config extraction ──────────────────────────────────────────

    def test_db_config_from_application_yml(self):
        """Extract DB type, hosts, databases, pool from application.yml."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "application.yml").write_text(
                "spring:\n"
                "  datasource:\n"
                "    url: jdbc:mysql://db.example.com:3306/mydb\n"
                "    hikari:\n"
                "      minimum-idle: 5\n"
                "      maximum-pool-size: 20\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            config = a._extract_db_config()
            assert config["type"] == "MYSQL"
            assert "db.example.com:3306" in config["hosts"]
            assert "mydb" in config["databases"]
            assert config["pool"].get("min_idle") == 5
            assert config["pool"].get("max_size") == 20

    def test_db_config_flyway_detection(self):
        """Detect Flyway migration when db/migration directory exists."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            migration_dir = repo / "src" / "main" / "resources" / "db" / "migration"
            migration_dir.mkdir(parents=True)
            (migration_dir / "V1__init.sql").write_text("-- init")
            a = JavaAnalyzer(repo_path=repo)
            config = a._extract_db_config()
            assert config.get("migration") == "Flyway"

    def test_db_config_liquibase_detection(self):
        """Detect Liquibase when changelog XML files exist."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "db").mkdir()
            (repo / "db" / "changelog-master.xml").write_text(
                '<databaseChangeLog></databaseChangeLog>'
            )
            a = JavaAnalyzer(repo_path=repo)
            config = a._extract_db_config()
            assert config.get("migration") == "Liquibase"

    # ── P1-7: Cache analysis ────────────────────────────────────────────────

    def test_cache_redis_detection(self):
        """Detect Redis cache from pom.xml dependency."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                "<project>"
                "<dependencies>"
                "<dependency><artifactId>spring-boot-starter-data-redis</artifactId></dependency>"
                "</dependencies>"
                "</project>"
            )
            a = JavaAnalyzer(repo_path=repo)
            cache = a._extract_cache_info()
            assert cache["type"] == "Redis"

    def test_cacheable_annotation_extraction(self):
        """Extract @Cacheable annotations from Java files."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (repo / "pom.xml").write_text(
                "<project>"
                "<dependencies>"
                "<dependency><artifactId>spring-boot-starter-data-redis</artifactId></dependency>"
                "</dependencies>"
                "</project>"
            )
            (src / "UserService.java").write_text(
                "package com.example;\n"
                "import org.springframework.cache.annotation.Cacheable;\n"
                "@Service\n"
                "public class UserService {\n"
                '  @Cacheable(value = "users", key = "#id")\n'
                "  public User getUser(Long id) { return null; }\n"
                '  @Cacheable("products")\n'
                "  public Product getProduct(Long id) { return null; }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            cache = a._extract_cache_info()
            assert cache["type"] == "Redis"
            assert len(cache["entries"]) >= 2

            user_entry = next(
                (e for e in cache["entries"] if e["name"] == "users"), None
            )
            assert user_entry is not None
            assert user_entry["key"] == "#id"
            assert "UserService.java" in user_entry["file"]

    # ── P1-8: MQ analysis ───────────────────────────────────────────────────

    def test_mq_kafka_detection(self):
        """Detect Kafka from pom.xml dependency."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                "<project>"
                "<dependencies>"
                "<dependency><artifactId>spring-kafka</artifactId></dependency>"
                "</dependencies>"
                "</project>"
            )
            a = JavaAnalyzer(repo_path=repo)
            mq = a._extract_mq_info()
            assert mq["type"] == "Kafka"

    def test_mq_kafka_listener_extraction(self):
        """Extract @KafkaListener topics and groups."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (repo / "pom.xml").write_text(
                "<project>"
                "<dependencies>"
                "<dependency><artifactId>spring-kafka</artifactId></dependency>"
                "</dependencies>"
                "</project>"
            )
            (src / "OrderConsumer.java").write_text(
                "package com.example;\n"
                "import org.springframework.kafka.annotation.KafkaListener;\n"
                "@Service\n"
                "public class OrderConsumer {\n"
                '  @KafkaListener(topics = "orders", groupId = "order-group")\n'
                "  public void handle(String msg) {}\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            mq = a._extract_mq_info()
            assert mq["type"] == "Kafka"
            assert len(mq["topics"]) >= 1

            order_topic = next(
                (t for t in mq["topics"] if t["name"] == "orders"), None
            )
            assert order_topic is not None
            assert order_topic["type"] == "consumer"
            assert order_topic["group"] == "order-group"

    def test_mq_kafka_producer_extraction(self):
        """Detect KafkaTemplate.send() producers."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (repo / "pom.xml").write_text(
                "<project>"
                "<dependencies>"
                "<dependency><artifactId>spring-kafka</artifactId></dependency>"
                "</dependencies>"
                "</project>"
            )
            (src / "OrderService.java").write_text(
                "package com.example;\n"
                "@Service\n"
                "public class OrderService {\n"
                "  public void send() {\n"
                '    kafkaTemplate.send("orders", msg);\n'
                "  }\n"
                "}\n"
            )
            a = JavaAnalyzer(repo_path=repo)
            mq = a._extract_mq_info()
            assert len(mq["topics"]) >= 1

            producer = next(
                (t for t in mq["topics"] if t["type"] == "producer"), None
            )
            assert producer is not None
            assert producer["name"] == "orders"
