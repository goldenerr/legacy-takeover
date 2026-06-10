"""Git operations: clone, cleanup."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


def clone_repo(url: str, dest: str, depth: int = 1) -> Path:
    dest_path = Path(dest)
    if dest_path.exists():
        shutil.rmtree(dest_path)
    result = subprocess.run(
        ["git", "clone", "--depth", str(depth), url, str(dest_path)],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr.strip()}")
    return dest_path


def cleanup_repo(repo_path: Path) -> None:
    if repo_path.exists():
        shutil.rmtree(repo_path)
