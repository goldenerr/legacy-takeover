"""Tests for C++ analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.cpp import CppAnalyzer


class TestCppAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = CppAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_cpp_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.cpp").write_text("#include <iostream>\nint main() { return 0; }\n")
            a = CppAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.03

    def test_detect_with_cmake(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)\nproject(Foo)")
            a = CppAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.3

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "src").mkdir()
            (repo / "main.cpp").write_text("int main() { return 0; }")
            a = CppAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "cpp"

    def test_extract_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.10)\nproject(Foo)\nfind_package(Boost)\nfind_package(OpenCV)\n"
            )
            a = CppAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_reinterpret_cast(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.cpp").write_text("void f() { int* p = reinterpret_cast<int*>(ptr); }")
            a = CppAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("reinterpret_cast" in r.title.lower() for r in risks)
