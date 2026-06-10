"""CLI entry point for legacy-scan."""
from __future__ import annotations
import sys
from pathlib import Path
import click
from legacy_takeover.core.engine import run_scan
from legacy_takeover.report.renderer import render_report

@click.command()
@click.argument("repo", type=str)
@click.option("--depth", "-d", type=click.Choice(["quick","standard","deep"]), default="standard")
@click.option("--output", "-o", type=click.Path(), default=".", help="Output directory for reports")
@click.option("--no-report", is_flag=True, help="Only analyze, skip report generation")
@click.version_option(version="0.1.0", prog_name="legacy-scan")
def main(repo: str, depth: str, output: str, no_report: bool) -> None:
    """Scan a Git repository and generate a system takeover manual."""
    click.echo(f"🔍 Scanning {repo} (depth={depth})...")
    try:
        result = run_scan(repo_url=repo, depth=depth)
    except Exception as e:
        click.echo(f"❌ Scan failed: {e}", err=True)
        sys.exit(1)
    click.echo(f"\n📊 {result.repo_name}")
    click.echo(f"   Languages: {', '.join(result.languages) or 'none'}")
    click.echo(f"   Modules: {result.total_modules} | Deps: {result.total_dependencies} | Tables: {result.total_tables} | Risks: {result.total_risks}")
    if result.top_risks:
        click.echo(f"   🔴 Critical: {result.risk_summary['critical']}  🟠 High: {result.risk_summary['high']}  🟡 Medium: {result.risk_summary['medium']}")
    if not no_report:
        try: render_report(result, Path(output), repo_url=repo)
        except Exception as e: click.echo(f"⚠️  Report failed: {e}", err=True)
    click.echo("✅ Done.")

if __name__ == "__main__":
    main()
