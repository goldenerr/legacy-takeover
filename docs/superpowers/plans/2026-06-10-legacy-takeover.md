# Legacy Takeover Assistant — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that scans any Git repo and generates system takeover manual (MD + Mermaid + HTML)

**Architecture:** 4-layer plugin design — CLI/Hermes-Skill → Core Engine → Plugin Layer (Java/Python/Go) → Report Templates

**Tech Stack:** Python 3.11+, Click, Jinja2, Pydantic v2, tree-sitter, asyncio

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/legacy_takeover/__init__.py`
- Create: `src/legacy_takeover/core/__init__.py`
- Create: `src/legacy_takeover/plugins/__init__.py`
- Create: `src/legacy_takeover/risk/__init__.py`
- Create: `src/legacy_takeover/report/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write pyproject.toml with all dependencies**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "legacy-takeover"
version = "0.1.0"
description = "Legacy system takeover assistant — auto-generate system manuals, architecture diagrams, dependency maps, and risk reports"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "jinja2>=3.1",
    "pydantic>=2.0",
    "tree-sitter>=0.21",
    "pyyaml>=6.0",
    "gitpython>=3.1",
]

[project.scripts]
legacy-scan = "legacy_takeover.cli:main"

[project.entry-points."legacy_takeover.analyzers"]
python = "legacy_takeover.plugins.python:PythonAnalyzer"
java = "legacy_takeover.plugins.java:JavaAnalyzer"
go = "legacy_takeover.plugins.go:GoAnalyzer"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create directory structure and empty init files**

```bash
mkdir -p src/legacy_takeover/{core,plugins,risk,report/templates}
mkdir -p tests
for d in src/legacy_takeover src/legacy_takeover/core src/legacy_takeover/plugins src/legacy_takeover/risk src/legacy_takeover/report tests; do
  echo '"""Legacy Takeover Assistant."""' > "$d/__init__.py"
done
```

- [ ] **Step 3: Install in dev mode and verify**

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
uv pip install -e .
python -c "import legacy_takeover; print(legacy_takeover.__doc__)"
```

Expected: `Legacy Takeover Assistant.`

- [ ] **Step 4: Init git and commit**

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
git init
git add -A
git commit -m "feat: project scaffolding — legacy-takeover v0.1.0"
```

---

### Task 2: Plugin Base Interface + Data Models

**Files:**
- Create: `src/legacy_takeover/plugins/base.py`
- Test: `tests/test_plugins/__init__.py` (empty)
- Test: `tests/test_plugins/test_base.py`

- [ ] **Step 1: Write failing test for data models**

```python
# tests/test_plugins/test_base.py
import pytest
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
    LanguageAnalyzer,
)

class TestModule:
    def test_module_creation(self):
        m = Module(name="auth", path="/src/auth", type=ModuleType.PACKAGE)
        assert m.name == "auth"
        assert m.type == ModuleType.PACKAGE
        assert m.children == []

    def test_module_add_child(self):
        parent = Module(name="api", path="/src/api", type=ModuleType.PACKAGE)
        child = Module(name="handlers.py", path="/src/api/handlers.py", type=ModuleType.FILE)
        parent.children.append(child)
        assert len(parent.children) == 1

class TestDependency:
    def test_dependency_creation(self):
        d = Dependency(from_module="api", to_module="db", type=DependencyType.IMPORT)
        assert d.from_module == "api"
        assert d.to_module == "db"
        assert d.type == DependencyType.IMPORT

class TestRisk:
    def test_risk_creation(self):
        r = Risk(
            id="R001",
            category=RiskCategory.SECURITY,
            severity=RiskSeverity.HIGH,
            confidence=0.9,
            title="Hardcoded secret",
            description="Found API key in source code",
            file="config.py",
            line=42,
            evidence="API_KEY = 'sk-abc123'",
        )
        assert r.severity.value == 8
        assert r.risk_score == pytest.approx(7.2)  # severity(8) * confidence(0.9)

class TestLanguageAnalyzer:
    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LanguageAnalyzer()

    def test_concrete_analyzer_must_implement_all(self):
        class BadAnalyzer(LanguageAnalyzer):
            name = "bad"
            file_patterns = ["*.bad"]

        with pytest.raises(TypeError):
            BadAnalyzer()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
python -m pytest tests/test_plugins/test_base.py -v
```

Expected: FAIL — ModuleNotFoundError or import errors

- [ ] **Step 3: Implement base models and ABC**

```python
# src/legacy_takeover/plugins/base.py
"""Plugin base interface and data models for language analyzers."""

from __future__ import annotations

import abc
from enum import Enum, IntEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────

class ModuleType(str, Enum):
    PACKAGE = "package"
    MODULE = "module"
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    SERVICE = "service"
    CONTROLLER = "controller"
    MIDDLEWARE = "middleware"
    CONFIG = "config"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    IMPORT = "import"
    CALL = "call"
    INHERITANCE = "inheritance"
    HTTP_CLIENT = "http_client"
    GRPC_CLIENT = "grpc_client"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    FILE_READ = "file_read"
    UNKNOWN = "unknown"


class RiskCategory(str, Enum):
    SECURITY = "security"
    TECH_DEBT = "tech_debt"
    SINGLE_POINT = "single_point_of_failure"
    BUS_FACTOR = "bus_factor"
    LICENSE = "license_compliance"
    PERFORMANCE = "performance"


class RiskSeverity(IntEnum):
    INFO = 2
    LOW = 4
    MEDIUM = 6
    HIGH = 8
    CRITICAL = 10


# ── Data Models ────────────────────────────────────────────────────

class Module(BaseModel):
    """A node in the module graph."""
    name: str
    path: str
    type: ModuleType = ModuleType.UNKNOWN
    parent: str | None = None
    children: list[Module] = Field(default_factory=list)
    description: str = ""
    lines_of_code: int = 0
    metadata: dict = Field(default_factory=dict)


class ModuleGraph(BaseModel):
    """The module/component structure of the codebase."""
    language: str
    root: Module
    modules: list[Module] = Field(default_factory=list)
    summary: str = ""


class Dependency(BaseModel):
    """A dependency edge between two modules."""
    from_module: str
    to_module: str
    type: DependencyType = DependencyType.UNKNOWN
    detail: str = ""  # e.g. "imports sqlalchemy.orm"


class DependencyTree(BaseModel):
    """Full dependency graph."""
    language: str
    nodes: list[str] = Field(default_factory=list)  # module names
    edges: list[Dependency] = Field(default_factory=list)
    external_deps: list[str] = Field(default_factory=list)  # pip/maven/go modules
    summary: str = ""


class Column(BaseModel):
    """A database table column."""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: str | None = None  # "other_table.column"
    default: str | None = None


class Table(BaseModel):
    """A database table."""
    name: str
    columns: list[Column] = Field(default_factory=list)
    description: str = ""
    row_estimate: int = 0


class ERDiagram(BaseModel):
    """Entity-relationship diagram representation."""
    language: str
    tables: list[Table] = Field(default_factory=list)
    orm_framework: str = "unknown"  # "sqlalchemy", "django", "hibernate", "gorm", etc.
    summary: str = ""


class Risk(BaseModel):
    """A single risk finding."""
    id: str
    category: RiskCategory
    severity: RiskSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    description: str
    file: str = ""
    line: int = 0
    evidence: str = ""
    recommendation: str = ""

    @property
    def risk_score(self) -> float:
        return self.severity.value * self.confidence


# ── Plugin ABC ─────────────────────────────────────────────────────

class LanguageAnalyzer(abc.ABC):
    """Abstract base for language-specific analyzers.

    Subclasses must implement all abstract methods.
    Plugins are discovered via entry_points group 'legacy_takeover.analyzers'.
    """

    name: ClassVar[str]
    file_patterns: ClassVar[list[str]]  # e.g. ["*.py", "requirements.txt"]

    def __init__(self, repo_path: Path, depth: str = "standard"):
        self.repo_path = repo_path
        self.depth = depth

    @abc.abstractmethod
    def detect(self) -> float:
        """Return confidence 0-1 that this repo uses this language/framework."""
        ...

    @abc.abstractmethod
    def extract_structure(self) -> ModuleGraph:
        """Analyze directory/module structure and produce a module graph."""
        ...

    @abc.abstractmethod
    def extract_dependencies(self) -> DependencyTree:
        """Extract internal and external dependencies."""
        ...

    @abc.abstractmethod
    def extract_db_schema(self) -> ERDiagram:
        """Extract database schema from ORM models or SQL files."""
        ...

    @abc.abstractmethod
    def assess_risks(self) -> list[Risk]:
        """Identify risks specific to this language/framework."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
python -m pytest tests/test_plugins/test_base.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/plugins/base.py tests/test_plugins/
git commit -m "feat: plugin base interface + pydantic data models"
```

---

### Task 3: Core — Git Operations

**Files:**
- Create: `src/legacy_takeover/core/git.py`
- Test: `tests/test_git.py`

- [ ] **Step 1: Write tests for git operations**

