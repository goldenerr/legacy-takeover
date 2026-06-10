"""Tests for test_analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.test_analyzer import analyze_tests, find_untested_critical
from legacy_takeover.plugins.base import RiskSeverity


class TestAnalyzeTests:
    def test_no_src_or_test_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            result = analyze_tests(Path(d))
            assert result["total_src"] == 0
            assert result["total_tests"] == 0
            assert result["ratio"] == 0.0

    def test_src_without_tests(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            src.mkdir(parents=True)
            (src / "Service.java").write_text("public class Service {}")
            result = analyze_tests(repo)
            assert result["total_src"] >= 1
            assert result["total_tests"] == 0
            assert len(result["uncovered"]) >= 1

    def test_src_with_matching_tests(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            src = repo / "src" / "main" / "java" / "com" / "example"
            test_dir = repo / "src" / "test" / "java" / "com" / "example"
            src.mkdir(parents=True)
            test_dir.mkdir(parents=True)
            (src / "UserService.java").write_text("public class UserService {}")
            (test_dir / "UserServiceTest.java").write_text(
                "import org.junit.Test;\n"
                "public class UserServiceTest { @Test void test() {} }"
            )
            result = analyze_tests(repo)
            assert result["total_src"] >= 1
            assert result["total_tests"] >= 1
            assert len(result["covered"]) >= 1
            assert result["ratio"] > 0.0

    def test_detects_junit_framework(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            test_dir = repo / "src" / "test" / "java" / "com" / "example"
            test_dir.mkdir(parents=True)
            (test_dir / "DemoTest.java").write_text(
                "import org.junit.Test;\n"
                "import static org.mockito.Mockito.*;\n"
                "public class DemoTest {}\n"
            )
            result = analyze_tests(repo)
            assert "JUnit" in result["framework"]
            assert "Mockito" in result["framework"]

    def test_detects_testng(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            test_dir = repo / "src" / "test" / "java" / "com" / "example"
            test_dir.mkdir(parents=True)
            (test_dir / "DemoTest.java").write_text(
                "import org.testng.annotations.Test;\n"
                "public class DemoTest {}\n"
            )
            result = analyze_tests(repo)
            assert "TestNG" in result["framework"]


class TestFindUntestedCritical:
    def test_no_endpoints(self):
        analysis = {"covered": [], "uncovered": []}
        result = find_untested_critical(analysis, [])
        assert len(result) == 0

    def test_untested_post_endpoint(self):
        analysis = {"covered": ["UserController.java"], "uncovered": []}
        endpoints = [
            {
                "method": "POST",
                "path": "/api/orders",
                "controller": "OrderController",
            }
        ]
        result = find_untested_critical(analysis, endpoints)
        assert len(result) >= 1
        assert result[0].severity == RiskSeverity.HIGH
        assert "Untested endpoint" in result[0].title
        assert "POST" in result[0].title

    def test_tested_endpoint_no_risk(self):
        analysis = {"covered": ["UserController.java"], "uncovered": []}
        endpoints = [
            {
                "method": "GET",
                "path": "/api/users",
                "controller": "UserController",
            }
        ]
        result = find_untested_critical(analysis, endpoints)
        assert len(result) == 0

    def test_get_endpoint_is_medium(self):
        analysis = {"covered": [], "uncovered": []}
        endpoints = [
            {
                "method": "GET",
                "path": "/api/data",
                "controller": "DataController",
            }
        ]
        result = find_untested_critical(analysis, endpoints)
        assert len(result) >= 1
        assert result[0].severity == RiskSeverity.MEDIUM

    def test_delete_endpoint_is_high(self):
        analysis = {"covered": [], "uncovered": []}
        endpoints = [
            {
                "method": "DELETE",
                "path": "/api/users/1",
                "controller": "UserController",
            }
        ]
        result = find_untested_critical(analysis, endpoints)
        assert len(result) >= 1
        assert result[0].severity == RiskSeverity.HIGH
