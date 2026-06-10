import pytest
from pathlib import Path
from legacy_takeover.report.renderer import render_report
from legacy_takeover.core.aggregator import ScanResult
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    ERDiagram, Risk, RiskCategory, RiskSeverity,
)


@pytest.fixture
def scan_result():
    mg = ModuleGraph(language="python", root=Module(name="test", path="/test"),
        modules=[Module(name="api", path="api", type=ModuleType.PACKAGE)])
    dt = DependencyTree(language="python", nodes=["api"], edges=[], external_deps=["click"])
    ed = ERDiagram(language="python", tables=[])
    risks = [Risk(id="R01", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH,
                  confidence=0.9, title="Test", description="Test risk")]
    result = ScanResult(repo_name="test", repo_url="git@x", depth="standard")
    result.module_graphs = [mg]; result.dependency_trees = [dt]
    result.er_diagrams = [ed]; result.all_risks = risks
    return result


class TestRenderReport:
    def test_creates_output_dir(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        subdirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(subdirs) >= 1

    def test_generates_system_manual(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        report_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        manual = report_dirs[0] / "SYSTEM_MANUAL.md"
        assert manual.exists()
        assert "# test" in manual.read_text()

    def test_generates_architecture_md(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        report_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        arch = report_dirs[0] / "ARCHITECTURE.md"
        assert arch.exists()
        assert "mermaid" in arch.read_text()

    def test_generates_html_index(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        report_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        html = report_dirs[0] / "index.html"
        assert html.exists()
        assert "<!DOCTYPE html>" in html.read_text()

    def test_generates_mermaid_files(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        report_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        diagrams = report_dirs[0] / "diagrams"
        assert (diagrams / "architecture.mmd").exists()
        assert (diagrams / "er_diagram.mmd").exists()
        assert (diagrams / "dependency_graph.mmd").exists()

    def test_generates_data_json(self, tmp_path, scan_result):
        render_report(scan_result, tmp_path)
        report_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        data = report_dirs[0] / "data"
        assert (data / "modules.json").exists()
        assert (data / "dependencies.json").exists()
        assert (data / "risks.json").exists()
