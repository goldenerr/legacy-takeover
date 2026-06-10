"""Report renderer: MD docs, Mermaid diagrams, HTML index."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from legacy_takeover.core.aggregator import ScanResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"

def render_report(result: ScanResult, output_dir: Path, repo_url: str = "") -> None:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = output_dir / f"legacy-report-{result.repo_name}-{ts}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagrams").mkdir(exist_ok=True)
    (out / "data").mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=select_autoescape(["html"]))
    ctx = _build_context(result, repo_url or result.repo_url)

    templates = {
        "system_manual.md.j2": "SYSTEM_MANUAL.md",
        "architecture.md.j2": "ARCHITECTURE.md",
        "api_endpoints.md.j2": "API_ENDPOINTS.md",
        "database.md.j2": "DATABASE.md",
        "dependencies.md.j2": "DEPENDENCIES.md",
        "risk_report.md.j2": "RISK_REPORT.md",
        "index.html.j2": "index.html",
    }
    for tmpl_name, out_name in templates.items():
        tmpl = env.get_template(tmpl_name)
        (out / out_name).write_text(tmpl.render(**ctx))

    (out / "diagrams" / "architecture.mmd").write_text(_build_architecture_mermaid(result))
    (out / "diagrams" / "er_diagram.mmd").write_text(_build_er_mermaid(result))
    (out / "diagrams" / "dependency_graph.mmd").write_text(_build_dependency_mermaid(result))

    (out / "data" / "modules.json").write_text(json.dumps(
        [mg.model_dump() for mg in result.module_graphs], indent=2, default=str))
    (out / "data" / "dependencies.json").write_text(json.dumps(
        [dt.model_dump() for dt in result.dependency_trees], indent=2, default=str))
    (out / "data" / "risks.json").write_text(json.dumps(
        [r.model_dump() for r in result.all_risks], indent=2, default=str))
    print(f"✅ Report generated: {out}")

def _build_context(result: ScanResult, repo_url: str) -> dict:
    has_dep_edges = any(dt.edges for dt in result.dependency_trees)
    return {
        "repo_name": result.repo_name, "repo_url": repo_url, "depth": result.depth,
        "generated_at": datetime.now().isoformat(), "languages": result.languages,
        "module_graphs": result.module_graphs, "dependency_trees": result.dependency_trees,
        "er_diagrams": result.er_diagrams, "risks": result.top_risks,
        "risk_summary": result.risk_summary, "total_modules": result.total_modules,
        "total_deps": result.total_dependencies, "total_tables": result.total_tables,
        "total_risks": result.total_risks, "external_deps": result.external_deps,
        "has_dep_edges": has_dep_edges,
        "system_context": result.system_context,
        "system_purpose": result.system_purpose,
    }

def _build_architecture_mermaid(result: ScanResult) -> str:
    lines = ["graph TD"]
    for mg in result.module_graphs:
        for m in mg.modules:
            safe = m.name.replace("-","_").replace(".","_")
            lines.append(f"    {safe}[{m.name}]")
    if len(lines) == 1: lines.append('    A["No modules detected"]')
    return "\n".join(lines)

def _build_er_mermaid(result: ScanResult) -> str:
    lines = ["erDiagram"]
    for ed in result.er_diagrams:
        for t in ed.tables:
            cols = [f"        {c.type} {c.name}{' PK' if c.primary_key else ''}" for c in t.columns]
            if cols:
                lines.append(f"    {t.name} {{")
                lines.extend(cols); lines.append("    }")
    if len(lines) == 1: lines.append('    NO_TABLES { string note "No tables found" }')
    return "\n".join(lines)

def _build_dependency_mermaid(result: ScanResult) -> str:
    lines = ["graph LR"]
    for dt in result.dependency_trees:
        for edge in dt.edges:
            f = edge.from_module.replace("-","_").replace(".","_")
            t = edge.to_module.replace("-","_").replace(".","_")
            lines.append(f"    {f} -->|{edge.type.value}| {t}")
    if len(lines) == 1: lines.append('    A["No dependencies detected"]')
    return "\n".join(lines)
