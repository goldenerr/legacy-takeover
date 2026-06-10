"""Core pipeline: clone → detect → analyze → aggregate."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Type

from legacy_takeover.core.aggregator import ScanResult, aggregate_results
from legacy_takeover.core.detector import detect_languages
from legacy_takeover.core.git import cleanup_repo, clone_repo
from legacy_takeover.plugins.base import LanguageAnalyzer

# ── Depth tier → git clone depth mapping ────────────────────────────────────
_DEPTH_MAP: dict[str, int] = {
    "quick": 1,
    "standard": 50,
    "deep": 0,  # 0 = full history
}


def run_scan(
    repo_url: str,
    depth: str = "standard",
    plugins: list[Type[LanguageAnalyzer]] | None = None,
    output_dir: str | None = None,
) -> ScanResult:
    """Orchestrate a full scan pipeline: clone → detect → analyze → aggregate.

    Args:
        repo_url:  Git URL or local path to the repository.
        depth:     Scan depth tier (\"quick\", \"standard\", or \"deep\").
        plugins:   LanguageAnalyzer subclasses to use.  Auto-discovered via
                   entry-points when omitted.
        output_dir:If given, render a report after aggregation.

    Returns:
        Aggregated ScanResult.
    """
    if plugins is None:
        plugins = _discover_plugins()

    clone_depth = _DEPTH_MAP.get(depth, 50)
    repo_name = _extract_repo_name(repo_url)

    with tempfile.TemporaryDirectory(prefix="legacy_scan_") as tmp:
        repo_path = Path(tmp) / "repo"
        try:
            clone_repo(repo_url, str(repo_path), depth=clone_depth)

            # Instantiate all plugins, then let the detector decide which match.
            plugin_instances = [
                p(repo_path=repo_path, depth=depth) for p in plugins
            ]
            matched = detect_languages(repo_path, plugin_instances)

            # Run each matched plugin's analysis steps.
            plugins_data: list = []
            for plugin in matched:
                mg = plugin.extract_structure()
                dt = plugin.extract_dependencies()
                ed = plugin.extract_db_schema()
                risks = plugin.assess_risks()
                plugins_data.append((mg, dt, ed, risks))

            # Build system-level context from README, plugins, and module metadata.
            system_ctx: dict[str, object] = {}

            # 1. Read README.md first paragraph.
            readme_candidates = list(repo_path.glob("README*"))
            if readme_candidates:
                try:
                    text = readme_candidates[0].read_text()
                    first_para = text.split("\n\n")[0].strip().replace("# ", "")
                    system_ctx["readme_summary"] = first_para[:500]
                except Exception:
                    pass

            # 2. Guess purpose from readme summary + plugin entry points.
            purpose_parts: list[str] = []
            readme_summary = system_ctx.get("readme_summary", "")
            if readme_summary:
                purpose_parts.append(str(readme_summary)[:200])
            for plugin in matched:
                if hasattr(plugin, "_entry_points") and plugin._entry_points:
                    purpose_parts.append(
                        "Entry: " + ", ".join(str(ep) for ep in plugin._entry_points[:3])
                    )
            system_ctx["purpose"] = " | ".join(purpose_parts) if purpose_parts else "Unknown"

            # 3. Collect API endpoints from module metadata.
            endpoints: list[dict] = []
            ep_names: list[str] = []
            for mg, _dt, _ed, _risks in plugins_data:
                for m in mg.modules:
                    meta_endpoints = m.metadata.get("endpoints", [])
                    if meta_endpoints:
                        for ep in meta_endpoints:
                            endpoints.append({"module": m.name, **ep})
                    # Also collect entry point names from module annotations.
                    annotations = m.metadata.get("annotations", [])
                    for ann in annotations:
                        if ann in (
                            "RestController", "Controller", "RequestMapping",
                            "GetMapping", "PostMapping", "PutMapping", "DeleteMapping",
                            "PatchMapping", "app.route", "route", "Flask",
                        ) or ann.lower().endswith("controller"):
                            ep_names.append(m.name)
            system_ctx["api_endpoints"] = endpoints[:50]
            system_ctx["entry_points"] = ep_names[:20]

            # 4. Collect config files.
            config_patterns = {
                "*.yml", "*.yaml", "*.toml", "*.ini", "*.cfg", "*.conf",
                "*.properties", "*.env", "*.json",
            }
            config_files: list[str] = []
            for pat in config_patterns:
                for cf in repo_path.glob(pat):
                    # Only include recognized config filenames.
                    if cf.name.lower() in {
                        "application.yml", "application.yaml", "application.properties",
                        "application.toml", "settings.py", "config.py", "pyproject.toml",
                        "cargo.toml", "package.json", "tsconfig.json", "go.mod",
                        "pom.xml", "build.gradle", "build.gradle.kts",
                        "docker-compose.yml", "docker-compose.yaml",
                        ".env", ".env.example", "makefile", "cmakelists.txt",
                    } or cf.name.endswith(".config.js") or cf.name.endswith(".config.ts"):
                        config_files.append(cf.name)
            system_ctx["config_files"] = sorted(set(config_files))[:30]

            result = aggregate_results(
                repo_name, repo_url, plugins_data, depth, system_context=system_ctx,
            )

            # Optional report rendering (soft dependency).
            if output_dir:
                try:
                    from legacy_takeover.report.renderer import render_report  # type: ignore[import-untyped]

                    render_report(result, Path(output_dir))
                except ImportError:
                    pass  # Report renderer not installed — that's fine.

            return result
        finally:
            cleanup_repo(repo_path)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_repo_name(url: str) -> str:
    """Extract a human-readable repo name from a URL or local path."""
    path = Path(url)
    if path.exists():
        return path.name
    # URL case: strip trailing slash and optional .git suffix.
    name = url.rstrip("/").split("/")[-1]
    return name.replace(".git", "")


# Cache for plugin discovery so entry-points are loaded only once.
_PLUGIN_CACHE: list[Type[LanguageAnalyzer]] | None = None


def _discover_plugins() -> list[Type[LanguageAnalyzer]]:
    """Discover LanguageAnalyzer subclasses via ``legacy_takeover.analyzers``
    entry-points.  Results are cached after first call."""
    global _PLUGIN_CACHE
    if _PLUGIN_CACHE is not None:
        return _PLUGIN_CACHE

    from importlib.metadata import entry_points

    discovered: list[Type[LanguageAnalyzer]] = []
    try:
        eps = entry_points(group="legacy_takeover.analyzers")
    except TypeError:
        # Python < 3.12 needs the dict-style call.
        eps = entry_points().get("legacy_takeover.analyzers", [])

    for ep in eps:
        cls = ep.load()
        discovered.append(cls)

    _PLUGIN_CACHE = discovered
    return discovered
