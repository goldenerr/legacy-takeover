"""C language analyzer plugin."""
from __future__ import annotations
import re
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class CAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "c"
    file_patterns: ClassVar[list[str]] = ["*.c", "*.h", "Makefile", "CMakeLists.txt"]

    def detect(self) -> float:
        score = 0.0
        c_files = list(self.repo_path.rglob("*.c")) + list(self.repo_path.rglob("*.h"))
        score += min(0.6, len(c_files)*0.04)
        if (self.repo_path/"Makefile").exists() or (self.repo_path/"CMakeLists.txt").exists(): score += 0.4
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in (".git","build","obj"): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix in (".c",".h",".o"): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        return ModuleGraph(language="c", root=root, modules=modules, summary=f"C project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        for f in self.repo_path.rglob("*.c"):
            try:
                for m in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', f.read_text()):
                    external.add(m.group(1))
            except: pass
        return DependencyTree(language="c", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} includes")

    def extract_db_schema(self) -> ERDiagram:
        return ERDiagram(language="c", tables=[], summary="N/A (C typically no ORM)")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.c"):
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                if "strcpy" in c:
                    rid += 1; ln = c[:c.index("strcpy")].count("\n")+1
                    risks.append(Risk(id=f"CC-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.85, title="strcpy() used (buffer overflow risk)", description=f"Unsafe strcpy in {rp}", file=rp, line=ln, evidence="strcpy", recommendation="Use strncpy or strlcpy."))
                if "malloc" in c and "free" not in c:
                    for m in re.finditer(r'malloc\(', c):
                        rid += 1; ln = c[:m.start()].count("\n")+1
                        risks.append(Risk(id=f"CC-MEM-{rid:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.6, title="malloc() without visible free()", description=f"Potential memory leak in {rp}", file=rp, line=ln, recommendation="Ensure every malloc has corresponding free."))
                        break
            except: pass
        return risks
