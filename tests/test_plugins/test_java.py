"""Tests for Java analyzer plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.java import JavaAnalyzer


class TestJavaAnalyzer:
    def test_detect_empty_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            a = JavaAnalyzer(repo_path=Path(d))
            assert a.detect() == 0.0

    def test_detect_with_java_files(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Main.java").write_text("public class Main {}")
            a = JavaAnalyzer(repo_path=repo)
            score = a.detect()
            assert score > 0.0
            assert score <= 1.0

    def test_detect_with_pom_xml(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text("<project></project>")
            a = JavaAnalyzer(repo_path=repo)
            score = a.detect()
            assert score == 0.2

    def test_extract_structure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "src").mkdir()
            (repo / "pom.xml").write_text("<project></project>")
            a = JavaAnalyzer(repo_path=repo)
            graph = a.extract_structure()
            assert graph.language == "java"
            assert any(m.name == "src" for m in graph.modules)

    def test_extract_dependencies_from_pom(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<dependencies>"
                "<dependency><artifactId>spring-boot-starter</artifactId></dependency>"
                "<dependency><artifactId>lombok</artifactId></dependency>"
                "</dependencies></project>"
            )
            a = JavaAnalyzer(repo_path=repo)
            tree = a.extract_dependencies()
            assert len(tree.external_deps) >= 2

    def test_assess_risks_detects_thread_sleep(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Worker.java").write_text("class Worker { void run() { Thread.sleep(1000); } }")
            a = JavaAnalyzer(repo_path=repo)
            risks = a.assess_risks()
            assert any("Thread.sleep" in r.title for r in risks)
