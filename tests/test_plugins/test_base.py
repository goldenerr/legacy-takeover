import pytest
from legacy_takeover.plugins.base import (
    Module, ModuleGraph, ModuleType,
    Dependency, DependencyTree, DependencyType,
    Table, Column, ERDiagram,
    Risk, RiskCategory, RiskSeverity,
    LanguageAnalyzer,
)


class TestModule:
    def test_module_creation(self):
        m = Module(name="auth", path="/src/auth", type=ModuleType.PACKAGE)
        assert m.name == "auth"
        assert m.type == ModuleType.PACKAGE
        assert m.children == []

    def test_module_add_child(self):
        parent = Module(name="api", path="/src/api", type=ModuleType.PACKAGE)
        child = Module(name="handlers.py", path="/src/api/handlers.py", type=ModuleType.FILE)
        parent.children.append(child)
        assert len(parent.children) == 1


class TestDependency:
    def test_dependency_creation(self):
        d = Dependency(from_module="api", to_module="db", type=DependencyType.IMPORT)
        assert d.from_module == "api"
        assert d.to_module == "db"


class TestRisk:
    def test_risk_creation(self):
        r = Risk(
            id="R001", category=RiskCategory.SECURITY,
            severity=RiskSeverity.HIGH, confidence=0.9,
            title="Hardcoded secret", description="Found API key",
            file="config.py", line=42, evidence="API_KEY='***'",
        )
        assert r.severity.value == 8
        assert r.risk_score == pytest.approx(7.2)


class TestLanguageAnalyzer:
    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LanguageAnalyzer()

    def test_concrete_must_implement_all(self):
        class BadAnalyzer(LanguageAnalyzer):
            name = "bad"
            file_patterns = ["*.bad"]

        with pytest.raises(TypeError):
            BadAnalyzer()
