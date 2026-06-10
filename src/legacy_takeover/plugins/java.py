"""Java/Spring Boot language analyzer plugin."""
from __future__ import annotations
import re, xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class JavaAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "java"
    file_patterns: ClassVar[list[str]] = ["*.java", "pom.xml", "build.gradle", "build.gradle.kts"]

    def detect(self) -> float:
        score = 0.0
        java_files = list(self.repo_path.rglob("*.java"))
        score += min(0.4, len(java_files)*0.02)
        for i in ["pom.xml","build.gradle","build.gradle.kts"]:
            if (self.repo_path/i).exists(): score += 0.2
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in ("target","build",".git"): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix in (".java",".xml",".gradle",".properties",".yml",".yaml"): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        fw = ""
        for f in self.repo_path.rglob("*.java"):
            try:
                if "org.springframework" in f.read_text(): fw = "Spring Boot"; break
            except: pass
        return ModuleGraph(language="java", root=root, modules=modules, summary=f"Java{' — '+fw if fw else ''} project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        pom = self.repo_path / "pom.xml"
        if pom.exists():
            try:
                tree = ET.parse(pom)
                for dep in tree.findall(".//{http://maven.apache.org/POM/4.0.0}dependency/{http://maven.apache.org/POM/4.0.0}artifactId"):
                    external.add(dep.text or "")
                for dep in tree.findall(".//dependency/artifactId"):
                    external.add(dep.text or "")
            except: pass
        gradle = self.repo_path / "build.gradle"
        if gradle.exists():
            try:
                for m in re.finditer(r"""['"]([\w.\-]+:[\w.\-]+)['"]""", gradle.read_text()):
                    d = m.group(1); external.add(d.split(":")[1] if d.count(":")>1 else d.split(":")[-1])
            except: pass
        return DependencyTree(language="java", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        tables = []; orm = "unknown"
        for f in self.repo_path.rglob("*.java"):
            try:
                c = f.read_text()
                if "@Entity" in c or "@Table" in c:
                    orm = "jpa/hibernate"
                    tm = re.search(r'@Table\s*\(\s*name\s*=\s*"(\w+)"', c)
                    tn = tm.group(1) if tm else f.stem.lower()
                    tables.append(Table(name=tn, columns=[Column(name="id", type="Long", primary_key=True)]))
            except: pass
        return ERDiagram(language="java", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.java"):
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                if "Thread.sleep" in c:
                    rid += 1; ln = c[:c.index("Thread.sleep")].count("\n")+1
                    risks.append(Risk(id=f"JV-PERF-{rid:03d}", category=RiskCategory.PERFORMANCE, severity=RiskSeverity.MEDIUM, confidence=0.7, title="Thread.sleep() detected", description=f"Sync sleep in {rp}", file=rp, line=ln, evidence="Thread.sleep", recommendation="Use async alternatives."))
                todos = len(re.findall(r'//\s*(TODO|FIXME|HACK)', c))
                if todos >= 5:
                    rid += 1
                    risks.append(Risk(id=f"JV-DEBT-{rid:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.8, title=f"High TODO density ({todos})", description=f"{rp} has {todos} markers", file=rp, line=1, recommendation="Address tech debt."))
            except: pass
        return risks
