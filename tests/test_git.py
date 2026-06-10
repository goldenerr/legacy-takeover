import shutil
import subprocess
from pathlib import Path
import pytest
from legacy_takeover.core.git import clone_repo, cleanup_repo


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


def _make_local_git_repo(parent: Path, name: str, filename: str = "README.md",
                         content: str = "# Test Repo\n") -> Path:
    """Create a local git repo to use when GitHub is unreachable."""
    repo = parent / name
    repo.mkdir()
    (repo / filename).write_text(content)
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=str(repo), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=str(repo), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"],
                   cwd=str(repo), capture_output=True, check=True)
    return repo


_SKIP_NETWORK = False


@pytest.fixture(scope="session", autouse=True)
def _check_network():
    """Check once whether public GitHub clone works."""
    global _SKIP_NETWORK
    import tempfile
    try:
        d = tempfile.mkdtemp()
        r = subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/nickstenning/loguru-examples", d],
            capture_output=True, text=True, timeout=30,
        )
        _SKIP_NETWORK = (r.returncode != 0)
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        _SKIP_NETWORK = True


class TestCloneRepo:
    def test_clone_public_repo(self, temp_dir):
        url = "https://github.com/nickstenning/loguru-examples"
        dest = temp_dir / "repo"
        if _SKIP_NETWORK:
            local = _make_local_git_repo(temp_dir, "local_src", "README.md")
            url = str(local)
        path = clone_repo(url, str(dest))
        assert path.exists()
        assert (path / "README.md").exists()

    def test_clone_shallow_one_commit(self, temp_dir):
        url = "https://github.com/nickstenning/loguru-examples"
        dest = temp_dir / "repo"
        if _SKIP_NETWORK:
            local = _make_local_git_repo(temp_dir, "local_src")
            url = str(local)
        clone_repo(url, str(dest))
        result = subprocess.run(
            ["git", "log", "--oneline"], cwd=str(dest),
            capture_output=True, text=True,
        )
        assert len(result.stdout.strip().split("\n")) == 1

    def test_clone_local_path(self, temp_dir):
        local = _make_local_git_repo(temp_dir, "local", "test.txt", "hello")
        dest = temp_dir / "cloned"
        path = clone_repo(str(local), str(dest))
        assert (path / "test.txt").read_text() == "hello"


class TestCleanupRepo:
    def test_cleanup_removes_dir(self, temp_dir):
        d = temp_dir / "to_clean"
        d.mkdir()
        (d / "file.txt").write_text("data")
        cleanup_repo(d)
        assert not d.exists()