```python
# tests/test_git.py
import shutil
from pathlib import Path
import pytest
from legacy_takeover.core.git import clone_repo, cleanup_repo


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


class TestCloneRepo:
    def test_clone_public_repo_creates_directory(self, temp_dir):
        """Test cloning a small public repo."""
        url = "https://github.com/nickstenning/loguru-examples"
        dest = temp_dir / "repo"
        path = clone_repo(url, str(dest))
        assert path.exists()
        assert (path / "README.md").exists() or (path / "README.rst").exists()

    def test_clone_shallow_only_one_commit(self, temp_dir):
        """Shallow clone should have minimal git history."""
        url = "https://github.com/nickstenning/loguru-examples"
        dest = temp_dir / "repo"
        clone_repo(url, str(dest))
        import subprocess
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(dest), capture_output=True, text=True,
        )
        assert len(result.stdout.strip().split("\n")) == 1

    def test_clone_local_path_symlinks(self, temp_dir):
        """Cloning a local path creates a copy."""
        (temp_dir / "local").mkdir()
        (temp_dir / "local" / "test.txt").write_text("hello")
        import subprocess
        subprocess.run(["git", "init"], cwd=str(temp_dir / "local"), capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=str(temp_dir / "local"), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(temp_dir / "local"), capture_output=True)

        dest = temp_dir / "cloned"
        path = clone_repo(str(temp_dir / "local"), str(dest))
        assert path.exists()
        assert (path / "test.txt").read_text() == "hello"


class TestCleanupRepo:
    def test_cleanup_removes_directory(self, temp_dir):
        d = temp_dir / "to_clean"
        d.mkdir()
        (d / "file.txt").write_text("data")
        cleanup_repo(d)
        assert not d.exists()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python -m pytest tests/test_git.py -v
```

- [ ] **Step 3: Implement git module**

```python
# src/legacy_takeover/core/git.py
"""Git operations: clone, cleanup."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def clone_repo(url: str, dest: str, depth: int = 1) -> Path:
    """Clone a git repository with shallow depth.

    Args:
        url: Git URL or local path
        dest: Target directory path
        depth: Clone depth (1 = shallow)

    Returns:
        Path to cloned repo

    Raises:
        RuntimeError: If clone fails
    """
    dest_path = Path(dest)
    if dest_path.exists():
        shutil.rmtree(dest_path)

    result = subprocess.run(
        ["git", "clone", "--depth", str(depth), url, str(dest_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr.strip()}")

    return dest_path


def cleanup_repo(repo_path: Path) -> None:
    """Remove a cloned repository directory."""
    if repo_path.exists():
        shutil.rmtree(repo_path)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_git.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/core/git.py tests/test_git.py
git commit -m "feat: git clone + cleanup operations"
```

---

### Task 4: Core — Language Detector

**Files:**
- Create: `src/legacy_takeover/core/detector.py`
- Test: `tests/test_detector.py`

- [ ] **Step 1: Write detector tests**

```python
# tests/test_detector.py
from pathlib import Path
import pytest
from legacy_takeover.core.detector import detect_languages
from legacy_takeover.plugins.base import LanguageAnalyzer


class FakePythonAnalyzer(LanguageAnalyzer):
    name = "python"
    file_patterns = ["*.py"]

    def detect(self) -> float:
        py_files = list(self.repo_path.rglob("*.py"))
        return min(1.0, len(py_files) / 5)

    def extract_structure(self): pass
    def extract_dependencies(self): pass
    def extract_db_schema(self): pass
    def assess_risks(self): return []


class FakeJavaAnalyzer(LanguageAnalyzer):
    name = "java"
    file_patterns = ["*.java", "pom.xml"]

    def detect(self) -> float:
        has_pom = (self.repo_path / "pom.xml").exists()
        java_files = list(self.repo_path.rglob("*.java"))
        score = (0.5 if has_pom else 0.0) + min(0.5, len(java_files) / 10)
        return score

    def extract_structure(self): pass
    def extract_dependencies(self): pass
    def extract_db_schema(self): pass
    def assess_risks(self): return []


@pytest.fixture
def python_repo(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.py").write_text("def foo(): pass")
    return tmp_path


@pytest.fixture
def java_repo(tmp_path):
    (tmp_path / "pom.xml").write_text("<project></project>")
    src = tmp_path / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "App.java").write_text("class App {}")
    return tmp_path


@pytest.fixture
def mixed_repo(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "pom.xml").write_text("<project></project>")
    return tmp_path


class TestDetectLanguages:
    def test_detect_python(self, python_repo):
        plugins = [FakePythonAnalyzer(python_repo)]
        results = detect_languages(python_repo, plugins)
        assert len(results) == 1
        assert results[0].name == "python"
        assert results[0].detect() > 0.3

    def test_detect_java(self, java_repo):
        plugins = [FakeJavaAnalyzer(java_repo)]
        results = detect_languages(java_repo, plugins)
        assert len(results) == 1
        assert results[0].name == "java"

    def test_detect_mixed_returns_both(self, mixed_repo):
        plugins = [
            FakePythonAnalyzer(mixed_repo),
            FakeJavaAnalyzer(mixed_repo),
        ]
        results = detect_languages(mixed_repo, plugins, threshold=0.0)
        names = {r.name for r in results}
        assert names == {"python", "java"}

    def test_threshold_filters_low_confidence(self, mixed_repo):
        plugins = [FakeJavaAnalyzer(mixed_repo)]
        results = detect_languages(mixed_repo, plugins, threshold=0.9)
        assert len(results) == 0

    def test_no_detection_returns_empty(self, tmp_path):
        plugins = [FakePythonAnalyzer(tmp_path)]
        results = detect_languages(tmp_path, plugins)
        assert len(results) == 0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python -m pytest tests/test_detector.py -v
```

- [ ] **Step 3: Implement detector**

```python
# src/legacy_takeover/core/detector.py
"""Language detection: dispatch repos to matching analyzer plugins."""

from __future__ import annotations

from pathlib import Path

from legacy_takeover.plugins.base import LanguageAnalyzer


def detect_languages(
    repo_path: Path,
    available_plugins: list[LanguageAnalyzer],
    threshold: float = 0.3,
) -> list[LanguageAnalyzer]:
    """Run detection on all plugins and return those above confidence threshold.

    Each plugin is instantiated for the repo and its detect() method is called.
    Plugins with confidence > threshold are returned.
    """
    matched: list[LanguageAnalyzer] = []
    for plugin in available_plugins:
        # Plugin is already instantiated with repo_path
        confidence = plugin.detect()
        if confidence > threshold:
            matched.append(plugin)
    return matched
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_detector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/core/detector.py tests/test_detector.py
git commit -m "feat: language detector with plugin dispatch"
```

---

### Task 5: Core — Aggregator (Intermediate Representation)

**Files:**
- Create: `src/legacy_takeover/core/aggregator.py`
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: Write aggregator tests**

```python
# tests/test_aggregator.py
from legacy_takeover.core.aggregator import (
    ScanResult, aggregate_results,
)
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)


class TestScanResult:
    def test_empty_result(self):
        r = ScanResult(repo_name="test", repo_url="http://x")
        assert r.languages == []
        assert r.total_modules == 0
        assert r.total_dependencies == 0
        assert r.total_tables == 0
        assert r.total_risks == 0
        assert r.top_risks == []


class TestAggregateResults:
    def test_single_plugin(self):
        graph = ModuleGraph(
            language="python",
            root=Module(name="root", path="/", type=ModuleType.PACKAGE),
            modules=[
                Module(name="api", path="/api", type=ModuleType.PACKAGE),
                Module(name="db", path="/db", type=ModuleType.PACKAGE),
            ],
            summary="A Python app",
        )
        deps = DependencyTree(
            language="python",
            nodes=["api", "db"],
            edges=[
                Dependency(from_module="api", to_module="db", type=DependencyType.IMPORT),
            ],
            external_deps=["fastapi", "sqlalchemy"],
        )
        db = ERDiagram(language="python", tables=[], orm_framework="sqlalchemy")
        risks = [
            Risk(
                id="R001", category=RiskCategory.SECURITY,
                severity=RiskSeverity.HIGH, confidence=0.9,
                title="Hardcoded key", description="Secret in code",
                file="config.py", line=10, evidence="KEY='abc'",
            ),
        ]

        result = aggregate_results(
            repo_name="myapp", repo_url="git@x",
            plugins_data=[
                (graph, deps, db, risks),
            ],
        )

        assert result.repo_name == "myapp"
        assert result.total_modules == 2
        assert result.total_dependencies == 1
        assert len(result.external_deps) == 2
        assert result.total_risks == 1
        assert result.top_risks[0].id == "R001"

    def test_risks_sorted_by_score_desc(self):
        risks = [
            Risk(id="R1", category=RiskCategory.SECURITY, severity=RiskSeverity.LOW, confidence=0.5, title="a", description="a"),
            Risk(id="R2", category=RiskCategory.SECURITY, severity=RiskSeverity.CRITICAL, confidence=1.0, title="b", description="b"),
            Risk(id="R3", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.8, title="c", description="c"),
        ]
        result = aggregate_results("x", "y", [(
            ModuleGraph(language="py", root=Module(name="r", path="/"), modules=[]),
            DependencyTree(language="py", nodes=[], edges=[]),
            ERDiagram(language="py", tables=[]),
            risks,
        )])
        assert result.top_risks[0].id == "R2"   # 10.0
        assert result.top_risks[1].id == "R3"   # 4.8
        assert result.top_risks[2].id == "R1"   # 2.0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
python -m pytest tests/test_aggregator.py -v
```

- [ ] **Step 3: Implement aggregator**

