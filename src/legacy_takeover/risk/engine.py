"""Risk matching engine — built-in + custom rules."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity

@dataclass
class CustomRule:
    pattern: str
    file_glob: str
    category: RiskCategory
    severity: RiskSeverity
    message: str
    recommendation: str = ""

class RiskEngine:
    def run(self, repo_path: Path, custom_rules: list[CustomRule] | None = None) -> list[Risk]:
        all_risks: list[Risk] = []
        risk_id = 0
        for rule in (custom_rules or []):
            for file_path in repo_path.rglob(rule.file_glob):
                if ".git" in file_path.parts:
                    continue
                try:
                    content = file_path.read_text()
                except Exception:
                    continue
                for match in re.finditer(rule.pattern, content):
                    risk_id += 1
                    line = content[:match.start()].count("\n") + 1 if "\n" in content else 1
                    all_risks.append(Risk(
                        id=f"CUST-{risk_id:03d}",
                        category=rule.category,
                        severity=rule.severity,
                        confidence=0.85,
                        title=rule.message,
                        description=f"Custom rule match in {file_path.relative_to(repo_path)}",
                        file=str(file_path.relative_to(repo_path)),
                        line=line,
                        evidence=match.group()[:80],
                        recommendation=rule.recommendation,
                    ))
        return sorted(all_risks, key=lambda r: r.risk_score, reverse=True)
