"""Tests for Phase 2 security scanner plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.security_scanner import scan_vulnerabilities


class TestSecurityScanner:
    def test_sql_injection_statement_detected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "LegacyDao.java").write_text(
                "public class LegacyDao {\n"
                "  void query() {\n"
                "    Statement stmt = conn.createStatement();\n"
                "    stmt.executeQuery(sql);\n"
                "  }\n"
                "}\n"
            )
            risks = scan_vulnerabilities(repo)
            assert any("SQL" in r.title for r in risks), (
                f"Expected SQL injection risk, got: {[r.title for r in risks]}"
            )

    def test_csrf_disabled_detected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "SecurityConfig.java").write_text(
                "public class SecurityConfig {\n"
                "  http.csrf().disable();\n"
                "}\n"
            )
            risks = scan_vulnerabilities(repo)
            assert any("CSRF" in r.title for r in risks), (
                f"Expected CSRF risk, got: {[r.title for r in risks]}"
            )

    def test_no_false_positives_empty(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Safe.java").write_text(
                "public class Safe {\n"
                "  void query() {\n"
                "    PreparedStatement ps = conn.prepareStatement(sql);\n"
                "  }\n"
                "}\n"
            )
            risks = scan_vulnerabilities(repo)
            sql_risks = [r for r in risks if "SQL" in r.title]
            assert len(sql_risks) == 0, f"Expected no SQL risks, got: {sql_risks}"
