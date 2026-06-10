"""Tests for C# analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.csharp import CSharpAnalyzer


class TestCSharpAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = CSharpAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_cs_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Program.cs").write_text("class Program {}")
            a = CSharpAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.03

    def test_detect_with_csproj(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "MyApp.csproj").write_text("<Project />")
            a = CSharpAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.25

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Controllers").mkdir()
            (repo / "Program.cs").write_text("class Program {}")
            a = CSharpAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "csharp"

    def test_extract_dependencies(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "MyApp.csproj").write_text(
                '<Project><ItemGroup>'
                '<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />'
                '<PackageReference Include="Serilog" Version="3.0.0" />'
                '</ItemGroup></Project>'
            )
            a = CSharpAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_secret(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Config.cs").write_text('class Config { string API_KEY = "sk-abc123456789"; }')
            a = CSharpAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any(r.category.value == "security" for r in risks)
