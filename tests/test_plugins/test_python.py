"""Tests for Python analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.python import PythonAnalyzer


class TestPythonAnalyzer:
    def test_detect_empty_repo_returns_low_score(self):
        with tempfile.TemporaryDirectory() as d:
            a = PythonAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_py_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "main.py").write_text("print('hello')")
            (repo / "utils.py").write_text("# utils")
            a = PythonAnalyzer(repo_path=repo)
            score = a.detect()
            assert score > 0.0
            assert score <= 1.0

    def test_detect_with_requirements_txt(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "requirements.txt").write_text("flask==2.0.0")
            a = PythonAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.15

    def test_extract_structure_detects_packages(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "myapp").mkdir()
            (repo / "myapp" / "__init__.py").write_text("")
            (repo / "main.py").write_text("print('hello')")
            a = PythonAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "python"
            assert any(m.name == "myapp" for m in graph.modules)
            assert any(m.name == "main.py" for m in graph.modules)

    def test_extract_dependencies_parses_requirements(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "requirements.txt").write_text("flask==2.0.0\nrequests>=2.28\n# comment")
            a = PythonAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert "flask" in tree.external_deps
            assert "requests" in tree.external_deps

    def test_extract_db_schema_sqlalchemy(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "models.py").write_text(
                "from sqlalchemy import Column, Integer, String\n"
                "from sqlalchemy.ext.declarative import declarative_base\n"
                "Base = declarative_base()\n"
                "class User(Base):\n"
                '    __tablename__ = "users"\n'
                "    id = Column(Integer, primary_key=True)\n"
            )
            a = PythonAnalyzer(repo_path=repo)
            diagram = a.extract_db_schema()
            assert len(diagram.tables) >= 1
            assert diagram.orm_framework == "sqlalchemy"

    def test_assess_risks_detects_hardcoded_secret(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "config.py").write_text('API_KEY = "sk-abcdef123456"\n')
            a = PythonAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert len(risks) >= 1
            assert any(r.category.value == "security" for r in risks)
