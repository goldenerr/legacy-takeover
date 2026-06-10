"""Go language analyzer plugin."""
from __future__ import annotations
import re
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class GoAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "go"
    file_patterns: ClassVar[list[str]] = ["*.go", "go.mod", "go.sum"]

    def detect(self) -> float:
        score = min(0.5, len(list(self.repo_path.rglob("*.go")))*0.05)
        if (self.repo_path/"go.mod").exists(): score += 0.5
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith("."): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix == ".go": modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        fw = ""
        for f in self.repo_path.rglob("*.go"):
            try:
                c = f.read_text()
                if "github.com/gin-gonic/gin" in c: fw = "Gin"; break
                if "github.com/labstack/echo" in c: fw = "Echo"; break
            except: pass
        return ModuleGraph(language="go", root=root, modules=modules, summary=f"Go{' — '+fw if fw else ''} project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        gomod = self.repo_path/"go.mod"
        if gomod.exists():
            try:
                in_req = False
                for line in gomod.read_text().splitlines():
                    line = line.strip()
                    if line == "require (": in_req = True; continue
                    if in_req:
                        if line == ")": break
                        parts = line.split()
                        if parts: external.add(parts[0].split("/")[-1] if "/" in parts[0] else parts[0])
            except: pass
        return DependencyTree(language="go", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        tables = []; orm = "unknown"
        for f in self.repo_path.rglob("*.go"):
            try:
                c = f.read_text()
                if "gorm.Model" in c or "gorm.io/gorm" in c:
                    orm = "gorm"
                    for m in re.finditer(r'type\s+(\w+)\s+struct\s*\{[^}]*\}', c, re.DOTALL):
                        if "gorm.Model" in m.group():
                            tables.append(Table(name=m.group(1).lower()+"s", columns=[Column(name="id", type="uint", primary_key=True)]))
            except: pass
        return ERDiagram(language="go", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.go"):
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                for m in re.finditer(r'(?:API_KEY|SECRET|PASSWORD)\s*[:=]\s*"[\w\-]{8,}"', c):
                    rid += 1; ln = c[:m.start()].count("\n")+1
                    risks.append(Risk(id=f"GO-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Hardcoded secret", description=f"Secret in {rp}", file=rp, line=ln, evidence=m.group()[:80], recommendation="Use environment variables."))
            except: pass
        return risks
