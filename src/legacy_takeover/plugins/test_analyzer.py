"""Test coverage and quality analysis."""
from __future__ import annotations

import re
from pathlib import Path
from legacy_takeover.plugins.base import Risk, RiskCategory, RiskSeverity


def analyze_tests(repo_path: Path) -> dict:
    """Analyze test coverage for a Java project.

    Returns dict with total_src, total_tests, covered, uncovered, ratio, framework.
    """
    src_dir = repo_path / "src" / "main" / "java"
    test_dir = repo_path / "src" / "test" / "java"

    src_files = list(src_dir.rglob("*.java")) if src_dir.exists() else []
    test_files = list(test_dir.rglob("*.java")) if test_dir.exists() else []

    # Build lookup: class name → test file path
    test_names: dict[str, str] = {}
    if test_dir.exists():
        for tf in test_files:
            stem = tf.stem
            # Remove common test suffixes to get the source class name
            for suffix in ("Test", "Tests", "IT"):
                if stem.endswith(suffix):
                    stripped = stem[: -len(suffix)]
                    if stripped:
                        test_names[stripped] = str(tf.relative_to(test_dir))
                        break
            else:
                test_names[stem] = str(tf.relative_to(test_dir))

    covered: list[str] = []
    uncovered: list[str] = []
    for sf in src_files:
        name = sf.stem
        found = False
        # Check direct match
        if name in test_names:
            found = True
        else:
            # Check partial/substring match
            for k in test_names:
                if name in k or k in name:
                    found = True
                    break
        if found:
            covered.append(str(sf.relative_to(src_dir)))
        else:
            uncovered.append(str(sf.relative_to(src_dir)))

    # Detect test framework
    framework = "unknown"
    if test_dir.exists():
        for tf in test_files:
            try:
                c = tf.read_text(encoding="utf-8", errors="ignore")
                frameworks: list[str] = []
                if "import org.junit" in c:
                    frameworks.append("JUnit")
                if "import org.testng" in c:
                    frameworks.append("TestNG")
                if "Mockito" in c or "import org.mockito" in c:
                    frameworks.append("Mockito")
                if frameworks:
                    framework = " + ".join(frameworks)
                    break
            except Exception:
                pass

    return {
        "total_src": len(src_files),
        "total_tests": len(test_files),
        "covered": covered,
        "uncovered": uncovered,
        "ratio": len(covered) / len(src_files) if src_files else 0.0,
        "framework": framework,
    }


def find_untested_critical(
    analysis: dict, endpoints: list[dict]
) -> list[Risk]:
    """Identify critical endpoints without test coverage.

    Args:
        analysis: Result from analyze_tests()
        endpoints: List of endpoint dicts (method, path, controller, etc.)

    Returns:
        List of Risk objects for untested critical endpoints.
    """
    risks: list[Risk] = []
    rid = 0
    covered_names = {Path(f).stem for f in analysis.get("covered", [])}

    for ep in endpoints:
        ctrl_name = ep.get(
            "controller",
            ep.get("module", "").split(".")[-1] if ep.get("module") else "",
        )
        if ctrl_name and ctrl_name not in covered_names and f"{ctrl_name}Test" not in covered_names:
            sev = (
                RiskSeverity.HIGH
                if ep["method"] in ("POST", "PUT", "DELETE")
                else RiskSeverity.MEDIUM
            )
            rid += 1
            risks.append(Risk(
                id=f"TEST-{rid:03d}",
                category=RiskCategory.BUS_FACTOR,
                severity=sev,
                confidence=0.8,
                title=f"Untested endpoint: {ep['method']} {ep.get('path', '')}",
                description=f"Controller {ctrl_name} has no corresponding test",
                recommendation=f"Add test for {ctrl_name}.",
            ))
    return risks
