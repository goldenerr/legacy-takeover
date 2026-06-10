from pathlib import Path
import pytest
from legacy_takeover.plugins.base import LanguageAnalyzer


class FakePythonAnalyzer(LanguageAnalyzer):
    name = "python"
    file_patterns = ["*.py"]

    def detect(self) -> float:
        py_files = list(self.repo_path.rglob("*.py"))
        return min(1.0, len(py_files) / 5)

    def extract_structure(self):
        return None

    def extract_dependencies(self):
        return None

    def extract_db_schema(self):
        return None

    def assess_risks(self):
        return []


class FakeJavaAnalyzer(LanguageAnalyzer):
    name = "java"
    file_patterns = ["*.java", "pom.xml"]

    def detect(self) -> float:
        has_pom = (self.repo_path / "pom.xml").exists()
        java_files = list(self.repo_path.rglob("*.java"))
        score = (0.5 if has_pom else 0.0) + min(0.5, len(java_files) / 10)
        return score

    def extract_structure(self):
        return None

    def extract_dependencies(self):
        return None

    def extract_db_schema(self):
        return None

    def assess_risks(self):
        return []


@pytest.fixture
def python_repo(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.py").write_text("def foo(): pass")
    return tmp_path


@pytest.fixture
def java_repo(tmp_path):
    (tmp_path / "pom.xml").write_text("<project></project>")
    src = tmp_path / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "App.java").write_text("class App {}")
    return tmp_path


@pytest.fixture
def mixed_repo(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "pom.xml").write_text("<project></project>")
    return tmp_path


class TestDetectLanguages:
    def test_detect_python(self, python_repo):
        from legacy_takeover.core.detector import detect_languages

        plugins = [FakePythonAnalyzer(python_repo)]
        results = detect_languages(python_repo, plugins)
        assert len(results) == 1
        assert results[0].name == "python"
        assert results[0].detect() > 0.3

    def test_detect_java(self, java_repo):
        from legacy_takeover.core.detector import detect_languages

        plugins = [FakeJavaAnalyzer(java_repo)]
        results = detect_languages(java_repo, plugins)
        assert len(results) == 1
        assert results[0].name == "java"

    def test_detect_mixed_returns_both(self, mixed_repo):
        from legacy_takeover.core.detector import detect_languages

        plugins = [FakePythonAnalyzer(mixed_repo), FakeJavaAnalyzer(mixed_repo)]
        results = detect_languages(mixed_repo, plugins, threshold=0.0)
        names = {r.name for r in results}
        assert names == {"python", "java"}

    def test_threshold_filters_low_confidence(self, mixed_repo):
        from legacy_takeover.core.detector import detect_languages

        plugins = [FakeJavaAnalyzer(mixed_repo)]
        results = detect_languages(mixed_repo, plugins, threshold=0.9)
        assert len(results) == 0

    def test_no_detection_returns_empty(self, tmp_path):
        from legacy_takeover.core.detector import detect_languages

        plugins = [FakePythonAnalyzer(tmp_path)]
        results = detect_languages(tmp_path, plugins)
        assert len(results) == 0