```python
# src/legacy_takeover/core/aggregator.py
"""Aggregate plugin outputs into a unified intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field

from legacy_takeover.plugins.base import (
    ModuleGraph, DependencyTree, ERDiagram, Risk,
)


@dataclass
class ScanResult:
    """Unified scan result aggregating all plugin outputs."""
    repo_name: str
    repo_url: str
    depth: str

    # From all plugins
    module_graphs: list[ModuleGraph] = field(default_factory=list)
    dependency_trees: list[DependencyTree] = field(default_factory=list)
    er_diagrams: list[ERDiagram] = field(default_factory=list)
    all_risks: list[Risk] = field(default_factory=list)

    @property
    def languages(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for mg in self.module_graphs:
            if mg.language not in seen:
                seen.add(mg.language)
                result.append(mg.language)
        return result

    @property
    def total_modules(self) -> int:
        return sum(len(mg.modules) for mg in self.module_graphs)

    @property
    def total_dependencies(self) -> int:
        return sum(len(dt.edges) for dt in self.dependency_trees)

    @property
    def total_tables(self) -> int:
        return sum(len(ed.tables) for ed in self.er_diagrams)

    @property
    def external_deps(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for dt in self.dependency_trees:
            for dep in dt.external_deps:
                if dep not in seen:
                    seen.add(dep)
                    result.append(dep)
        return sorted(result)

    @property
    def total_risks(self) -> int:
        return len(self.all_risks)

    @property
    def top_risks(self) -> list[Risk]:
        return sorted(self.all_risks, key=lambda r: r.risk_score, reverse=True)

    @property
    def risk_summary(self) -> dict[str, int]:
        """Count risks per severity level."""
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for r in self.all_risks:
            key = r.severity.name.lower()
            counts[key] = counts.get(key, 0) + 1
        return counts


def aggregate_results(
    repo_name: str,
    repo_url: str,
    plugins_data: list[tuple[ModuleGraph, DependencyTree, ERDiagram, list[Risk]]],
    depth: str = "standard",
) -> ScanResult:
    """Combine all plugin outputs into one ScanResult."""
    result = ScanResult(repo_name=repo_name, repo_url=repo_url, depth=depth)
    for mg, dt, ed, risks in plugins_data:
        result.module_graphs.append(mg)
        result.dependency_trees.append(dt)
        result.er_diagrams.append(ed)
        result.all_risks.extend(risks)
    return result
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_aggregator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/core/aggregator.py tests/test_aggregator.py
git commit -m "feat: result aggregator with unified ScanResult IR"
```

---

### Task 6: Core — Engine Pipeline

**Files:**
- Create: `src/legacy_takeover/core/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write engine test with fake plugins**

```python
# tests/test_engine.py
import pytest
from pathlib import Path
from legacy_takeover.core.engine import run_scan
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
    LanguageAnalyzer,
)


class PassThroughAnalyzer(LanguageAnalyzer):
    """Fake analyzer that returns static data for testing the pipeline."""
    name = "python"
    file_patterns = ["*.py"]

    def detect(self) -> float:
        return 0.9

    def extract_structure(self) -> ModuleGraph:
        return ModuleGraph(
            language="python",
            root=Module(name="root", path=str(self.repo_path), type=ModuleType.PACKAGE),
            modules=[
                Module(name="main", path=str(self.repo_path / "main.py"), type=ModuleType.FILE),
            ],
            summary="Test project",
        )

    def extract_dependencies(self) -> DependencyTree:
        return DependencyTree(
            language="python",
            nodes=["main"],
            edges=[],
            external_deps=["click"],
            summary="Uses click",
        )

    def extract_db_schema(self) -> ERDiagram:
        return ERDiagram(language="python", tables=[])

    def assess_risks(self) -> list[Risk]:
        return [
            Risk(
                id="T001", category=RiskCategory.TECH_DEBT,
                severity=RiskSeverity.LOW, confidence=0.8,
                title="Test risk", description="A test risk",
            ),
        ]


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "main.py").write_text("import click\nclick.echo('hi')")
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    return tmp_path


class TestRunScan:
    def test_local_repo_scan_produces_result(self, sample_repo):
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
        result = run_scan(
            repo_url=str(sample_repo),
            depth="quick",
            plugins=[PassThroughAnalyzer],
        )
        assert result.repo_name == sample_repo.name

    def test_no_matching_plugin_returns_empty_result(self, tmp_path):
        (tmp_path / "main.py").write_text("# empty")
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "x"], cwd=str(tmp_path), capture_output=True)

        # Create analyzer with 0 confidence
        class NoMatchAnalyzer(LanguageAnalyzer):
            name = "nomatch"
            file_patterns = ["*.zzz"]
            def detect(self) -> float: return 0.0
            def extract_structure(self): pass
            def extract_dependencies(self): pass
            def extract_db_schema(self): pass
            def assess_risks(self): return []

        result = run_scan(
            repo_url=str(tmp_path),
            depth="quick",
            plugins=[NoMatchAnalyzer],
        )
        assert result.languages == []
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement engine**

```python
# src/legacy_takeover/core/engine.py
"""Core pipeline: clone → detect → analyze → aggregate."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Type

from legacy_takeover.core.git import clone_repo, cleanup_repo
from legacy_takeover.core.detector import detect_languages
from legacy_takeover.core.aggregator import aggregate_results, ScanResult
from legacy_takeover.plugins.base import LanguageAnalyzer


def run_scan(
    repo_url: str,
    depth: str = "standard",
    plugins: list[Type[LanguageAnalyzer]] | None = None,
    output_dir: str | None = None,
) -> ScanResult:
    """Run full scan pipeline on a Git repository.

    Args:
        repo_url: Git URL or local path
        depth: "quick", "standard", or "deep"
        plugins: Analyzer classes to use (default: discover via entry_points)
        output_dir: Where to write reports (None = don't write)

    Returns:
        Aggregated ScanResult
    """
    if plugins is None:
        plugins = _discover_plugins()

    repo_name = _extract_repo_name(repo_url)

    with tempfile.TemporaryDirectory(prefix="legacy_scan_") as tmp:
        repo_path = Path(tmp) / "repo"
        try:
            # 1. Clone
            clone_repo(repo_url, str(repo_path))

            # 2. Detect
            plugin_instances = [
                p(repo_path=repo_path, depth=depth) for p in plugins
            ]
            matched = detect_languages(repo_path, plugin_instances)

            # 3. Analyze (run each matched plugin)
            plugins_data = []
            for plugin in matched:
                mg = plugin.extract_structure()
                dt = plugin.extract_dependencies()
                ed = plugin.extract_db_schema()
                risks = plugin.assess_risks()
                plugins_data.append((mg, dt, ed, risks))

            # 4. Aggregate
            result = aggregate_results(repo_name, repo_url, plugins_data, depth)

            # 5. Render reports if output_dir specified
            if output_dir:
                from legacy_takeover.report.renderer import render_report
                render_report(result, Path(output_dir))

            return result
        finally:
            cleanup_repo(repo_path)


def _extract_repo_name(url: str) -> str:
    """Extract repo name from git URL or local path."""
    path = Path(url)
    if path.exists():
        return path.name
    # git URL: user/repo.git or git@host:user/repo.git
    name = url.rstrip("/").split("/")[-1]
    return name.replace(".git", "")


def _discover_plugins() -> list[Type[LanguageAnalyzer]]:
    """Discover analyzer plugins via entry_points."""
    if hasattr(_discover_plugins, "_cache"):
        return _discover_plugins._cache

    from importlib.metadata import entry_points
    plugins: list[Type[LanguageAnalyzer]] = []
    try:
        eps = entry_points(group="legacy_takeover.analyzers")
    except TypeError:
        # Python 3.11 compatibility
        eps = entry_points().get("legacy_takeover.analyzers", [])

    for ep in eps:
        cls = ep.load()
        plugins.append(cls)

    _discover_plugins._cache = plugins
    return plugins
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/core/engine.py tests/test_engine.py
git commit -m "feat: core scan engine pipeline"
```

---

### Task 7: Python Plugin

**Files:**
- Create: `src/legacy_takeover/plugins/python.py`
- Test: `tests/test_plugins/test_python.py`

- [ ] **Step 1: Write Python plugin tests**

