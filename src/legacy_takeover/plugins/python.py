"""Python/FastAPI/Django language analyzer plugin."""
from __future__ import annotations
import re
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class PythonAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "python"
    file_patterns: ClassVar[list[str]] = ["*.py", "pyproject.toml", "setup.py", "requirements.txt", "Pipfile"]

    def detect(self) -> float:
        score = 0.0
        py_files = list(self.repo_path.rglob("*.py"))
        score += min(0.4, len(py_files) * 0.02)
        for i in ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"]:
            if (self.repo_path / i).exists(): score += 0.15
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in ("node_modules","venv",".venv",".git","__pycache__","dist","build"): continue
            if item.is_dir() and (item / "__init__.py").exists():
                modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.is_file() and item.suffix == ".py":
                modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        fw = ""
        for f in self.repo_path.rglob("*.py"):
            try:
                c = f.read_text()
                if "from fastapi" in c or "import fastapi" in c: fw = "FastAPI"; break
                if "from django" in c: fw = "Django"; break
                if "from flask" in c: fw = "Flask"; break
            except: pass
        return ModuleGraph(language="python", root=root, modules=modules, summary=f"Python{' — '+fw if fw else ''} project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        req = self.repo_path / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        dep = re.split(r'[<>=~!;\[\\]', line)[0].strip()
                        if dep: external.add(dep)
            except: pass
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                in_deps = False
                for line in pyproject.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("dependencies") and "[" in line: in_deps = True; continue
                    if in_deps and line.startswith("]"): break
                    if in_deps and line.startswith('"'):
                        dep = line.split('"')[1]; external.add(dep)
            except: pass
        return DependencyTree(language="python", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        tables = []; orm = "unknown"
        for f in self.repo_path.rglob("*.py"):
            try:
                c = f.read_text()
                if "sqlalchemy" in c.lower(): orm = "sqlalchemy"
                elif "django.db.models" in c: orm = "django"
                else: continue
                for m in re.finditer(r'class\s+(\w+)\s*\(.*?Base.*?\).*?__tablename__\s*=\s*["\'](\w+)["\']', c, re.DOTALL):
                    tables.append(Table(name=m.group(2), columns=[Column(name="id", type="Integer", primary_key=True)]))
            except: pass
        if not tables:
            for f in self.repo_path.rglob("*.py"):
                try:
                    c = f.read_text()
                    for m in re.finditer(r'class\s+(\w+)\s*\(models\.Model\)', c):
                        tables.append(Table(name=m.group(1).lower(), columns=[Column(name="id", type="Integer", primary_key=True)]))
                except: pass
        return ERDiagram(language="python", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.py"):
            if "venv" in str(f) or ".venv" in str(f): continue
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                for m in re.finditer(r'(?:API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*["\'][\w\-]{8,}["\']', c):
                    rid += 1; ln = c[:m.start()].count("\n")+1
                    risks.append(Risk(id=f"PY-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Hardcoded secret", description=f"Secret in {rp}", file=rp, line=ln, evidence=m.group()[:80], recommendation="Use environment variables."))
                todos = len(re.findall(r'#\s*(TODO|FIXME|HACK|XXX)', c))
                if todos >= 5:
                    rid += 1
                    risks.append(Risk(id=f"PY-DEBT-{rid:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM if todos<10 else RiskSeverity.HIGH, confidence=0.8, title=f"High TODO density ({todos})", description=f"{rp} has {todos} markers", file=rp, line=1, recommendation="Address tech debt."))
            except: pass
        # Bus factor
        has_tests = any((d.is_dir() and d.name.startswith("test")) for d in self.repo_path.rglob("*")) or any(f.stem.startswith("test") for f in self.repo_path.rglob("*.py"))
        if not has_tests:
            rid += 1
            risks.append(Risk(id=f"PY-BUS-{rid:03d}", category=RiskCategory.BUS_FACTOR, severity=RiskSeverity.HIGH, confidence=0.85, title="No test directory found", description="No visible test suite", recommendation="Add tests."))
        return risks
