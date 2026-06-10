"""C++ language analyzer plugin."""
from __future__ import annotations
import re
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class CppAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "cpp"
    file_patterns: ClassVar[list[str]] = ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.hh", "*.hxx", "CMakeLists.txt", "*.cmake"]

    def detect(self) -> float:
        score = 0.0
        cpp_files = list(self.repo_path.rglob("*.cpp")) + list(self.repo_path.rglob("*.cc")) + list(self.repo_path.rglob("*.cxx"))
        score += min(0.5, len(cpp_files)*0.03)
        if (self.repo_path/"CMakeLists.txt").exists() or list(self.repo_path.rglob("*.cmake")): score += 0.3
        if list(self.repo_path.rglob("*.hpp")): score += 0.2
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in (".git","build","cmake-build-*"): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix in (".cpp",".cc",".cxx",".hpp",".hh",".hxx",".cmake"): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        return ModuleGraph(language="cpp", root=root, modules=modules, summary=f"C++ project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        for f in list(self.repo_path.rglob("*.cpp")) + list(self.repo_path.rglob("*.cc")) + list(self.repo_path.rglob("*.hpp")) + list(self.repo_path.rglob("*.h")):
            try:
                for m in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', f.read_text()):
                    inc = m.group(1)
                    if not inc.endswith(".h") and not inc.endswith(".hpp"):
                        external.add(inc)
            except: pass
        cmake = self.repo_path/"CMakeLists.txt"
        if cmake.exists():
            try:
                for m in re.finditer(r'find_package\((\w+)', cmake.read_text()):
                    external.add(m.group(1))
            except: pass
        return DependencyTree(language="cpp", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        return ERDiagram(language="cpp", tables=[], summary="N/A (C++ typically no ORM)")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in list(self.repo_path.rglob("*.cpp")) + list(self.repo_path.rglob("*.hpp")):
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                if "new " in c and "delete " not in c:
                    rid += 1
                    risks.append(Risk(id=f"CPP-MEM-{rid:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.6, title="new without visible delete", description=f"Potential memory leak in {rp}", file=rp, line=1, recommendation="Use smart pointers (unique_ptr, shared_ptr)."))
                if "reinterpret_cast" in c:
                    rid += 1; ln = c[:c.index("reinterpret_cast")].count("\n")+1
                    risks.append(Risk(id=f"CPP-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.MEDIUM, confidence=0.75, title="reinterpret_cast used", description=f"Type-unsafe cast in {rp}", file=rp, line=ln, evidence="reinterpret_cast", recommendation="Prefer static_cast or dynamic_cast."))
            except: pass
        return risks
