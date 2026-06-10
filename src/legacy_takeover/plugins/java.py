"""Java/Spring Boot language analyzer plugin — deep code analysis.

Walks the actual package tree under src/main/java (Maven) or src/main/java (Gradle),
groups .java files by package declaration, detects Spring annotations, parses
internal imports for cross-package dependencies, deeply parses JPA @Entity classes,
and runs comprehensive risk checks.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import ClassVar

from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

# Patterns for Spring/JPA annotation detection
_ANNOTATION_RE = re.compile(
    r'@(RestController|Service|Repository|Component|Configuration|'
    r'SpringBootApplication|Controller|RequestMapping|GetMapping|'
    r'PostMapping|PutMapping|DeleteMapping|PatchMapping|Entity|'
    r'Table|Column|Id|GeneratedValue|ManyToOne|OneToMany|OneToOne|'
    r'ManyToMany|JoinColumn|Transactional|Deprecated|Autowired)\b'
)

_REQUEST_MAPPING_RE = re.compile(
    r'@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)'
    r'\s*\((?:[^)]*?(?:value|path)\s*=\s*)?\s*"([^"]*)"'
)

_PACKAGE_RE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
_IMPORT_RE = re.compile(r'^\s*import\s+([\w.*]+)\s*;', re.MULTILINE)
_CLASS_RE = re.compile(r'\bclass\s+(\w+)')

_TABLE_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"(\w+)"')
_COLUMN_RE = re.compile(
    r'@Column\s*\(((?:[^()]*|\([^()]*\))*)\)'
)
_COLUMN_NAME_RE = re.compile(r'name\s*=\s*"(\w+)"')
_COLUMN_NULLABLE_RE = re.compile(r'nullable\s*=\s*(true|false)')
_COLUMN_LENGTH_RE = re.compile(r'length\s*=\s*(\d+)')
_COLUMN_TYPE_RE = re.compile(
    r'(?:private|protected|public)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;'
)

_RELATION_RE = re.compile(
    r'@(ManyToOne|OneToMany|OneToOne|ManyToMany)\s*\((?:[^)]*?mappedBy\s*=\s*"(\w+)")?[^)]*\)'
)
_JOIN_COLUMN_RE = re.compile(r'@JoinColumn\s*\(\s*name\s*=\s*"(\w+)"')

_TODO_RE = re.compile(r'//\s*(TODO|FIXME|HACK)', re.IGNORECASE)
_METHOD_RE = re.compile(
    r'(?:public|private|protected|static|\s)+[\w<>,\s]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
    re.MULTILINE
)

# Find Java source roots
_JAVA_SRC_ROOTS = ("src/main/java", "src/main/kotlin")


# ── Analyzer ───────────────────────────────────────────────────────────────────

class JavaAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "java"
    file_patterns: ClassVar[list[str]] = [
        "*.java", "pom.xml", "build.gradle", "build.gradle.kts",
        "*.yml", "*.yaml", "*.properties",
    ]

    # ── detection ──────────────────────────────────────────────────────────

    def detect(self) -> float:
        score = 0.0
        java_files = list(self.repo_path.rglob("*.java"))
        real_java = [f for f in java_files if "/test/" not in str(f) and "\\test\\" not in str(f)]
        score += min(0.4, len(real_java) * 0.02)
        for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            if (self.repo_path / name).exists():
                score += 0.2
                break
        return min(1.0, score)

    # ── helpers: find all .java files grouped by package ────────────────────

    def _find_java_source_root(self) -> Path | None:
        """Return the first Java source root (src/main/java) found."""
        for root_name in _JAVA_SRC_ROOTS:
            candidate = self.repo_path / root_name
            if candidate.is_dir():
                return candidate
        # Fallback: look for any dir containing .java files under src/
        src = self.repo_path / "src"
        if src.is_dir():
            for d in src.rglob("*.java"):
                p = d.parent
                # Walk up to find the "java" directory
                while p != self.repo_path and p != src:
                    if p.name == "java" and any(
                        f.suffix == ".java" for f in p.rglob("*.java")
                    ):
                        return p
                    p = p.parent
        return None

    def _collect_java_files(self) -> dict[str, list[Path]]:
        """Return {package_name: [Path, ...]} for all non-test .java files."""
        source_root = self._find_java_source_root()
        packages: dict[str, list[Path]] = defaultdict(list)

        if source_root is None:
            # Fallback: scan entire repo for .java files, skip tests
            for f in self.repo_path.rglob("*.java"):
                rp = str(f.relative_to(self.repo_path))
                if "/test/" in rp or "\\test\\" in rp or rp.startswith("test"):
                    continue
                pkg = self._extract_package(f)
                packages[pkg].append(f)
        else:
            for f in source_root.rglob("*.java"):
                pkg = self._extract_package(f)
                packages[pkg].append(f)

        return dict(packages)

    def _extract_package(self, filepath: Path) -> str:
        """Extract the Java package declaration from a file."""
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            m = _PACKAGE_RE.search(text)
            if m:
                return m.group(1)
        except Exception:
            pass
        # Fallback: derive from path relative to source root
        return "<default>"

    def _read_file_safe(self, filepath: Path) -> str | None:
        """Read file content, returning None on failure."""
        try:
            return filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

    # ── structure extraction ────────────────────────────────────────────────

    def extract_structure(self) -> ModuleGraph:
        root = Module(
            name=self.repo_path.name,
            path=str(self.repo_path),
            type=ModuleType.PACKAGE,
        )
        packages = self._collect_java_files()
        modules: list[Module] = []

        is_spring = False
        total_classes = 0
        controller_count = 0
        service_count = 0
        repo_count = 0

        for pkg_name, files in sorted(packages.items()):
            display = pkg_name if pkg_name != "<default>" else "(default package)"
            pkg_path = pkg_name.replace(".", "/") if pkg_name != "<default>" else ""
            loc = 0
            annotations: set[str] = set()
            endpoints: list[dict] = []
            is_entry = False

            child_modules: list[Module] = []
            for fp in files:
                text = self._read_file_safe(fp)
                if text is None:
                    continue
                loc += text.count("\n") + 1
                total_classes += 1

                # Detect Spring annotations
                for ann_match in _ANNOTATION_RE.finditer(text):
                    a = ann_match.group(1)
                    annotations.add(a)
                    if a in ("SpringBootApplication",):
                        is_entry = True
                        is_spring = True
                    elif a in ("RestController", "Controller"):
                        controller_count += 1
                        is_spring = True
                    elif a == "Service":
                        service_count += 1
                        is_spring = True
                    elif a == "Repository":
                        repo_count += 1
                        is_spring = True
                    elif a == "Entity":
                        is_spring = True

                # Detect @RequestMapping / @Get/Put/Post/Delete/PatchMapping
                for rm_match in _REQUEST_MAPPING_RE.finditer(text):
                    endpoints.append({
                        "method": self._guess_http_method(rm_match.group(0)),
                        "path": rm_match.group(1),
                    })

                # Check for main() method
                if re.search(
                    r'public\s+static\s+void\s+main\s*\(\s*String',
                    text,
                ):
                    is_entry = True

                # Add file-level child module
                child_modules.append(Module(
                    name=fp.name,
                    path=str(fp.relative_to(self.repo_path)),
                    type=ModuleType.FILE,
                    parent=display,
                    lines_of_code=loc,
                ))

            # Detect from pom.xml / build.gradle for Spring
            if not is_spring:
                is_spring = self._detect_spring_build()

            pkg_module = Module(
                name=display,
                path=pkg_path,
                type=ModuleType.PACKAGE,
                parent=root.name,
                lines_of_code=loc,
                children=child_modules,
                metadata={
                    "annotations": sorted(annotations),
                    "endpoints": endpoints,
                    "is_entry_point": is_entry,
                    "file_count": len(files),
                },
            )
            modules.append(pkg_module)

        # Summary
        parts = ["Java"]
        if is_spring:
            parts.append("Spring Boot project")
            detail_parts = []
            if controller_count:
                detail_parts.append(f"{controller_count} controllers")
            if service_count:
                detail_parts.append(f"{service_count} services")
            if repo_count:
                detail_parts.append(f"{repo_count} repos")
            if detail_parts:
                parts.append("— " + ", ".join(detail_parts))
        parts.append(f"{len(modules)} packages, {total_classes} classes")
        summary = " ".join(parts)

        return ModuleGraph(
            language="java", root=root, modules=modules, summary=summary,
        )

    def _guess_http_method(self, annotation_text: str) -> str:
        if "GetMapping" in annotation_text:
            return "GET"
        elif "PostMapping" in annotation_text:
            return "POST"
        elif "PutMapping" in annotation_text:
            return "PUT"
        elif "DeleteMapping" in annotation_text:
            return "DELETE"
        elif "PatchMapping" in annotation_text:
            return "PATCH"
        return "REQUEST"

    def _detect_spring_build(self) -> bool:
        """Check build files for Spring Boot dependencies."""
        pom = self.repo_path / "pom.xml"
        if pom.exists():
            try:
                text = pom.read_text(encoding="utf-8", errors="ignore")
                if "spring-boot" in text or "springframework" in text:
                    return True
            except Exception:
                pass
        for gf in ("build.gradle", "build.gradle.kts"):
            gf_path = self.repo_path / gf
            if gf_path.exists():
                try:
                    text = gf_path.read_text(encoding="utf-8", errors="ignore")
                    if "spring-boot" in text or "springframework" in text:
                        return True
                except Exception:
                    pass
        return False

    # ── dependency extraction ───────────────────────────────────────────────

    def extract_dependencies(self) -> DependencyTree:
        packages = self._collect_java_files()
        nodes = list(packages.keys())

        # Build internal import edges
        edges: list[Dependency] = []
        pkg_set = set(packages.keys())

        for pkg_name, files in packages.items():
            for fp in files:
                text = self._read_file_safe(fp)
                if text is None:
                    continue
                for imp_match in _IMPORT_RE.finditer(text):
                    full_import = imp_match.group(1)
                    # Skip java.*, javax.*, etc.
                    if full_import.startswith(("java.", "javax.", "jakarta.")):
                        continue
                    # Find the longest matching package prefix
                    imp_parts = full_import.split(".")
                    for i in range(len(imp_parts), 0, -1):
                        candidate = ".".join(imp_parts[:i])
                        if candidate in pkg_set and candidate != pkg_name:
                            edges.append(Dependency(
                                from_module=pkg_name,
                                to_module=candidate,
                                type=DependencyType.IMPORT,
                                detail=f"{fp.name} imports {full_import}",
                            ))
                            break

        # Deduplicate edges
        seen = set()
        unique_edges: list[Dependency] = []
        for e in edges:
            key = (e.from_module, e.to_module, e.type.value)
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        # External deps from pom.xml / build.gradle
        external = self._extract_external_deps()

        return DependencyTree(
            language="java",
            nodes=nodes,
            edges=unique_edges,
            external_deps=sorted(external),
            summary=f"{len(unique_edges)} internal deps, {len(external)} external deps",
        )

    def _extract_external_deps(self) -> set[str]:
        external: set[str] = set()
        pom = self.repo_path / "pom.xml"
        if pom.exists():
            try:
                tree = ET.parse(pom)
                ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}
                for dep in tree.findall(".//mvn:dependency/mvn:artifactId", ns):
                    if dep.text:
                        external.add(dep.text)
                # Also try without namespace (for simpler POMs)
                if not external:
                    for dep in tree.findall(".//{http://maven.apache.org/POM/4.0.0}dependency/{http://maven.apache.org/POM/4.0.0}artifactId"):
                        if dep.text:
                            external.add(dep.text)
                if not external:
                    for dep in tree.findall(".//dependency/artifactId"):
                        if dep.text:
                            external.add(dep.text)
            except Exception:
                pass

        for gf_name in ("build.gradle", "build.gradle.kts"):
            gf = self.repo_path / gf_name
            if gf.exists():
                try:
                    text = gf.read_text(encoding="utf-8", errors="ignore")
                    for m in re.finditer(
                        r"""['"]([\w.\-]+:[\w.\-]+(?::[\w.\-]+)?)['"]""",
                        text,
                    ):
                        d = m.group(1)
                        parts = d.split(":")
                        if len(parts) >= 2:
                            external.add(parts[1])
                        else:
                            external.add(parts[-1])
                except Exception:
                    pass
        return external

    # ── DB schema extraction ────────────────────────────────────────────────

    def extract_db_schema(self) -> ERDiagram:
        packages = self._collect_java_files()
        tables: list[Table] = []
        orm = "unknown"

        for pkg_name, files in packages.items():
            for fp in files:
                text = self._read_file_safe(fp)
                if text is None:
                    continue
                if "@Entity" not in text and "@Table" not in text:
                    continue

                orm = "jpa/hibernate"

                # Table name
                table_name = fp.stem  # default: class name
                tm = _TABLE_RE.search(text)
                if tm:
                    table_name = tm.group(1)

                # Parse fields
                columns: list[Column] = []
                fk_map: dict[str, str] = {}  # field_name -> referenced_table

                # Find all field blocks — split by annotations
                # Strategy: find lines with @Column, @Id, @ManyToOne, etc.
                lines = text.split("\n")
                i = 0
                current_field_name: str | None = None
                current_column_name: str | None = None
                current_nullable: bool = True
                current_length: int | None = None
                current_type: str = "String"
                is_pk: bool = False
                has_column: bool = False
                has_relation: bool = False
                relation_type: str | None = None
                join_column: str | None = None
                relation_mapped_by: str | None = None

                def flush_field():
                    nonlocal current_field_name, current_column_name, current_nullable
                    nonlocal current_length, current_type, is_pk, has_column, has_relation
                    nonlocal relation_type, join_column, relation_mapped_by

                    if current_field_name is None:
                        return

                    col_name = current_column_name or camel_to_snake(current_field_name)
                    col_type = current_type or "String"

                    fk_ref: str | None = None
                    if has_relation and join_column:
                        fk_ref = ".".join([table_name, join_column])
                    elif has_relation:
                        related_table = camel_to_snake(
                            relation_type.replace("ManyToOne", "").replace("OneToMany", "")
                            .replace("OneToOne", "").replace("ManyToMany", "")
                            or "entity"
                        )
                        fk_ref = related_table

                    columns.append(Column(
                        name=col_name,
                        type=col_type,
                        nullable=current_nullable,
                        primary_key=is_pk,
                        foreign_key=fk_ref,
                    ))

                    # If this is a join column FK, mark it in fk_map
                    if join_column:
                        fk_map[join_column] = col_name

                    # Reset
                    current_field_name = None
                    current_column_name = None
                    current_nullable = True
                    current_length = None
                    current_type = "String"
                    is_pk = False
                    has_column = False
                    has_relation = False
                    relation_type = None
                    join_column = None
                    relation_mapped_by = None

                # Track class-level brace depth so method-body detection works
                class_brace_depth = 0

                for line in lines:
                    stripped = line.strip()

                    # Track class-level opening/closing braces
                    if not stripped.startswith("@") and "{" in stripped:
                        if re.search(r'\bclass\s+\w+', stripped):
                            class_brace_depth = 1

                    # Detect annotations
                    if stripped.startswith("@"):
                        if "@Entity" in stripped or "@Table" in stripped:
                            continue
                        # Flush any pending field before processing new field annotations
                        if current_field_name is not None and not stripped.startswith("@JoinColumn"):
                            flush_field()
                        if "@Id" in stripped:
                            is_pk = True
                            continue
                        if "@GeneratedValue" in stripped:
                            continue
                        if stripped.startswith("@Column"):
                            has_column = True
                            cm = _COLUMN_RE.search(stripped)
                            if cm:
                                col_body = cm.group(1)
                                nm = _COLUMN_NAME_RE.search(col_body)
                                if nm:
                                    current_column_name = nm.group(1)
                                nl = _COLUMN_NULLABLE_RE.search(col_body)
                                if nl:
                                    current_nullable = nl.group(1) == "true"
                                ln = _COLUMN_LENGTH_RE.search(col_body)
                                if ln:
                                    current_length = int(ln.group(1))
                            continue
                        if stripped.startswith("@ManyToOne"):
                            has_relation = True
                            relation_type = "ManyToOne"
                            continue
                        if stripped.startswith("@OneToMany"):
                            has_relation = True
                            relation_type = "OneToMany"
                            rm = _RELATION_RE.search(stripped)
                            if rm and rm.group(2):
                                relation_mapped_by = rm.group(2)
                            continue
                        if stripped.startswith("@OneToOne"):
                            has_relation = True
                            relation_type = "OneToOne"
                            continue
                        if stripped.startswith("@ManyToMany"):
                            has_relation = True
                            relation_type = "ManyToMany"
                            continue
                        if stripped.startswith("@JoinColumn"):
                            jcm = _JOIN_COLUMN_RE.search(stripped)
                            if jcm:
                                join_column = jcm.group(1)
                            continue
                        # Other annotations — skip
                        continue

                    # Field declaration line
                    field_match = _COLUMN_TYPE_RE.search(stripped)
                    if field_match:
                        # Flush previous field if any
                        if current_field_name is not None:
                            flush_field()
                        current_type = field_match.group(1)
                        current_field_name = field_match.group(2)
                        # If we saw annotations but no explicit column name
                        continue

                    # End of class or next annotation block
                    if "}" in stripped and current_field_name is not None:
                        flush_field()

                # Flush last field
                flush_field()

                # Always add an id column if none parsed (fallback)
                if not any(c.primary_key for c in columns):
                    columns.insert(0, Column(
                        name="id", type="Long", primary_key=True,
                    ))

                tables.append(Table(
                    name=table_name,
                    columns=columns,
                    description=f"JPA entity: {fp.stem}",
                ))

        return ERDiagram(
            language="java",
            tables=tables,
            orm_framework=orm,
            summary=f"{len(tables)} tables ({orm})",
        )

    # ── risk assessment ─────────────────────────────────────────────────────

    def assess_risks(self) -> list[Risk]:
        risks: list[Risk] = []
        rid = 0
        packages = self._collect_java_files()
        all_files = [fp for flist in packages.values() for fp in flist]

        for fp in all_files:
            text = self._read_file_safe(fp)
            if text is None:
                continue
            rp = str(fp.relative_to(self.repo_path))
            lines = text.split("\n")

            # 1. Thread.sleep() — performance risk
            if "Thread.sleep" in text:
                rid += 1
                ln = text[:text.index("Thread.sleep")].count("\n") + 1
                risks.append(Risk(
                    id=f"JV-PERF-{rid:03d}",
                    category=RiskCategory.PERFORMANCE,
                    severity=RiskSeverity.MEDIUM,
                    confidence=0.7,
                    title="Thread.sleep() detected",
                    description=f"Synchronous sleep in {rp}",
                    file=rp, line=ln,
                    evidence="Thread.sleep",
                    recommendation="Use asynchronous alternatives (CompletableFuture, reactive streams).",
                ))

            # 2. TODO/FIXME/HACK density
            todos = len(_TODO_RE.findall(text))
            if todos >= 5:
                rid += 1
                risks.append(Risk(
                    id=f"JV-DEBT-{rid:03d}",
                    category=RiskCategory.TECH_DEBT,
                    severity=RiskSeverity.MEDIUM,
                    confidence=0.8,
                    title=f"High TODO density ({todos})",
                    description=f"{rp} has {todos} TODO/FIXME/HACK markers",
                    file=rp, line=1,
                    evidence=f"{todos} markers found",
                    recommendation="Address accumulated tech debt.",
                ))

            # 3. @Deprecated usage
            if "@Deprecated" in text:
                rid += 1
                idx = text.index("@Deprecated")
                ln = text[:idx].count("\n") + 1
                risks.append(Risk(
                    id=f"JV-DEBT-{rid:03d}",
                    category=RiskCategory.TECH_DEBT,
                    severity=RiskSeverity.LOW,
                    confidence=0.9,
                    title="Deprecated code detected",
                    description=f"@Deprecated usage in {rp}",
                    file=rp, line=ln,
                    evidence="@Deprecated",
                    recommendation="Migrate to the recommended replacement API.",
                ))

            # 4. God class (>500 lines)
            if len(lines) > 500:
                rid += 1
                risks.append(Risk(
                    id=f"JV-DEBT-{rid:03d}",
                    category=RiskCategory.TECH_DEBT,
                    severity=RiskSeverity.MEDIUM,
                    confidence=0.9,
                    title=f"God class ({len(lines)} lines)",
                    description=f"{rp} has {len(lines)} lines — exceeds 500-line threshold",
                    file=rp, line=1,
                    evidence=f"File is {len(lines)} lines",
                    recommendation="Refactor into smaller, focused classes.",
                ))

            # 5. Long methods (>50 lines)
            long_methods = self._find_long_methods(text, lines)
            for m_name, m_start, m_len in long_methods:
                if m_len > 50:
                    rid += 1
                    risks.append(Risk(
                        id=f"JV-DEBT-{rid:03d}",
                        category=RiskCategory.TECH_DEBT,
                        severity=RiskSeverity.LOW,
                        confidence=0.8,
                        title=f"Long method {m_name}() ({m_len} lines)",
                        description=f"Method {m_name}() in {rp} has {m_len} lines — exceeds 50-line threshold",
                        file=rp, line=m_start,
                        evidence=f"Method body: {m_len} lines",
                        recommendation=f"Extract sub-methods from {m_name}().",
                    ))

        # 6. Classes without tests (check once per package)
        test_root = None
        for candidate in (
            self.repo_path / "src" / "test" / "java",
            self.repo_path / "src" / "test",
        ):
            if candidate.is_dir():
                test_root = candidate
                break

        if test_root:
            test_files = {f.stem for f in test_root.rglob("*.java")}
            for fp in all_files:
                rp = str(fp.relative_to(self.repo_path))
                # Check if a corresponding test file exists (FooTest, TestFoo, FooTests)
                stem = fp.stem
                has_test = any(
                    t in test_files
                    for t in (f"{stem}Test", f"Test{stem}", f"{stem}Tests")
                )
                if not has_test:
                    rid += 1
                    risks.append(Risk(
                        id=f"JV-BUS-{rid:03d}",
                        category=RiskCategory.BUS_FACTOR,
                        severity=RiskSeverity.LOW,
                        confidence=0.7,
                        title=f"No test coverage for {fp.stem}",
                        description=f"{rp} has no corresponding test class",
                        file=rp, line=1,
                        evidence="No matching *Test.java found",
                        recommendation=f"Add unit tests for {fp.stem}.",
                    ))

        # 7. Missing @Transactional on service methods calling repos
        service_files_with_tx: set[str] = set()
        service_files_without_tx: set[str] = set()
        for fp in all_files:
            text = self._read_file_safe(fp)
            if text is None:
                continue
            rp = str(fp.relative_to(self.repo_path))
            is_service = "@Service" in text
            is_repo = "@Repository" in text
            has_transactional = "@Transactional" in text

            if is_service:
                if has_transactional:
                    service_files_with_tx.add(rp)
                else:
                    # Check if this service has methods that might need @Transactional
                    # Heuristic: if it imports or references repository types
                    imports_repo = bool(re.search(
                        r'import\s+[\w.]*[Rr]epository', text
                    ))
                    uses_repo = bool(re.search(
                        r'(?:private|protected|public)\s+\w*[Rr]epository\s+\w+', text
                    ))
                    if imports_repo or uses_repo:
                        service_files_without_tx.add(rp)

        for rp in service_files_without_tx:
            rid += 1
            risks.append(Risk(
                id=f"JV-SEC-{rid:03d}",
                category=RiskCategory.TECH_DEBT,
                severity=RiskSeverity.MEDIUM,
                confidence=0.6,
                title="Service missing @Transactional",
                description=f"{rp} is a @Service that uses repositories but lacks @Transactional",
                file=rp, line=1,
                evidence="Uses repository without @Transactional",
                recommendation="Add @Transactional to service methods or class.",
            ))

        # 8. Hardcoded database passwords in config files
        for config_pattern in ("*.yml", "*.yaml", "*.properties"):
            for cf in self.repo_path.rglob(config_pattern):
                if "/test/" in str(cf) or "\\test\\" in str(cf):
                    continue
                try:
                    ct = cf.read_text(encoding="utf-8", errors="ignore")
                    cfp = str(cf.relative_to(self.repo_path))
                    # Look for password/db-password/spring.datasource.password patterns
                    pwd_matches = list(re.finditer(
                        r'(?:password|passwd|pwd|secret)[\s:=]+["\']?([^\s"\']{3,})["\']?',
                        ct,
                        re.IGNORECASE,
                    ))
                    for pm in pwd_matches:
                        val = pm.group(1)
                        # Skip placeholder values
                        if val in ("${", "{{", "ENC(", "changeme", "password", "secret"):
                            continue
                        # Check it's not a reference
                        if val.startswith(("$", "{")):
                            continue
                        rid += 1
                        ln = ct[:pm.start()].count("\n") + 1
                        risks.append(Risk(
                            id=f"JV-SEC-{rid:03d}",
                            category=RiskCategory.SECURITY,
                            severity=RiskSeverity.HIGH,
                            confidence=0.85,
                            title="Hardcoded password in config",
                            description=f"Potential hardcoded credential in {cfp}",
                            file=cfp, line=ln,
                            evidence=pm.group(0)[:80],
                            recommendation="Use environment variables or a secrets manager.",
                        ))
                except Exception:
                    pass

        return risks

    def _find_long_methods(
        self, text: str, lines: list[str],
    ) -> list[tuple[str, int, int]]:
        """Find methods longer than 50 lines. Returns [(method_name, start_line, length)]."""
        result: list[tuple[str, int, int]] = []
        brace_depth = 0
        in_method = False
        method_name = ""
        method_start = 0
        method_body_start = 0
        method_entry_depth = 0  # brace depth when method was entered

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue

            # Track ALL brace changes including class/interface/enum
            opens = stripped.count("{")
            closes = stripped.count("}")
            if closes:
                brace_depth -= closes
                if in_method and brace_depth <= method_entry_depth:
                    # Method ends
                    length = i - method_body_start + 1
                    if length > 50:
                        result.append((method_name, method_start, length))
                    in_method = False
            if opens:
                brace_depth += opens

            if not in_method:
                # Look for method declaration (must have opening brace on this line)
                mm = _METHOD_RE.search(stripped)
                if mm and not stripped.startswith("@"):
                    # Check this is a real method (not a class declaration)
                    method_name_candidate = mm.group(1)
                    if method_name_candidate[0].islower() or stripped.startswith(
                        ("public ", "private ", "protected ")
                    ):
                        in_method = True
                        method_name = method_name_candidate
                        method_start = i + 1
                        method_body_start = i + 1
                        method_entry_depth = brace_depth - 1  # inside method body

        return result


# ── Utilities ──────────────────────────────────────────────────────────────────


def camel_to_snake(name: str) -> str:
    """Convert camelCase/PascalCase to snake_case."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s1)
    return s2.lower()
