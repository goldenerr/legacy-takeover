from pathlib import Path
from legacy_takeover.risk.loader import load_custom_rules
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity

class TestLoadCustomRules:
    def test_load_yaml_rules(self, tmp_path):
        config = tmp_path / ".legacy-takeover.yaml"
        config.write_text("""custom_rules:
  - pattern: "Thread\\\\.sleep"
    file_glob: "*.java"
    category: performance
    severity: 4
    message: "Avoid Thread.sleep()"
    recommendation: "Use async"
  - pattern: "console\\\\.log"
    file_glob: "*.ts"
    category: tech_debt
    severity: 2
    message: "Remove debug log"
""")
        rules = load_custom_rules(tmp_path)
        assert len(rules) == 2
        assert rules[0].category == RiskCategory.PERFORMANCE
        assert rules[0].severity == RiskSeverity.LOW

    def test_no_config_returns_empty(self, tmp_path):
        assert load_custom_rules(tmp_path) == []

    def test_invalid_yaml_returns_empty(self, tmp_path):
        (tmp_path / ".legacy-takeover.yaml").write_text("::: invalid yaml :::")
        assert load_custom_rules(tmp_path) == []

    def test_missing_fields_skipped(self, tmp_path):
        (tmp_path / ".legacy-takeover.yaml").write_text("""custom_rules:
  - pattern: "x"
    category: security
    severity: 8
    # missing message is OK
""")
        rules = load_custom_rules(tmp_path)
        assert len(rules) == 1
