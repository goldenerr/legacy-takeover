"""Tests for Phase 2 CVE checker plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.cve_checker import check_cves


class TestCveChecker:
    def test_log4j_vulnerable_detected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies>"
                "<dependency><artifactId>log4j-core</artifactId><version>2.14.0</version></dependency>"
                "</dependencies></project>"
            )
            risks = check_cves(repo)
            assert any("CVE-2021-44228" in r.title for r in risks), (
                f"Expected Log4j CVE, got: {[r.title for r in risks]}"
            )

    def test_safe_version_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies>"
                "<dependency><artifactId>log4j-core</artifactId><version>2.17.1</version></dependency>"
                "</dependencies></project>"
            )
            risks = check_cves(repo)
            assert len(risks) == 0, f"Expected no CVEs for patched version, got: {[r.title for r in risks]}"

    def test_no_pom_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            risks = check_cves(repo)
            assert len(risks) == 0

    def test_unknown_artifact_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies>"
                "<dependency><artifactId>some-lib</artifactId><version>1.0.0</version></dependency>"
                "</dependencies></project>"
            )
            risks = check_cves(repo)
            assert len(risks) == 0, f"Expected no CVEs for unknown lib, got: {[r.title for r in risks]}"
