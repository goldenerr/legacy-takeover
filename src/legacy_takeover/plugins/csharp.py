"""C#/.NET language analyzer plugin."""
from __future__ import annotations
import re
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class CSharpAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "csharp"
    file_patterns: ClassVar[list[str]] = ["*.cs", "*.csproj", "*.sln", "*.csx"]

    def detect(self) -> float:
        score = 0.0
        cs_files = list(self.repo_path.rglob("*.cs"))
        score += min(0.5, len(cs_files)*0.03)
        for i in ["*.csproj","*.sln"]:
            if list(self.repo_path.rglob(i)): score += 0.25
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in ("bin","obj",".git","packages"): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix in (".cs",".csproj",".sln",".json",".config"): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        return ModuleGraph(language="csharp", root=root, modules=modules, summary=f"C# project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        for csproj in self.repo_path.rglob("*.csproj"):
            try:
                for m in re.finditer(r'<PackageReference\s+Include="([^"]+)"', csproj.read_text()):
                    external.add(m.group(1))
            except: pass
        return DependencyTree(language="csharp", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        tables = []; orm = "unknown"
        for f in self.repo_path.rglob("*.cs"):
            try:
                c = f.read_text()
                if "DbContext" in c: orm = "entity_framework"
                for m in re.finditer(r'public\s+DbSet<(\w+)>\s+(\w+)', c):
                    tables.append(Table(name=m.group(2).lower(), columns=[Column(name="Id", type="int", primary_key=True)]))
            except: pass
        return ERDiagram(language="csharp", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.cs"):
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                for m in re.finditer(r'(?:API_KEY|SECRET|PASSWORD|ConnectionString)\s*=\s*"[^"]{8,}"', c):
                    rid += 1; ln = c[:m.start()].count("\n")+1
                    risks.append(Risk(id=f"CS-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Hardcoded secret", description=f"Secret in {rp}", file=rp, line=ln, evidence=m.group()[:80], recommendation="Use appsettings or key vault."))
                if "Thread.Sleep" in c:
                    rid += 1; ln = c[:c.index("Thread.Sleep")].count("\n")+1
                    risks.append(Risk(id=f"CS-PERF-{rid:03d}", category=RiskCategory.PERFORMANCE, severity=RiskSeverity.MEDIUM, confidence=0.7, title="Thread.Sleep() detected", description=f"Sync sleep in {rp}", file=rp, line=ln, recommendation="Use Task.Delay()."))
            except: pass
        return risks
