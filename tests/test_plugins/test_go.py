"""Tests for Go analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.go import GoAnalyzer


class TestGoAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = GoAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_go_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.go").write_text("package main\nfunc main() {}\n")
            a = GoAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.05

    def test_detect_with_go_mod(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "go.mod").write_text("module example.com/app")
            a = GoAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.5

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "cmd").mkdir()
            (repo / "main.go").write_text("package main")
            a = GoAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "go"
            assert any(m.name == "main.go" for m in graph.modules)

    def test_extract_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "go.mod").write_text(
                "module example.com/app\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n\tgithub.com/lib/pq v1.10.0\n)\n"
            )
            a = GoAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_secret(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "config.go").write_text('package config\nvar API_KEY = "sk-12345678"\n')
            a = GoAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(r.category.value == "security" for r in risks)
