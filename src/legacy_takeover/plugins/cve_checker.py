"""CVE dependency checker — matches Maven dependencies against known vulnerabilities."""
from __future__ import annotations
import re
from pathlib import Path
from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity

KNOWN_CVES = {
    "log4j-core": {"max_safe": "2.17.0", "cve": "CVE-2021-44228", "severity": "CRITICAL"},
    "log4j-api": {"max_safe": "2.17.0", "cve": "CVE-2021-44228", "severity": "CRITICAL"},
    "jackson-databind": {"max_safe": "2.13.4", "cve": "CVE-2022-42003", "severity": "HIGH"},
    "spring-beans": {"max_safe": "5.3.18", "cve": "CVE-2022-22965", "severity": "CRITICAL"},
    "spring-core": {"max_safe": "5.3.18", "cve": "CVE-2022-22965", "severity": "CRITICAL"},
    "fastjson": {"max_safe": "1.2.83", "cve": "CVE-2022-25845", "severity": "HIGH"},
    "shiro-core": {"max_safe": "1.10.0", "cve": "CVE-2022-40664", "severity": "CRITICAL"},
    "struts2-core": {"max_safe": "2.5.30", "cve": "CVE-2021-31805", "severity": "CRITICAL"},
    "tomcat-embed-core": {"max_safe": "9.0.63", "cve": "CVE-2022-22965", "severity": "CRITICAL"},
    "xstream": {"max_safe": "1.4.19", "cve": "CVE-2021-43859", "severity": "HIGH"},
}

def _parse_version(version_str: str) -> tuple:
    try:
        return tuple(int(x) for x in re.findall(r'\d+', version_str))
    except Exception:
        return (0,)

def _version_less(v1: str, v2: str) -> bool:
    return _parse_version(v1) < _parse_version(v2)

def check_cves(repo_path: Path) -> list[Risk]:
    risks: list[Risk] = []; rid = 0
    pom = repo_path / "pom.xml"
    if not pom.exists():
        return risks
    try:
        content = pom.read_text()
        deps = re.findall(r'<artifactId>([^<]+)</artifactId>\s*<version>([^<]+)</version>', content, re.DOTALL)
        for artifact, version in deps:
            if artifact in KNOWN_CVES:
                info = KNOWN_CVES[artifact]
                if _version_less(version, info["max_safe"]):
                    sv = RiskSeverity.CRITICAL if info["severity"] == "CRITICAL" else RiskSeverity.HIGH
                    rid += 1; risks.append(Risk(id=f"CVE-{rid:03d}", category=RiskCategory.SECURITY, severity=sv, confidence=0.95, title=f"{info['cve']}: {artifact}:{version}", description=f"Vulnerable dependency {artifact}@{version} (safe: >={info['max_safe']})", file="pom.xml", recommendation=f"Upgrade {artifact} to {info['max_safe']}+"))
    except Exception:
        pass
    return risks
