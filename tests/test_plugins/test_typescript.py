"""Tests for TypeScript analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.typescript import TypeScriptAnalyzer


class TestTypeScriptAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = TypeScriptAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_ts_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "index.ts").write_text("const x: number = 1;")
            a = TypeScriptAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.02

    def test_detect_with_package_json(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "package.json").write_text('{"name":"test"}')
            a = TypeScriptAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.3

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "src").mkdir()
            (repo / "index.ts").write_text("export {};")
            a = TypeScriptAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "typescript"
            assert any(m.name == "index.ts" for m in graph.modules)

    def test_extract_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "package.json").write_text(
                '{"dependencies":{"express":"^4.18.0","typescript":"^5.0.0"}}'
            )
            a = TypeScriptAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_secret(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "config.ts").write_text('export const API_KEY = "sk-abcdef123456";')
            a = TypeScriptAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(r.category.value == "security" for r in risks)