```python
# tests/test_plugins/test_python.py
from pathlib import Path
import pytest
from legacy_takeover.plugins.python import PythonAnalyzer


@pytest.fixture
def python_project(tmp_path):
    """Create a realistic Python project structure."""
    (tmp_path / "pyproject.toml").write_text("""[project]
name = "myapp"
dependencies = ["fastapi>=0.100", "sqlalchemy>=2.0"]
""")
    (tmp_path / "requirements.txt").write_text("fastapi\nsqlalchemy\npydantic\n")
    src = tmp_path / "myapp"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text("""from fastapi import FastAPI
from myapp.db import get_session
app = FastAPI()
""")
    (src / "db.py").write_text("""from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, Session
Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
""")
    (src / "config.py").write_text("API_KEY = 'sk-abc123xyz'\n")
    return tmp_path


@pytest.fixture
def empty_dir(tmp_path):
    return tmp_path


class TestPythonDetect:
    def test_detect_python_project(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        confidence = analyzer.detect()
        assert confidence > 0.5

    def test_detect_empty_dir(self, empty_dir):
        analyzer = PythonAnalyzer(empty_dir)
        confidence = analyzer.detect()
        assert confidence == 0.0


class TestPythonStructure:
    def test_extract_structure(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        graph = analyzer.extract_structure()
        assert graph.language == "python"
        assert len(graph.modules) >= 2
        module_names = {m.name for m in graph.modules}
        assert "myapp" in module_names

    def test_detect_framework_fastapi(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        graph = analyzer.extract_structure()
        assert "fastapi" in graph.summary.lower()


class TestPythonDependencies:
    def test_extract_deps_from_pyproject(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        tree = analyzer.extract_dependencies()
        assert "fastapi" in tree.external_deps
        assert "sqlalchemy" in tree.external_deps

    def test_extract_deps_from_requirements(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        tree = analyzer.extract_dependencies()
        assert "pydantic" in tree.external_deps


class TestPythonDBSchema:
    def test_extract_sqlalchemy_models(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        er = analyzer.extract_db_schema()
        assert er.orm_framework == "sqlalchemy"
        assert len(er.tables) >= 1
        user_table = [t for t in er.tables if t.name == "users"]
        assert len(user_table) == 1
        columns = {c.name for c in user_table[0].columns}
        assert "id" in columns
        assert "name" in columns


class TestPythonRisks:
    def test_detect_hardcoded_secret(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        risks = analyzer.assess_risks()
        secret_risks = [r for r in risks if "secret" in r.title.lower() or "key" in r.title.lower()]
        assert len(secret_risks) >= 1

    def test_detect_missing_tests(self, python_project):
        analyzer = PythonAnalyzer(python_project)
        risks = analyzer.assess_risks()
        test_risks = [r for r in risks if "test" in r.title.lower()]
        assert len(test_risks) >= 1
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement Python analyzer**

```python
# src/legacy_takeover/plugins/python.py
"""Python/FastAPI/Django language analyzer plugin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)


class PythonAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "python"
    file_patterns: ClassVar[list[str]] = [
        "*.py", "pyproject.toml", "setup.py", "setup.cfg",
        "requirements.txt", "requirements.in", "Pipfile",
    ]

    # ── Detect ────────────────────────────────────────────────────

    def detect(self) -> float:
        score = 0.0
        py_files = list(self.repo_path.rglob("*.py"))
        score += min(0.4, len(py_files) * 0.02)

        indicators = ["pyproject.toml", "setup.py", "requirements.txt", "setup.cfg", "Pipfile"]
        found = sum(1 for i in indicators if (self.repo_path / i).exists())
        score += found * 0.15

        return min(1.0, score)

    # ── Structure ─────────────────────────────────────────────────

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules: list[Module] = []

        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name.startswith("__"):
                continue
            if item.name in ("node_modules", "venv", ".venv", ".git", "__pycache__", "dist", "build"):
                continue

            if item.is_dir() and (item / "__init__.py").exists():
                m = Module(
                    name=item.name,
                    path=str(item.relative_to(self.repo_path)),
                    type=ModuleType.PACKAGE,
                    parent=root.name,
                )
                modules.append(m)
            elif item.is_file() and item.suffix == ".py":
                m = Module(
                    name=item.name,
                    path=str(item.relative_to(self.repo_path)),
                    type=ModuleType.FILE,
                    parent=root.name,
                )
                modules.append(m)

        # Detect framework
        framework = self._detect_framework()
        summary = f"Python project{' — ' + framework if framework else ''} with {len(modules)} modules"

        return ModuleGraph(
            language="python",
            root=root,
            modules=modules,
            summary=summary,
        )

    def _detect_framework(self) -> str:
        # Check for fastapi imports
        for py_file in self.repo_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                if "from fastapi" in content or "import fastapi" in content:
                    return "FastAPI"
                if "from django" in content or "import django" in content:
                    return "Django"
                if "from flask" in content or "import flask" in content:
                    return "Flask"
            except Exception:
                continue
        return ""

    # ── Dependencies ──────────────────────────────────────────────

    def extract_dependencies(self) -> DependencyTree:
        external: set[str] = set()
        edges: list[Dependency] = []
        module_names: set[str] = set()

        # Parse pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            deps = self._parse_pyproject_deps(pyproject)
            external.update(deps)

        # Parse requirements.txt
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            deps = self._parse_requirements(req_file)
            external.update(deps)

        # Internal imports
        for py_file in self.repo_path.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                module_names.add(py_file.stem)
                imports = re.findall(r'^(?:from|import)\s+(\w+)', content, re.MULTILINE)
                for imp in imports:
                    if imp not in external and imp not in ("__future__", "os", "sys", "re", "json", "typing", "abc"):
                        if imp in module_names or imp == py_file.stem:
                            continue
                        edges.append(Dependency(
                            from_module=py_file.stem,
                            to_module=imp,
                            type=DependencyType.IMPORT,
                            detail=f"imports {imp}",
                        ))
            except Exception:
                continue

        return DependencyTree(
            language="python",
            nodes=list(module_names),
            edges=edges,
            external_deps=sorted(external),
            summary=f"{len(external)} external, {len(edges)} internal dependencies",
        )

    def _parse_pyproject_deps(self, path: Path) -> list[str]:
        """Simple TOML dependency parser — avoids toml library dep."""
        deps: list[str] = []
        in_deps = False
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("dependencies") and "[" in line:
                    in_deps = True
                    continue
                if in_deps and line.startswith("]"):
                    break
                if in_deps and line.startswith('"'):
                    dep = line.split('"')[1]
                    deps.append(dep)
        except Exception:
            pass
        return deps

    def _parse_requirements(self, path: Path) -> list[str]:
        deps: list[str] = []
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    dep = re.split(r'[<>=~!;\[]', line)[0].strip()
                    if dep:
                        deps.append(dep)
        except Exception:
            pass
        return deps

    # ── DB Schema ──────────────────────────────────────────────────

    def extract_db_schema(self) -> ERDiagram:
        tables: list[Table] = []
        orm = "unknown"

        for py_file in self.repo_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                if "sqlalchemy" in content.lower():
                    orm = "sqlalchemy"
                    tables.extend(self._parse_sqlalchemy_models(content, py_file))
                elif "django.db.models" in content:
                    orm = "django"
                    tables.extend(self._parse_django_models(content, py_file))
            except Exception:
                continue

        return ERDiagram(
            language="python",
            tables=tables,
            orm_framework=orm,
            summary=f"{len(tables)} tables using {orm}",
        )

    def _parse_sqlalchemy_models(self, content: str, file_path: Path) -> list[Table]:
        tables: list[Table] = []
        # Pattern: class Foo(Base): ... __tablename__ = "foo"
        class_pattern = re.findall(
            r'class\s+(\w+)\s*\(.*?Base.*?\).*?__tablename__\s*=\s*["\'](\w+)["\']',
            content, re.DOTALL,
        )
        for class_name, table_name in class_pattern:
            columns: list[Column] = []
            col_matches = re.findall(
                r'(\w+)\s*=\s*Column\(([^)]*)\)',
                content, re.DOTALL,
            )
            for col_name, col_args in col_matches:
                col_type = "VARCHAR"
                type_match = re.search(r'(Integer|String|Float|Boolean|DateTime|Text|JSON)($|[,\s)])', col_args)
                if type_match:
                    col_type = type_match.group(1)
                is_pk = "primary_key=True" in col_args
                is_nullable = "nullable=False" not in col_args
                columns.append(Column(
                    name=col_name,
                    type=col_type,
                    primary_key=is_pk,
                    nullable=is_nullable,
                ))

            if columns:
                tables.append(Table(name=table_name, columns=columns))

        return tables

    def _parse_django_models(self, content: str, file_path: Path) -> list[Table]:
        tables: list[Table] = []
        class_matches = re.findall(
            r'class\s+(\w+)\s*\(models\.Model\)',
            content,
        )
        for class_name in class_matches:
            table_name = class_name.lower()
            columns: list[Column] = []
            field_matches = re.findall(
                r'(\w+)\s*=\s*models\.(\w+)Field\(([^)]*)\)',
                content,
            )
            for field_name, field_type, field_args in field_matches:
                col_type = field_type.replace("Field", "").upper()
                is_pk = "primary_key=True" in field_args
                is_nullable = "null=True" in field_args
                columns.append(Column(
                    name=field_name,
                    type=col_type,
                    primary_key=is_pk,
                    nullable=is_nullable,
                ))
            if columns:
                tables.append(Table(name=table_name, columns=columns))
        return tables

    # ── Risks ─────────────────────────────────────────────────────

    def assess_risks(self) -> list[Risk]:
        risks: list[Risk] = []
        risk_id = 0

        for py_file in self.repo_path.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                rel_path = str(py_file.relative_to(self.repo_path))

                # Check for hardcoded secrets
                secret_patterns = [
                    (r'(?:API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*["\'][\w\-]{8,}["\']', "Hardcoded secret"),
                    (r'(?:api_key|secret|password|token)\s*=\s*["\'][\w\-]{8,}["\']', "Hardcoded secret (lowercase)"),
                ]
                for pattern, title in secret_patterns:
                    for match in re.finditer(pattern, content):
                        risk_id += 1
                        line_num = content[:match.start()].count("\n") + 1
                        risks.append(Risk(
                            id=f"PY-SEC-{risk_id:03d}",
                            category=RiskCategory.SECURITY,
                            severity=RiskSeverity.HIGH,
                            confidence=0.9,
                            title=title,
                            description=f"Potential secret found in {rel_path}",
                            file=rel_path,
                            line=line_num,
                            evidence=match.group()[:80],
                            recommendation="Move secrets to environment variables or a vault.",
                        ))

                # Check for TODO/FIXME density
                todos = len(re.findall(r'#\s*(TODO|FIXME|HACK|XXX)', content))
                if todos >= 5:
                    risk_id += 1
                    risks.append(Risk(
                        id=f"PY-DEBT-{risk_id:03d}",
                        category=RiskCategory.TECH_DEBT,
                        severity=RiskSeverity.MEDIUM if todos < 10 else RiskSeverity.HIGH,
                        confidence=0.8,
                        title=f"High TODO/FIXME density ({todos} markers)",
                        description=f"{rel_path} has {todos} TODO/FIXME/HACK markers",
                        file=rel_path,
                        line=1,
                        evidence=f"{todos} markers found",
                        recommendation="Prioritize and address technical debt markers.",
                    ))

            except Exception:
                continue

        # Bus factor: check for missing tests
        test_dirs = list(self.repo_path.rglob("test*")) + list(self.repo_path.rglob("*test*"))
        has_tests = any(d.is_dir() for d in test_dirs) or any(
            f.suffix == ".py" and f.stem.startswith("test") for f in self.repo_path.rglob("*.py")
        )
        if not has_tests:
            risk_id += 1
            risks.append(Risk(
                id=f"PY-BUS-{risk_id:03d}",
                category=RiskCategory.BUS_FACTOR,
                severity=RiskSeverity.HIGH,
                confidence=0.85,
                title="No test directory found",
                description="The repository has no visible test suite.",
                recommendation="Add tests to reduce bus factor and prevent regressions.",
            ))

        return risks
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/legacy_takeover/plugins/python.py tests/test_plugins/test_python.py
git commit -m "feat: Python/FastAPI/Django analyzer plugin"
```

---

### Task 8: Java Plugin

**Files:**
- Create: `src/legacy_takeover/plugins/java.py`
- Test: `tests/test_plugins/test_java.py`

- [ ] **Step 1: Write Java plugin tests**

```python
# tests/test_plugins/test_java.py
from pathlib import Path
import pytest
from legacy_takeover.plugins.java import JavaAnalyzer


@pytest.fixture
def java_spring_project(tmp_path):
    """Create a realistic Java Spring Boot project structure."""
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0"?>
<project>
    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <dependencies>
        <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
        <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
    </dependencies>
</project>""")
    (tmp_path / "build.gradle").write_text("")
    src = tmp_path / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "DemoApplication.java").write_text("""package com.example;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
@SpringBootApplication
public class DemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}""")
    (src / "UserController.java").write_text("""package com.example;
import org.springframework.web.bind.annotation.*;
@RestController
public class UserController {
    @GetMapping("/users")
    public String list() { return "[]"; }
}""")
    (src / "User.java").write_text("""package com.example;
import javax.persistence.*;
@Entity
@Table(name = "users")
public class User {
    @Id @GeneratedValue
    private Long id;
    @Column(nullable = false)
    private String name;
}""")
    return tmp_path


