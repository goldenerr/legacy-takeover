"""Load custom risk rules from .legacy-takeover.yaml."""
from __future__ import annotations
from pathlib import Path
import yaml
from legacy_takeover.risk.engine import CustomRule
from legacy_takeover.plugins.base import RiskCategory, RiskSeverity

def load_custom_rules(repo_path: Path) -> list[CustomRule]:
    config_path = repo_path / ".legacy-takeover.yaml"
    if not config_path.exists():
        return []
    try:
        data = yaml.safe_load(config_path.read_text())
    except Exception:
        return []
    rules: list[CustomRule] = []
    for item in data.get("custom_rules", []):
        try:
            rules.append(CustomRule(
                pattern=item["pattern"],
                file_glob=item.get("file_glob", "*"),
                category=RiskCategory(item["category"]),
                severity=RiskSeverity(item["severity"]),
                message=item.get("message", item["pattern"]),
                recommendation=item.get("recommendation", ""),
            ))
        except (KeyError, ValueError):
            continue
    return rules
