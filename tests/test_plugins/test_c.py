"""Tests for C analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.c import CAnalyzer


class TestCAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = CAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_c_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.c").write_text("#include <stdio.h>\nint main() { return 0; }\n")
            a = CAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.04

    def test_detect_with_makefile(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Makefile").write_text("all:\n\tgcc main.c\n")
            a = CAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.4

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "src").mkdir()
            (repo / "main.c").write_text("int main() { return 0; }")
            a = CAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "c"

    def test_extract_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.c").write_text("#include <stdio.h>\n#include <stdlib.h>\nint main(){}")
            a = CAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_strcpy(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.c").write_text("#include <string.h>\nvoid f() { strcpy(buf, src); }")
            a = CAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("strcpy" in r.title.lower() for r in risks)