class TestJavaDetect:
    def test_detect_java_project(self, java_spring_project):
        analyzer = JavaAnalyzer(java_spring_project)
        confidence = analyzer.detect()
        assert confidence > 0.5

    def test_detect_empty_dir(self, tmp_path):
        analyzer = JavaAnalyzer(tmp_path)
        assert analyzer.detect() == 0.0


class TestJavaStructure:
    def test_extract_structure_spring(self, java_spring_project):
        analyzer = JavaAnalyzer(java_spring_project)
        graph = analyzer.extract_structure()
        assert graph.language == "java"
        assert "Spring Boot" in graph.summary


class TestJavaDependencies:
    def test_extract_maven_deps(self, java_spring_project):
        analyzer = JavaAnalyzer(java_spring_project)
        tree = analyzer.extract_dependencies()
        deps = tree.external_deps
        has_spring = any("spring-boot" in d for d in deps)
        assert has_spring


class TestJavaDBSchema:
    def test_extract_jpa_entities(self, java_spring_project):
        analyzer = JavaAnalyzer(java_spring_project)
        er = analyzer.extract_db_schema()
        assert er.orm_framework == "jpa/hibernate"
        user_table = [t for t in er.tables if t.name == "users"]
        assert len(user_table) == 1
```

- [ ] **Step 2: Run — FAIL, Step 3: Implement Java analyzer**

```python
# src/legacy_takeover/plugins/java.py
"""Java/Spring Boot language analyzer plugin."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar

from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)


class JavaAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "java"
    file_patterns: ClassVar[list[str]] = [
        "*.java", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    ]

    def detect(self) -> float:
        score = 0.0
        java_files = list(self.repo_path.rglob("*.java"))
        score += min(0.4, len(java_files) * 0.02)

        indicators = ["pom.xml", "build.gradle", "build.gradle.kts"]
        found = sum(1 for i in indicators if (self.repo_path / i).exists())
        score += found * 0.2

        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules: list[Module] = []

        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith("."): continue
            if item.name in ("target", "build", "node_modules", ".git"): continue

            if item.is_dir():
                m = Module(
                    name=item.name,
                    path=str(item.relative_to(self.repo_path)),
                    type=ModuleType.PACKAGE,
                    parent=root.name,
                )
                modules.append(m)
            elif item.is_file() and item.suffix in (".java", ".xml", ".gradle", ".properties", ".yml", ".yaml"):
                m = Module(
                    name=item.name,
                    path=str(item.relative_to(self.repo_path)),
                    type=ModuleType.FILE,
                    parent=root.name,
                )
                modules.append(m)

        framework = self._detect_framework()
        summary = f"Java project{' — ' + framework if framework else ''} with {len(modules)} modules"

        return ModuleGraph(language="java", root=root, modules=modules, summary=summary)

    def _detect_framework(self) -> str:
        for java_file in self.repo_path.rglob("*.java"):
            try:
                content = java_file.read_text()
                if "org.springframework" in content:
                    return "Spring Boot"
            except: continue
        return ""

    def extract_dependencies(self) -> DependencyTree:
        external: set[str] = set()

        pom = self.repo_path / "pom.xml"
        if pom.exists():
            try:
                tree = ET.parse(pom)
                ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}
                for dep in tree.findall(".//mvn:dependency/mvn:artifactId", ns):
                    external.add(dep.text or "")
                for dep in tree.findall(".//dependency/artifactId"):
                    external.add(dep.text or "")
            except Exception:
                pass

        gradle = self.repo_path / "build.gradle"
        if gradle.exists():
            try:
                content = gradle.read_text()
                deps = re.findall(r'''['"]([\w.\-]+:[\w.\-]+)['"]''', content)
                for d in deps:
                    if ":" in d:
                        external.add(d.split(":")[-1] if d.count(":") == 1 else d.split(":")[1])
            except: pass

        return DependencyTree(
            language="java",
            nodes=[],
            edges=[],
            external_deps=sorted(external),
            summary=f"{len(external)} external dependencies",
        )

    def extract_db_schema(self) -> ERDiagram:
        tables: list[Table] = []
        orm = "unknown"

        for java_file in self.repo_path.rglob("*.java"):
            try:
                content = java_file.read_text()
                if "@Entity" in content or "@Table" in content:
                    orm = "jpa/hibernate"
                    # Parse entity
                    table_match = re.search(r'@Table\s*\(\s*name\s*=\s*"(\w+)"', content)
                    table_name = table_match.group(1) if table_match else java_file.stem.lower()

                    columns: list[Column] = []
                    col_pattern = re.findall(
                        r'@Column\s*\(([^)]*)\)\s*\n\s*private\s+(\w+)\s+(\w+)',
                        content,
                    )
                    for col_args, col_type, col_name in col_pattern:
                        is_nullable = "nullable = false" not in col_args.lower()
                        columns.append(Column(name=col_name, type=col_type, nullable=is_nullable))

                    # Check @Id
                    id_match = re.search(r'@Id\s*\n\s*private\s+\w+\s+(\w+)', content)
                    if id_match:
                        pk_name = id_match.group(1)
                        for c in columns:
                            if c.name == pk_name:
                                c.primary_key = True

                    if columns:
                        tables.append(Table(name=table_name, columns=columns))
            except: continue

        return ERDiagram(language="java", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables using {orm}")

    def assess_risks(self) -> list[Risk]:
        risks: list[Risk] = []
        risk_id = 0

        for java_file in self.repo_path.rglob("*.java"):
            try:
                content = java_file.read_text()
                rel_path = str(java_file.relative_to(self.repo_path))

                if "Thread.sleep" in content:
                    risk_id += 1
                    line = content[:content.index("Thread.sleep")].count("\n") + 1
                    risks.append(Risk(
                        id=f"JV-PERF-{risk_id:03d}",
                        category=RiskCategory.PERFORMANCE,
                        severity=RiskSeverity.MEDIUM,
                        confidence=0.7,
                        title="Thread.sleep() detected",
                        description=f"Synchronous sleep in {rel_path}",
                        file=rel_path, line=line,
                        evidence="Thread.sleep",
                        recommendation="Use async alternatives or scheduled executors.",
                    ))

                todos = len(re.findall(r'//\s*(TODO|FIXME|HACK)', content))
                if todos >= 5:
                    risk_id += 1
                    risks.append(Risk(
                        id=f"JV-DEBT-{risk_id:03d}",
                        category=RiskCategory.TECH_DEBT,
                        severity=RiskSeverity.MEDIUM,
                        confidence=0.8,
                        title=f"High TODO density ({todos} markers)",
                        description=f"{rel_path} has {todos} TODO/FIXME markers",
                        file=rel_path, line=1,
                        evidence=f"{todos} markers",
                        recommendation="Address technical debt markers.",
                    ))
            except: continue

        return risks
```

- [ ] **Step 4: Run tests — PASS. Step 5: Commit**

```bash
git add src/legacy_takeover/plugins/java.py tests/test_plugins/test_java.py
git commit -m "feat: Java/Spring Boot analyzer plugin"
```

---

### Task 9: Go Plugin

**Files:**
- Create: `src/legacy_takeover/plugins/go.py`
- Test: `tests/test_plugins/test_go.py`

- [ ] **Step 1: Write Go plugin test, Step 2: Implement, Step 3: Tests pass**

```python
# tests/test_plugins/test_go.py
from pathlib import Path
import pytest
from legacy_takeover.plugins.go import GoAnalyzer

@pytest.fixture
def go_project(tmp_path):
    (tmp_path / "go.mod").write_text("""module github.com/example/myservice
