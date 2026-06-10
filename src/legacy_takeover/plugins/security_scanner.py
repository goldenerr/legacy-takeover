"""Static security vulnerability scanner."""
from __future__ import annotations
import re
from pathlib import Path
from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity

SQL_INJECTION_PATTERNS = [
    (r'(?<!Prepared)Statement\s+\w+\s*=', 'java.sql.Statement instead of PreparedStatement'),
    (r'createStatement\(\)', 'Statement creation without parameterization'),
]
SSRF_PATTERNS = [
    (r'RestTemplate.*\.getForEntity\s*\([^)]*\+\s*[^)]*\)', 'User input in HTTP URL'),
    (r'URLConnection.*\.openConnection\s*\(.*url', 'User-controlled URL connection'),
]
XSS_PATTERNS = [
    (r'@ResponseBody.*\n.*return.*request\.getParameter', 'Unescaped request param in response'),
]

def scan_vulnerabilities(repo_path: Path) -> list[Risk]:
    risks: list[Risk] = []; rid = 0
    for f in repo_path.rglob("*.java"):
        try:
            content = f.read_text(); rp = str(f.relative_to(repo_path))
            for pattern, desc in SQL_INJECTION_PATTERNS:
                if re.search(pattern, content):
                    rid += 1; risks.append(Risk(id=f"SEC-SQL-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.75, title=f"Potential SQL injection: {desc}", description=f"Found in {rp}", file=rp, recommendation="Use PreparedStatement or JPA parameterized queries."))
            for pattern, desc in SSRF_PATTERNS:
                if re.search(pattern, content):
                    rid += 1; risks.append(Risk(id=f"SEC-SSRF-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.HIGH, confidence=0.7, title=f"Potential SSRF: {desc}", description=f"Found in {rp}", file=rp, recommendation="Validate and whitelist outgoing URLs."))
            if "csrf().disable()" in content:
                rid += 1; risks.append(Risk(id=f"SEC-CSRF-{rid:03d}", category=RiskCategory.SECURITY, severity=RiskSeverity.MEDIUM, confidence=0.9, title="CSRF protection disabled", description=f"Found in {rp}", file=rp, recommendation="Re-enable CSRF unless absolutely necessary."))
        except Exception:
            pass
    return risks
