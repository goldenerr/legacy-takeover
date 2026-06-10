"""Tests for ScanResult dataclass and aggregate_results()."""
from legacy_takeover.core.aggregator import ScanResult, aggregate_results
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
)


class TestScanResult:
    def test_empty_result(self):
        r = ScanResult(repo_name="test", repo_url="http://x", depth="quick")
        assert r.languages == []
        assert r.total_modules == 0
        assert r.total_dependencies == 0
        assert r.total_tables == 0
        assert r.total_risks == 0
        assert r.top_risks == []
        assert r.system_context == {}
        assert r.system_purpose == ""

    def test_system_context_field(self):
        """system_context is populated and system_purpose property works."""
        ctx = {
            "purpose": "Backup data management service",
            "readme_summary": "A Spring Boot service for managing backup data.",
            "entry_points": ["BackupController", "DataService"],
            "api_endpoints": [
                {"module": "BackupController", "method": "GET", "path": "/api/backups"},
            ],
            "config_files": ["application.yml", "pom.xml"],
        }
        r = ScanResult(
            repo_name="test", repo_url="http://x",
            system_context=ctx,
        )
        assert r.system_context == ctx
        assert r.system_purpose == "Backup data management service"
        assert r.system_context["entry_points"] == ["BackupController", "DataService"]
        assert len(r.system_context["api_endpoints"]) == 1

    def test_system_purpose_defaults_to_empty(self):
        r = ScanResult(repo_name="test", repo_url="http://x")
        assert r.system_purpose == ""

    def test_risk_summary_correct_counts(self):
        risks = [
            Risk(id="R1", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.9,
                 title="a", description="a"),
            Risk(id="R2", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.8,
                 title="b", description="b"),
            Risk(id="R3", category=RiskCategory.BUS_FACTOR, severity=RiskSeverity.LOW, confidence=0.5,
                 title="c", description="c"),
            Risk(id="R4", category=RiskCategory.SECURITY, severity=RiskSeverity.CRITICAL, confidence=1.0,
                 title="d", description="d"),
            Risk(id="R5", category=RiskCategory.PERFORMANCE, severity=RiskSeverity.INFO, confidence=0.3,
                 title="e", description="e"),
        ]
        r = ScanResult(repo_name="x", repo_url="y")
        r.all_risks = risks
        summary = r.risk_summary
        assert summary == {"critical": 1, "high": 1, "medium": 1, "low": 1, "info": 1}


class TestAggregateResults:
    def test_single_plugin(self):
        graph = ModuleGraph(
            language="python",
            root=Module(name="root", path="/", type=ModuleType.PACKAGE),
            modules=[
                Module(name="api", path="/api", type=ModuleType.PACKAGE),
                Module(name="db", path="/db", type=ModuleType.PACKAGE),
            ],
            summary="A Python app",
        )
        deps = DependencyTree(
            language="python", nodes=["api", "db"],
            edges=[Dependency(from_module="api", to_module="db", type=DependencyType.IMPORT)],
            external_deps=["fastapi", "sqlalchemy"],
        )
        db = ERDiagram(language="python", tables=[])
        risks = [
            Risk(id="R001", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH,
                 confidence=0.9, title="Hardcoded key", description="Secret", file="config.py")
        ]
        result = aggregate_results("myapp", "git@x", [(graph, deps, db, risks)])
        assert result.repo_name == "myapp"
        assert result.total_modules == 2
        assert result.total_dependencies == 1
        assert len(result.external_deps) == 2
        assert result.total_risks == 1
        assert result.top_risks[0].id == "R001"

    def test_risks_sorted_by_score_desc(self):
        risks = [
            Risk(id="R1", category=RiskCategory.SECURITY, severity=RiskSeverity.LOW, confidence=0.5,
                 title="a", description="a"),
            Risk(id="R2", category=RiskCategory.SECURITY, severity=RiskSeverity.CRITICAL, confidence=1.0,
                 title="b", description="b"),
            Risk(id="R3", category=RiskCategory.TECH_DEBT, severity=RiskSeverity.MEDIUM, confidence=0.8,
                 title="c", description="c"),
        ]
        result = aggregate_results("x", "y", [(
            ModuleGraph(language="py", root=Module(name="r", path="/"), modules=[]),
            DependencyTree(language="py", nodes=[], edges=[]),
            ERDiagram(language="py", tables=[]),
            risks,
        )])
        assert result.top_risks[0].id == "R2"   # 10.0
        assert result.top_risks[1].id == "R3"   # 4.8
        assert result.top_risks[2].id == "R1"   # 2.0

    def test_multiple_plugins_language_dedup(self):
        g1 = ModuleGraph(language="python", root=Module(name="r1", path="/"),
                         modules=[Module(name="m1", path="/m1")])
        g2 = ModuleGraph(language="python", root=Module(name="r2", path="/"),
                         modules=[Module(name="m2", path="/m2")])
        g3 = ModuleGraph(language="java", root=Module(name="r3", path="/"),
                         modules=[Module(name="m3", path="/m3")])
        result = aggregate_results("x", "y", [
            (g1, DependencyTree(language="py", nodes=[], edges=[]), ERDiagram(language="py", tables=[]), []),
            (g2, DependencyTree(language="py", nodes=[], edges=[]), ERDiagram(language="py", tables=[]), []),
            (g3, DependencyTree(language="java", nodes=[], edges=[]), ERDiagram(language="java", tables=[]), []),
        ])
        assert result.languages == ["python", "java"]
        assert result.total_modules == 3

    def test_external_deps_dedup_and_sorted(self):
        dt1 = DependencyTree(language="py", nodes=[], edges=[],
                             external_deps=["flask", "sqlalchemy"])
        dt2 = DependencyTree(language="py", nodes=[], edges=[],
                             external_deps=["fastapi", "sqlalchemy", "pydantic"])
        result = aggregate_results("x", "y", [
            (ModuleGraph(language="py", root=Module(name="r", path="/"), modules=[]), dt1,
             ERDiagram(language="py", tables=[]), []),
            (ModuleGraph(language="py", root=Module(name="r2", path="/"), modules=[]), dt2,
             ERDiagram(language="py", tables=[]), []),
        ])
        assert result.external_deps == ["fastapi", "flask", "pydantic", "sqlalchemy"]