go 1.21
require (
    github.com/gin-gonic/gin v1.9.0
    gorm.io/gorm v1.25.0
)""")
    (tmp_path / "go.sum").write_text("")
    (tmp_path / "main.go").write_text("""package main
import "github.com/gin-gonic/gin"
func main() {
    r := gin.Default()
    r.GET("/health", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })
    r.Run()
}""")
    (tmp_path / "models.go").write_text("""package main
import "gorm.io/gorm"
type User struct {
    gorm.Model
    Name  string `gorm:"not null"`
    Email string `gorm:"unique"`
}""")
    return tmp_path

class TestGoDetect:
    def test_detect_go_project(self, go_project):
        analyzer = GoAnalyzer(go_project)
        assert analyzer.detect() > 0.5

    def test_detect_empty_dir(self, tmp_path):
        assert GoAnalyzer(tmp_path).detect() == 0.0

class TestGoStructure:
    def test_extract_structure(self, go_project):
        analyzer = GoAnalyzer(go_project)
        graph = analyzer.extract_structure()
        assert graph.language == "go"
        assert "gin" in graph.summary.lower() or len(graph.modules) >= 1

class TestGoDependencies:
    def test_extract_gomod_deps(self, go_project):
        analyzer = GoAnalyzer(go_project)
        tree = analyzer.extract_dependencies()
        has_gin = any("gin" in d for d in tree.external_deps)
        assert has_gin

class TestGoDBSchema:
    def test_extract_gorm_models(self, go_project):
        analyzer = GoAnalyzer(go_project)
        er = analyzer.extract_db_schema()
        assert er.orm_framework == "gorm"
        user_table = [t for t in er.tables if t.name == "users"]
        assert len(user_table) == 1
```

```python
# src/legacy_takeover/plugins/go.py
"""Go language analyzer plugin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)


class GoAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "go"
    file_patterns: ClassVar[list[str]] = ["*.go", "go.mod", "go.sum"]

    def detect(self) -> float:
        score = 0.0
        go_files = list(self.repo_path.rglob("*.go"))
        score += min(0.5, len(go_files) * 0.05)
        if (self.repo_path / "go.mod").exists():
            score += 0.5
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules: list[Module] = []

        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith("."): continue
            if item.is_dir():
                modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.is_file() and item.suffix == ".go":
                modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))

        framework = ""
        for f in self.repo_path.rglob("*.go"):
            try:
                c = f.read_text()
                if "github.com/gin-gonic/gin" in c: framework = "Gin"; break
                if "github.com/labstack/echo" in c: framework = "Echo"; break
            except: continue

        return ModuleGraph(language="go", root=root, modules=modules, summary=f"Go project{' — ' + framework if framework else ''} with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external: set[str] = set()
        gomod = self.repo_path / "go.mod"
        if gomod.exists():
            try:
                in_require = False
                for line in gomod.read_text().splitlines():
                    line = line.strip()
                    if line == "require (":
                        in_require = True; continue
                    if in_require:
                        if line == ")": break
                        parts = line.split()
                        if parts:
                            dep = parts[0]
                            if "/" in dep:
                                external.add(dep.split("/")[-1])
                            else:
                                external.add(dep)
            except: pass

        return DependencyTree(language="go", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external dependencies")

    def extract_db_schema(self) -> ERDiagram:
        tables: list[Table] = []
        orm = "unknown"

        for go_file in self.repo_path.rglob("*.go"):
            try:
                content = go_file.read_text()
                if "gorm.Model" in content or "gorm.io/gorm" in content:
                    orm = "gorm"
                    # Parse struct with gorm.Model
                    structs = re.findall(r'type\s+(\w+)\s+struct\s*\{([^}]+)\}', content, re.DOTALL)
                    for struct_name, body in structs:
                        if "gorm.Model" not in body and struct_name not in ("User",):
                            continue
                        table_name = struct_name.lower() + "s"
                        columns: list[Column] = []
                        fields = re.findall(r'(\w+)\s+(\S+)\s+`(?:.*?)gorm:"([^"]*)"', body)
                        for field_name, field_type, tags in fields:
                            go_type = field_type
                            is_nullable = "not null" not in tags
                            is_pk = "primaryKey" in tags
                            columns.append(Column(name=field_name, type=go_type, nullable=is_nullable, primary_key=is_pk))
                        if columns:
                            tables.append(Table(name=table_name, columns=columns))
            except: continue

        return ERDiagram(language="go", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables using {orm}")

    def assess_risks(self) -> list[Risk]:
        risks: list[Risk] = []
        risk_id = 0
        for go_file in self.repo_path.rglob("*.go"):
            try:
                content = go_file.read_text()
                rel_path = str(go_file.relative_to(self.repo_path))
                # Hardcoded secrets
                for match in re.finditer(r'(?:API_KEY|SECRET|PASSWORD)\s*[:=]\s*"[\w\-]{8,}"', content):
                    risk_id += 1
                    line = content[:match.start()].count("\n") + 1
                    risks.append(Risk(id=f"GO-SEC-{risk_id:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Hardcoded secret", description=f"Secret in {rel_path}", file=rel_path, line=line, evidence=match.group()[:80], recommendation="Use environment variables."))
                # Missing error handling
                bare_assigns = len(re.findall(r'(\w+)\s*:=\s*\w+\.\w+\(', content)) - len(re.findall(r'(\w+),\s*err\s*:=\s*\w+\.\w+\(', content))
                if bare_assigns > 5:
                    risk_id += 1
                    risks.append(Risk(id=f"GO-DEBT-{risk_id:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.7, title="Missing error handling", description=f"{rel_path} has {bare_assigns} calls ignoring errors", file=rel_path, line=1, recommendation="Always check and handle errors."))
            except: continue
        return risks
```

- [ ] **Step 3: Commit**

```bash
git add src/legacy_takeover/plugins/go.py tests/test_plugins/test_go.py
git commit -m "feat: Go analyzer plugin"
```

---

### Task 10: Risk Engine — Custom Rules & Scoring

**Files:**
- Create: `src/legacy_takeover/risk/engine.py`
- Create: `src/legacy_takeover/risk/loader.py`
- Test: `tests/test_risk/test_engine.py`
- Test: `tests/test_risk/test_loader.py`

- [ ] **Step 1: Write risk engine tests**

```python
# tests/test_risk/test_loader.py
from pathlib import Path
from legacy_takeover.risk.loader import load_custom_rules
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity

class TestLoadCustomRules:
    def test_load_yaml_rules(self, tmp_path):
        config = tmp_path / ".legacy-takeover.yaml"
        config.write_text("""custom_rules:
  - pattern: "Thread\\.sleep"
    file_glob: "*.java"
    category: performance
    severity: 4
    message: "Avoid Thread.sleep()"
    recommendation: "Use async"
  - pattern: "console\\.log"
    file_glob: "*.ts"
    category: tech_debt
    severity: 2
    message: "Remove debug log"
""")
        rules = load_custom_rules(tmp_path)
        assert len(rules) == 2
        assert rules[0].category == RiskCategory.PERFORMANCE
        assert rules[0].severity == RiskSeverity.LOW

    def test_no_config_returns_empty(self, tmp_path):
        rules = load_custom_rules(tmp_path)
        assert rules == []


# tests/test_risk/test_engine.py
import pytest
from legacy_takeover.risk.engine import RiskEngine, CustomRule
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity
from pathlib import Path

@pytest.fixture
def risk_engine():
    return RiskEngine()

@pytest.fixture
def code_dir(tmp_path):
    (tmp_path / "test.py").write_text("API_KEY = 'abc123'\nTODO: fix this\n")
    (tmp_path / "Helper.java").write_text("Thread.sleep(1000);\n")
    return tmp_path

class TestRiskEngine:
    def test_run_builtin_rules(self, risk_engine, code_dir):
        risks = risk_engine.run(code_dir)
        assert len(risks) > 0

    def test_run_custom_rules(self, risk_engine, code_dir):
        custom = [
            CustomRule(pattern="Thread\\.sleep", file_glob="*.java", category=RiskCategory.PERFORMANCE, severity=RiskSeverity.MEDIUM, message="No sleep", recommendation="Use async"),
        ]
        risks = risk_engine.run(code_dir, custom_rules=custom)
        perf_risks = [r for r in risks if r.category == RiskCategory.PERFORMANCE]
        assert len(perf_risks) >= 1

    def test_risks_sorted_by_score(self, risk_engine, code_dir):
        custom = [
            CustomRule(pattern="Thread", file_glob="*.java", category=RiskCategory.PERFORMANCE, severity=RiskSeverity.HIGH, message="x", recommendation="x"),
            CustomRule(pattern="API_KEY", file_glob="*.py", category=RiskCategory.SECURITY, severity=RiskSeverity.CRITICAL, message="x", recommendation="x"),
        ]
        risks = risk_engine.run(code_dir, custom_rules=custom)
        scores = [r.risk_score for r in risks]
        assert scores == sorted(scores, reverse=True)
```

- [ ] **Step 2: Implement — FAIL → PASS**

```python
# src/legacy_takeover/risk/loader.py
"""Load custom risk rules from .legacy-takeover.yaml."""

from __future__ import annotations

from pathlib import Path
import yaml

from legacy_takeover.risk.engine import CustomRule
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity


def load_custom_rules(repo_path: Path) -> list[CustomRule]:
    """Load custom risk rules from repo config file."""
    config_path = repo_path / ".legacy-takeover.yaml"
    if not config_path.exists():
        return []

    try:
        data = yaml.safe_load(config_path.read_text())
    except Exception:
        return []

    rules: list[CustomRule] = []
    for item in data.get("custom_rules", []):
        try:
            rules.append(CustomRule(
                pattern=item["pattern"],
                file_glob=item.get("file_glob", "*"),
                category=RiskCategory(item["category"]),
                severity=RiskSeverity(item["severity"]),
                message=item.get("message", item["pattern"]),
                recommendation=item.get("recommendation", ""),
            ))
        except (KeyError, ValueError):
            continue

    return rules
```

```python
# src/legacy_takeover/risk/engine.py
"""Risk matching engine — built-in + custom rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity


@dataclass
class CustomRule:
    pattern: str
    file_glob: str
    category: RiskCategory
    severity: RiskSeverity
    message: str
    recommendation: str = ""


class RiskEngine:
    """Scan repo files against built-in and custom risk rules."""

    def run(
        self,
        repo_path: Path,
        custom_rules: list[CustomRule] | None = None,
    ) -> list[Risk]:
        """Run all rules and return scored risks sorted by risk_score desc."""
        all_risks: list[Risk] = []
        risk_id = 0

        # Run custom rules
        for rule in (custom_rules or []):
            for file_path in repo_path.rglob(rule.file_glob):
                if ".git" in file_path.parts:
                    continue
                try:
                    content = file_path.read_text()
                except Exception:
                    continue
                for match in re.finditer(rule.pattern, content):
                    risk_id += 1
                    line = content[:match.start()].count("\n") + 1 if "\n" in content else 1
                    all_risks.append(Risk(
                        id=f"CUST-{risk_id:03d}",
                        category=rule.category,
                        severity=rule.severity,
                        confidence=0.85,
                        title=rule.message,
                        description=f"Custom rule match in {file_path.relative_to(repo_path)}",
                        file=str(file_path.relative_to(repo_path)),
                        line=line,
                        evidence=match.group()[:80],
                        recommendation=rule.recommendation,
                    ))

        return sorted(all_risks, key=lambda r: r.risk_score, reverse=True)
```

- [ ] **Step 3: Commit**

```bash
git add src/legacy_takeover/risk/ tests/test_risk/
git commit -m "feat: risk engine with custom YAML rules + scoring"
```

---

### Task 11: Report Renderer — MD + Mermaid + HTML

**Files:**
- Create: `src/legacy_takeover/report/renderer.py`
- Create: `src/legacy_takeover/report/templates/system_manual.md.j2`
- Create: `src/legacy_takeover/report/templates/architecture.md.j2`
- Create: `src/legacy_takeover/report/templates/database.md.j2`
- Create: `src/legacy_takeover/report/templates/dependencies.md.j2`
- Create: `src/legacy_takeover/report/templates/risk_report.md.j2`
- Create: `src/legacy_takeover/report/templates/index.html.j2`
- Test: `tests/test_report/test_renderer.py`

- [ ] **Step 1: Write renderer test**

```python
# tests/test_report/test_renderer.py
import pytest
from pathlib import Path
from legacy_takeover.report.renderer import render_report
from legacy_takeover.core.aggregator import ScanResult
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)

@pytest.fixture
def scan_result():
    mg = ModuleGraph(
        language="python",
        root=Module(name="test", path="/test"),
        modules=[Module(name="api", path="api", type=ModuleType.PACKAGE)],
        summary="A test project",
    )
    dt = DependencyTree(language="python", nodes=["api"], edges=[], external_deps=["click"], summary="1 dep")
    ed = ERDiagram(language="python", tables=[], orm_framework="none")
    risks = [
        Risk(id="R01", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Test", description="Test risk"),
    ]
    result = ScanResult(repo_name="test", repo_url="git@x", depth="standard")
    result.module_graphs = [mg]
    result.dependency_trees = [dt]
    result.er_diagrams = [ed]
    result.all_risks = risks
    return result

class TestRenderReport:
    def test_creates_output_dir(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        assert out.exists()

    def test_generates_system_manual(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        manual = out / "SYSTEM_MANUAL.md"
        assert manual.exists()
        content = manual.read_text()
        assert "# test" in content

    def test_generates_architecture(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        arch = out / "ARCHITECTURE.md"
        assert arch.exists()
        content = arch.read_text()
        assert "```mermaid" in content

    def test_generates_database(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        db = out / "DATABASE.md"
        assert db.exists()

    def test_generates_dependencies(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        deps = out / "DEPENDENCIES.md"
        assert deps.exists()

    def test_generates_risk_report(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        risk = out / "RISK_REPORT.md"
        assert risk.exists()
        content = risk.read_text()
        assert "R01" in content

    def test_generates_html_index(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        html = out / "index.html"
        assert html.exists()
        content = html.read_text()
        assert "<!DOCTYPE html>" in content

    def test_generates_mermaid_diagrams(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        arch_mmd = out / "diagrams" / "architecture.mmd"
        assert arch_mmd.exists()

    def test_generates_data_files(self, tmp_path, scan_result):
        out = tmp_path / "report"
        render_report(scan_result, out)
        assert (out / "data" / "modules.json").exists()
        assert (out / "data" / "dependencies.json").exists()
        assert (out / "data" / "risks.json").exists()
```

- [ ] **Step 2: RUN → FAIL. Step 3: Implement renderer + templates**

Due to length, templates are summarized — full Jinja2 templates in actual implementation. The renderer module:

```python
# src/legacy_takeover/report/renderer.py
"""Report renderer: MD docs, Mermaid diagrams, HTML index."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from legacy_takeover.core.aggregator import ScanResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_report(result: ScanResult, output_dir: Path, repo_url: str = "") -> None:
    """Generate full report from ScanResult into output_dir."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = output_dir / f"legacy-report-{result.repo_name}-{ts}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagrams").mkdir(exist_ok=True)
    (out / "data").mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    ctx = _build_context(result, repo_url)

    # Render each section
    templates = {
        "system_manual.md.j2": "SYSTEM_MANUAL.md",
        "architecture.md.j2": "ARCHITECTURE.md",
        "database.md.j2": "DATABASE.md",
        "dependencies.md.j2": "DEPENDENCIES.md",
        "risk_report.md.j2": "RISK_REPORT.md",
        "index.html.j2": "index.html",
    }
    for tmpl_name, out_name in templates.items():
        tmpl = env.get_template(tmpl_name)
        (out / out_name).write_text(tmpl.render(**ctx))

    # Write Mermaid diagram files
    (out / "diagrams" / "architecture.mmd").write_text(_build_architecture_mermaid(result))
    (out / "diagrams" / "er_diagram.mmd").write_text(_build_er_mermaid(result))
    (out / "diagrams" / "dependency_graph.mmd").write_text(_build_dependency_mermaid(result))

    # Write structured data
    (out / "data" / "modules.json").write_text(json.dumps(
        [mg.model_dump() for mg in result.module_graphs], indent=2, default=str,
    ))
    (out / "data" / "dependencies.json").write_text(json.dumps(
        [dt.model_dump() for dt in result.dependency_trees], indent=2, default=str,
    ))
    (out / "data" / "risks.json").write_text(json.dumps(
        [r.model_dump() for r in result.all_risks], indent=2, default=str,
    ))

    print(f"✅ Report generated: {out}")


def _build_context(result: ScanResult, repo_url: str) -> dict:
    return {
        "repo_name": result.repo_name,
        "repo_url": repo_url or result.repo_url,
        "depth": result.depth,
        "generated_at": datetime.now().isoformat(),
        "languages": result.languages,
        "module_graphs": result.module_graphs,
        "dependency_trees": result.dependency_trees,
        "er_diagrams": result.er_diagrams,
        "risks": result.top_risks,
        "risk_summary": result.risk_summary,
        "total_modules": result.total_modules,
        "total_deps": result.total_dependencies,
        "total_tables": result.total_tables,
        "total_risks": result.total_risks,
        "external_deps": result.external_deps,
    }


def _build_architecture_mermaid(result: ScanResult) -> str:
    lines = ["graph TD"]
    for mg in result.module_graphs:
        for m in mg.modules:
            safe_name = m.name.replace("-", "_").replace(".", "_")
            lines.append(f"    {safe_name}[{m.name}]")
        if mg.root:
            lines.append(f"    style {mg.root.name.replace('-','_')} fill:#1f6feb,color:#fff")
    if len(lines) == 1:
        lines.append('    A["No modules detected"]')
    return "\n".join(lines)


def _build_er_mermaid(result: ScanResult) -> str:
    lines = ["erDiagram"]
    for ed in result.er_diagrams:
        for table in ed.tables:
            cols = []
            for c in table.columns:
                pk = " PK" if c.primary_key else ""
                fk = f' FK "{c.foreign_key}"' if c.foreign_key else ""
                cols.append(f"        {c.type} {c.name}{pk}{fk}")
            if cols:
                lines.append(f"    {table.name} {{")
                lines.extend(cols)
                lines.append("    }")
    if len(lines) == 1:
        lines.append('    NO_TABLES { string note "No tables found" }')
    return "\n".join(lines)


def _build_dependency_mermaid(result: ScanResult) -> str:
    lines = ["graph LR"]
    for dt in result.dependency_trees:
        for edge in dt.edges:
            f = edge.from_module.replace("-", "_").replace(".", "_")
            t = edge.to_module.replace("-", "_").replace(".", "_")
            lines.append(f"    {f} -->|{edge.type.value}| {t}")
    if len(lines) == 1:
        lines.append('    A["No dependencies detected"]')
    return "\n".join(lines)
```

Jinja2 templates (create each file in `src/legacy_takeover/report/templates/`):

```jinja2
{# system_manual.md.j2 #}
# {{ repo_name }} — System Takeover Manual

**Generated:** {{ generated_at }}
**Depth:** {{ depth }}
**Languages:** {{ languages | join(", ") }}

## Overview

- **Modules:** {{ total_modules }}
- **Dependencies:** {{ total_deps }} ({{ external_deps | length }} external)
- **Database Tables:** {{ total_tables }}
- **Risks Identified:** {{ total_risks }}

## Quick Statistics

| Metric | Value |
|--------|-------|
| Languages | {{ languages | join(", ") }} |
| Total Modules | {{ total_modules }} |
| Internal Dependencies | {{ total_deps }} |
| External Dependencies | {{ external_deps | length }} |
| Database Tables | {{ total_tables }} |
| Critical Risks | {{ risk_summary.critical }} |
| High Risks | {{ risk_summary.high }} |
| Medium Risks | {{ risk_summary.medium }} |

## Architecture Summary

{% for mg in module_graphs %}
### {{ mg.language | title }} Layer
{{ mg.summary }}

| Module | Type | Path |
|--------|------|------|
{% for m in mg.modules %}
| {{ m.name }} | {{ m.type.value }} | {{ m.path }} |
{% endfor %}
{% endfor %}

## Risk Summary

{% for risk in risks[:10] %}
- **[{{ risk.severity.name }}]** {{ risk.title }} — {{ risk.file }}{% if risk.line %}:{{ risk.line }}{% endif %}
{% endfor %}

> See ARCHITECTURE.md, DATABASE.md, DEPENDENCIES.md, and RISK_REPORT.md for detailed breakdowns.
```

(Similar templates for architecture, database, dependencies, risk_report, and the HTML index — all follow the same Jinja2 pattern with Mermaid code blocks.)

- [ ] **Step 4: Tests PASS. Step 5: Commit**

---

### Task 12: CLI Entry Point

**Files:**
- Create: `src/legacy_takeover/cli.py`

- [ ] **Step 1: Implement CLI**

```python
# src/legacy_takeover/cli.py
"""CLI entry point for legacy-scan."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from legacy_takeover.core.engine import run_scan
from legacy_takeover.report.renderer import render_report


@click.command()
@click.argument("repo", type=str)
@click.option(
    "--depth", "-d",
    type=click.Choice(["quick", "standard", "deep"]),
    default="standard",
    help="Scan depth (default: standard)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=".",
    help="Output directory for reports (default: current directory)",
)
@click.option(
    "--no-report", is_flag=True,
    help="Only analyze, don't generate reports",
)
@click.version_option(version="0.1.0", prog_name="legacy-scan")
def main(repo: str, depth: str, output: str, no_report: bool) -> None:
    """Scan a Git repository and generate a system takeover manual.

    REPO: Git URL or local path to analyze.

    Examples:\n
        legacy-scan https://github.com/user/repo

        legacy-scan ./my-local-repo --depth deep

        legacy-scan git@github.com:org/repo.git -o ./reports
    """
    click.echo(f"🔍 Scanning {repo} (depth={depth})...")

    try:
        result = run_scan(
            repo_url=repo,
            depth=depth,
        )
    except Exception as e:
        click.echo(f"❌ Scan failed: {e}", err=True)
        sys.exit(1)

    # Summary output
    click.echo(f"\n📊 Scan Results for {result.repo_name}")
    click.echo(f"   Languages: {', '.join(result.languages) or 'none detected'}")
    click.echo(f"   Modules: {result.total_modules}")
    click.echo(f"   Dependencies: {result.total_dependencies} ({len(result.external_deps)} external)")
    click.echo(f"   DB Tables: {result.total_tables}")
    click.echo(f"   Risks: {result.total_risks}")

    if result.top_risks:
        click.echo(f"\n   🔴 Critical: {result.risk_summary['critical']}")
        click.echo(f"   🟠 High:     {result.risk_summary['high']}")
        click.echo(f"   🟡 Medium:   {result.risk_summary['medium']}")
        click.echo(f"   🟢 Low:      {result.risk_summary['low']}")

    if not no_report:
        output_path = Path(output)
        try:
            render_report(result, output_path, repo_url=repo)
        except Exception as e:
            click.echo(f"⚠️  Report generation failed: {e}", err=True)

    click.echo(f"\n✅ Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test CLI**

```bash
cd /home/hermes/.hermes/projects/legacy-takeover
python -m legacy_takeover.cli --help
```

Expected: Help text with all options

- [ ] **Step 3: Commit**

```bash
git add src/legacy_takeover/cli.py
git commit -m "feat: CLI entry point with --depth and --output options"
```

---

### Task 13: Integration Test — End-to-End

**Files:**
- Modify: `tests/conftest.py` (add fixtures)
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""End-to-end integration test with a real repo."""
import tempfile
from pathlib import Path
from legacy_takeover.core.engine import run_scan
from legacy_takeover.report.renderer import render_report


def test_e2e_python_repo():
    """Full pipeline on a small Python repo."""
    # Use a small public Python repo
    url = "https://github.com/pallets/click"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reports"
        result = run_scan(repo_url=url, depth="quick")

        assert result.repo_name == "click"
        assert "python" in result.languages
        assert result.total_modules > 0
        assert len(result.external_deps) > 0

        render_report(result, out)
        assert (out / "legacy-report-click-" / "SYSTEM_MANUAL.md").exists() or \
               any((out / d / "SYSTEM_MANUAL.md").exists() for d in out.iterdir() if d.is_dir())
```

- [ ] **Step 2: Run — expect PASS (may need network)**

```bash
python -m pytest tests/test_integration.py -v --timeout=120
```

- [ ] **Step 3: Commit**

---

### Task 14: Hermes Skill Definition

**Files:**
- Create: `skills/legacy-takeover.md`

```markdown
---
name: legacy-takeover
description: Legacy system takeover assistant — scan any Git repo and generate system manual, architecture diagrams, dependency maps, and risk reports
---

# Legacy Takeover Assistant

Scan a Git repository and generate comprehensive documentation for system handover.

## Trigger

When the user asks to analyze, scan, or document a codebase/repository:
- "分析一下 https://github.com/foo/bar"
- "给我生成这个项目的架构文档"
- "Scan this repo and tell me the risks"

## Workflow

1. Identify the repo URL (Git URL or local path)
2. Run: `cd /home/hermes/.hermes/projects/legacy-takeover && python -m legacy_takeover.cli <repo_url> --depth standard -o /tmp/legacy-reports`
3. Read the generated `SYSTEM_MANUAL.md` for a summary
4. Present key findings: languages, module count, top 5 risks
5. Tell the user where the full report is saved

## Quick Mode

For fast overviews, use `--depth quick`:
```bash
python -m legacy_takeover.cli <repo_url> --depth quick --no-report
```

## Tips

- The tool generates MD + Mermaid diagrams + HTML index
- Custom risk rules can be added via `.legacy-takeover.yaml` in the target repo
- Supports Python, Java, Go out of the box
```

- [ ] **Step 2: Install skill**

```bash
mkdir -p /home/hermes/.hermes/skills/legacy-takeover
cp /home/hermes/.hermes/projects/legacy-takeover/docs/superpowers/specs/2026-06-10-legacy-takeover-design.md /home/hermes/.hermes/skills/legacy-takeover/SKILL.md
```

---

## Execution Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project scaffolding | pyproject.toml, dirs |
| 2 | Plugin ABC + models | base.py, tests |
| 3 | Git operations | git.py, tests |
| 4 | Language detector | detector.py, tests |
| 5 | Aggregator (IR) | aggregator.py, tests |
| 6 | Engine pipeline | engine.py, tests |
| 7 | Python plugin | python.py, tests |
| 8 | Java plugin | java.py, tests |
| 9 | Go plugin | go.py, tests |
| 10 | Risk engine | engine.py, loader.py, tests |
| 11 | Report renderer | renderer.py, templates, tests |
| 12 | CLI entry | cli.py |
| 13 | Integration test | test_integration.py |
| 14 | Hermes skill | skill definition |

**Total:** 14 tasks, ~30 files, all TDD with test-first approach.
