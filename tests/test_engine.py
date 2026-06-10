"""Tests for the core scan engine pipeline (engine.py)."""

import subprocess
from pathlib import Path

import pytest

from legacy_takeover.plugins.base import (
    Dependency,
    DependencyTree,
    DependencyType,
    ERDiagram,
    LanguageAnalyzer,
    Module,
    ModuleGraph,
    ModuleType,
    Risk,
    RiskCategory,
    RiskSeverity,
)


class PassThroughAnalyzer(LanguageAnalyzer):
    """Fake analyzer that returns predictable data — no real repo scanning."""

    name = "python"
    file_patterns = ["*.py"]

    def detect(self) -> float:
        return 0.9

    def extract_structure(self) -> ModuleGraph:
        return ModuleGraph(
            language="python",
            root=Module(
                name="root",
                path=str(self.repo_path),
                type=ModuleType.PACKAGE,
            ),
            modules=[
                Module(
                    name="main",
                    path=str(self.repo_path / "main.py"),
                    type=ModuleType.FILE,
                ),
            ],
            summary="Test project",
        )

    def extract_dependencies(self) -> DependencyTree:
        return DependencyTree(
            language="python",
            nodes=["main"],
            edges=[
                Dependency(
                    from_module="main",
                    to_module="click",
                    type=DependencyType.IMPORT,
                ),
            ],
            external_deps=["click"],
            summary="Uses click",
        )

    def extract_db_schema(self) -> ERDiagram:
        return ERDiagram(language="python", tables=[])

    def assess_risks(self) -> list[Risk]:
        return [
            Risk(
                id="T001",
                category=RiskCategory.TECH_DEBT,
                severity=RiskSeverity.LOW,
                confidence=0.8,
                title="Test risk",
                description="A test risk",
            ),
        ]


def _make_local_git_repo(parent: Path, name: str) -> Path:
    """Create a minimal local git repo for testing."""
    repo = parent / name
    repo.mkdir()
    (repo / "main.py").write_text("import click\nclick.echo('hi')\n")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo),
        capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    return repo


@pytest.fixture
def sample_repo(tmp_path):
    """Local git repo with a single Python file."""
    return _make_local_git_repo(tmp_path, "sample_repo")


class TestRunScan:
    def test_local_repo_scan_produces_result(self, sample_repo):
        from legacy_takeover.core.engine import run_scan

        result = run_scan(
            repo_url=str(sample_repo),
            depth="quick",
            plugins=[PassThroughAnalyzer],
        )
        assert result.repo_name == sample_repo.name
        assert "python" in result.languages
        assert result.total_modules == 1
        assert result.total_risks == 1

    def test_scan_returns_repo_name_from_url(self, sample_repo):
        from legacy_takeover.core.engine import run_scan

        result = run_scan(
            repo_url=str(sample_repo),
            depth="quick",
            plugins=[PassThroughAnalyzer],
        )
        assert result.repo_name == sample_repo.name

    def test_no_matching_plugin_returns_empty_result(self, tmp_path):
        from legacy_takeover.core.engine import run_scan

        repo = _make_local_git_repo(tmp_path, "empty_repo")

        class NoMatchAnalyzer(LanguageAnalyzer):
            name = "nomatch"
            file_patterns = ["*.zzz"]

            def detect(self) -> float:
                return 0.0

            def extract_structure(self):
                return ModuleGraph(
                    language="nomatch",
                    root=Module(name="r", path=str(repo), type=ModuleType.PACKAGE),
                    modules=[],
                )

            def extract_dependencies(self):
                return DependencyTree(language="nomatch", nodes=[], edges=[], external_deps=[])

            def extract_db_schema(self):
                return ERDiagram(language="nomatch", tables=[])

            def assess_risks(self) -> list[Risk]:
                return []

        result = run_scan(
            repo_url=str(repo),
            depth="quick",
            plugins=[NoMatchAnalyzer],
        )
        assert result.languages == []
        assert result.total_modules == 0

    def test_scan_stores_dependency_data(self, sample_repo):
        from legacy_takeover.core.engine import run_scan

        result = run_scan(
            repo_url=str(sample_repo),
            depth="quick",
            plugins=[PassThroughAnalyzer],
        )
        assert result.total_dependencies == 1
        assert "click" in result.external_deps

    def test_output_dir_triggers_no_error_when_module_missing(self, sample_repo, tmp_path):
        """run_scan should not crash if report.renderer is unavailable."""
        from legacy_takeover.core.engine import run_scan

        out_dir = tmp_path / "reports"
        out_dir.mkdir()
        result = run_scan(
            repo_url=str(sample_repo),
            depth="quick",
            plugins=[PassThroughAnalyzer],
            output_dir=str(out_dir),
        )
        # Should still return a valid ScanResult even if renderer is missing
        assert result.repo_name == sample_repo.name
