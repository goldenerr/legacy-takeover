import pytest
from pathlib import Path
from legacy_takeover.risk.engine import RiskEngine, CustomRule
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity

@pytest.fixture
def engine():
    return RiskEngine()

@pytest.fixture
def code_dir(tmp_path):
    (tmp_path / "app.py").write_text("API_KEY='secret123'\nTODO: fix later\n")
    (tmp_path / "Helper.java").write_text("Thread.sleep(1000);\n")
    return tmp_path

class TestRiskEngine:
    def test_empty_no_custom_rules(self, engine, code_dir):
        risks = engine.run(code_dir)
        assert len(risks) == 0

    def test_custom_rule_finds_match(self, engine, code_dir):
        rules = [CustomRule(
            pattern="API_KEY", file_glob="*.py",
            category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH,
            message="Secret found", recommendation="Use env vars"
        )]
        risks = engine.run(code_dir, custom_rules=rules)
        assert len(risks) == 1
        assert risks[0].category == RiskCategory.SECURITY
        assert risks[0].severity == RiskSeverity.HIGH
        assert "app.py" in risks[0].file

    def test_custom_rule_java_glob(self, engine, code_dir):
        rules = [CustomRule(
            pattern=r"Thread\.sleep", file_glob="*.java",
            category=RiskCategory.PERFORMANCE, severity=RiskSeverity.MEDIUM,
            message="No sleep", recommendation="Async"
        )]
        risks = engine.run(code_dir, custom_rules=rules)
        assert len(risks) == 1
        assert risks[0].category == RiskCategory.PERFORMANCE

    def test_risks_sorted_desc(self, engine, code_dir):
        rules = [
            CustomRule(pattern="TODO", file_glob="*.py",
                       category=RiskCategory.TECH_DEBT, severity=RiskSeverity.LOW,
                       message="x", recommendation=""),
            CustomRule(pattern="API_KEY", file_glob="*.py",
                       category=RiskCategory.SECURITY, severity=RiskSeverity.CRITICAL,
                       message="x", recommendation=""),
        ]
        risks = engine.run(code_dir, custom_rules=rules)
        # CRITICAL (10) * 0.85 = 8.5 > LOW (4) * 0.85 = 3.4
        assert risks[0].category == RiskCategory.SECURITY

    def test_pattern_no_match(self, engine, code_dir):
        rules = [CustomRule(
            pattern="NONEXISTENT", file_glob="*.py",
            category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH,
            message="x", recommendation=""
        )]
        assert engine.run(code_dir, custom_rules=rules) == []

    def test_risk_score_calculation(self, engine, code_dir):
        rules = [CustomRule(
            pattern="API_KEY", file_glob="*.py",
            category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH,
            message="x", recommendation=""
        )]
        risks = engine.run(code_dir, custom_rules=rules)
        # HIGH = 8, confidence = 0.85, risk_score = 8 * 0.85 = 6.8
        assert risks[0].risk_score == pytest.approx(6.8)
