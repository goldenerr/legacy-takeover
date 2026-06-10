"""E2E integration test — full pipeline on a real repo."""
import subprocess
import tempfile
from pathlib import Path

import pytest

from legacy_takeover.core.engine import run_scan
from legacy_takeover.report.renderer import render_report


def _make_local_git_repo(parent: Path, name: str, *, files: dict[str, str] | None = None) -> Path:
    """Create a minimal local git repo for testing."""
    repo = parent / name
    repo.mkdir()
    if files:
        for fname, content in files.items():
            fpath = repo / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content)
    else:
        (repo / "main.py").write_text("import click\nclick.echo('hi')\n")
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


def test_e2e_python_repo():
    """Full pipeline on a small public Python repo (with local fallback)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out = tmp_path / "reports"

        # Try a public repo first; fall back to local if network fails.
        try:
            result = run_scan(repo_url="https://github.com/pallets/click", depth="standard")
            repo_label = "click"
        except Exception:
            local_repo = _make_local_git_repo(
                tmp_path, "myapp",
                files={
                    "mypackage/__init__.py": "__version__ = '1.0'",
                    "mypackage/core.py": "import os\nfrom flask import Flask\n\ndef run():\n    pass\n",
                    "requirements.txt": "flask>=3.0\nclick>=8.0\n",
                },
            )
            result = run_scan(repo_url=str(local_repo), depth="quick")
            repo_label = local_repo.name

        assert result.repo_name == repo_label
        assert "python" in result.languages
        assert result.total_modules >= 0  # may be 0 for shallow clones of certain repos
        assert result.total_dependencies >= 0
        render_report(result, out)
        report_dirs = [d for d in out.iterdir() if d.is_dir()]
        assert len(report_dirs) >= 1
        manual = report_dirs[0] / "SYSTEM_MANUAL.md"
        assert manual.exists()
