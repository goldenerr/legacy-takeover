"""TypeScript/Node.js language analyzer plugin."""
from __future__ import annotations
import re, json
from pathlib import Path
from typing import ClassVar
from legacy_takeover.plugins.base import (
    LanguageAnalyzer, Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram, Risk, RiskCategory, RiskSeverity,
)

class TypeScriptAnalyzer(LanguageAnalyzer):
    name: ClassVar[str] = "typescript"
    file_patterns: ClassVar[list[str]] = ["*.ts", "*.tsx", "package.json", "tsconfig.json", "next.config.*"]

    def detect(self) -> float:
        score = 0.0
        ts_files = list(self.repo_path.rglob("*.ts")) + list(self.repo_path.rglob("*.tsx"))
        score += min(0.4, len(ts_files)*0.02)
        for i in ["package.json","tsconfig.json"]:
            if (self.repo_path/i).exists(): score += 0.3
        return min(1.0, score)

    def extract_structure(self) -> ModuleGraph:
        root = Module(name=self.repo_path.name, path=str(self.repo_path), type=ModuleType.PACKAGE)
        modules = []
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith(".") or item.name in ("node_modules",".git","dist","build",".next"): continue
            if item.is_dir(): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.PACKAGE, parent=root.name))
            elif item.suffix in (".ts",".tsx",".js",".jsx",".json"): modules.append(Module(name=item.name, path=str(item.relative_to(self.repo_path)), type=ModuleType.FILE, parent=root.name))
        fw = ""
        try:
            pkg = self.repo_path/"package.json"
            if pkg.exists():
                data = json.loads(pkg.read_text())
                deps = {**data.get("dependencies",{}), **data.get("devDependencies",{})}
                if "next" in deps: fw = "Next.js"
                elif "react" in deps: fw = "React"
                elif "express" in deps: fw = "Express"
                elif "nestjs" in deps or "@nestjs/core" in deps: fw = "NestJS"
        except: pass
        return ModuleGraph(language="typescript", root=root, modules=modules, summary=f"TypeScript{' — '+fw if fw else ''} project with {len(modules)} modules")

    def extract_dependencies(self) -> DependencyTree:
        external = set()
        pkg = self.repo_path/"package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                external.update(data.get("dependencies",{}).keys())
            except: pass
        return DependencyTree(language="typescript", nodes=[], edges=[], external_deps=sorted(external), summary=f"{len(external)} external deps")

    def extract_db_schema(self) -> ERDiagram:
        tables = []; orm = "unknown"
        for f in self.repo_path.rglob("*.ts"):
            try:
                c = f.read_text()
                if "prisma" in c.lower(): orm = "prisma"
                elif "typeorm" in c.lower(): orm = "typeorm"
                elif "sequelize" in c.lower(): orm = "sequelize"
            except: pass
        schema = self.repo_path/"prisma"/"schema.prisma"
        if schema.exists():
            try:
                for m in re.finditer(r'model\s+(\w+)\s*\{', schema.read_text()):
                    tables.append(Table(name=m.group(1).lower(), columns=[Column(name="id", type="String", primary_key=True)]))
            except: pass
        return ERDiagram(language="typescript", tables=tables, orm_framework=orm, summary=f"{len(tables)} tables")

    def assess_risks(self) -> list[Risk]:
        risks = []; rid = 0
        for f in self.repo_path.rglob("*.ts"):
            if "node_modules" in str(f): continue
            try:
                c = f.read_text(); rp = str(f.relative_to(self.repo_path))
                for m in re.finditer(r'(?:API_KEY|SECRET|PASSWORD|TOKEN)\s*[:=]\s*["\'][\w\-]{8,}["\']', c):
                    rid += 1; ln = c[:m.start()].count("\n")+1
                    risks.append(Risk(id=f"TS-SEC-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9, title="Hardcoded secret", description=f"Secret in {rp}", file=rp, line=ln, evidence=m.group()[:80], recommendation="Use environment variables."))
                if "console.log" in c or "console.error" in c:
                    count = len(re.findall(r'console\.(log|error|warn)', c))
                    if count >= 10:
                        rid += 1
                        risks.append(Risk(id=f"TS-DEBT-{rid:03d}", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.LOW, confidence=0.7, title=f"Excessive console logging ({count})", description=f"{rp} has {count} console calls", file=rp, line=1, recommendation="Replace with proper logger."))
            except: pass
        return risks
