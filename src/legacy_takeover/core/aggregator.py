"""Aggregate plugin outputs into a unified intermediate representation."""
from __future__ import annotations
from dataclasses import dataclass, field

from legacy_takeover.plugins.base import (
    DependencyTree,
    ERDiagram,
    ModuleGraph,
    Risk,
)


@dataclass
class ScanResult:
    """Unified IR produced by aggregating plugin scan results."""

    repo_name: str
    repo_url: str
    depth: str = "standard"
    module_graphs: list[ModuleGraph] = field(default_factory=list)
    dependency_trees: list[DependencyTree] = field(default_factory=list)
    er_diagrams: list[ERDiagram] = field(default_factory=list)
    all_risks: list[Risk] = field(default_factory=list)
    system_context: dict = field(default_factory=dict)
    # Populated by engine.py after all plugins run.
    # Keys: "purpose", "entry_points", "config_files", "readme_summary", "api_endpoints"

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def system_purpose(self) -> str:
        """Human-readable summary of what the system does."""
        return self.system_context.get("purpose", "")

    @property
    def languages(self) -> list[str]:
        """Unique languages detected across all module graphs (deduped, stable order)."""
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
        """Deduped and sorted list of external dependencies."""
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
        """Risks sorted by score descending (severity * confidence)."""
        return sorted(self.all_risks, key=lambda r: r.risk_score, reverse=True)

    @property
    def risk_summary(self) -> dict[str, int]:
        """Count of risks per severity level."""
        counts: dict[str, int] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        for r in self.all_risks:
            key = r.severity.name.lower()
            counts[key] = counts.get(key, 0) + 1
        return counts


def aggregate_results(
    repo_name: str,
    repo_url: str,
    plugins_data: list[tuple[ModuleGraph, DependencyTree, ERDiagram, list[Risk]]],
    depth: str = "standard",
    system_context: dict | None = None,
) -> ScanResult:
    """Combine per-plugin outputs into a single ScanResult.

    Args:
        repo_name: Human-readable repository name.
        repo_url:  Repository URL or path.
        plugins_data: List of (module_graph, dependency_tree, er_diagram, risks)
                      tuples — one per plugin that ran.
        depth: Scan depth tier (quick, standard, deep).
        system_context: Optional dict with system-level context (purpose,
                        entry_points, config_files, readme_summary, api_endpoints).

    Returns:
        Populated ScanResult aggregating all plugin outputs.
    """
    result = ScanResult(
        repo_name=repo_name,
        repo_url=repo_url,
        depth=depth,
        system_context=system_context or {},
    )
    for mg, dt, ed, risks in plugins_data:
        result.module_graphs.append(mg)
        result.dependency_trees.append(dt)
        result.er_diagrams.append(ed)
        result.all_risks.extend(risks)
    return result
