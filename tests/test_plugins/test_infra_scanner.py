"""Tests for Phase 2 infrastructure scanner plugin."""
import tempfile
from pathlib import Path
from legacy_takeover.plugins.infra_scanner import scan_docker, scan_cicd


class TestInfraScanner:
    def test_dockerfile_detection(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Dockerfile").write_text(
                "FROM openjdk:17-slim\n"
                "EXPOSE 8080\n"
                "CMD [\"java\", \"-jar\", \"app.jar\"]\n"
            )
            result = scan_docker(repo)
            assert len(result["dockerfiles"]) == 1
            assert result["dockerfiles"][0]["base_image"] == "openjdk:17-slim"
            assert "8080" in result["dockerfiles"][0]["exposed_ports"]

    def test_dockerfile_multi_stage(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Dockerfile.build").write_text(
                "FROM maven:3 AS builder\n"
                "ENTRYPOINT [\"mvn\"]\n"
            )
            result = scan_docker(repo)
            assert len(result["dockerfiles"]) == 1
            assert result["dockerfiles"][0]["base_image"] == "maven:3"

    def test_jenkins_cicd(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "Jenkinsfile").write_text(
                "pipeline {\n"
                "  stage('Build') {}\n"
                "  stage('Test') {}\n"
                "  stage('Deploy') {}\n"
                "}\n"
            )
            result = scan_cicd(repo)
            assert result["type"] == "Jenkins"
            assert "Build" in result["pipelines"]
            assert "Test" in result["pipelines"]

    def test_github_actions_cicd(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            workflows = repo / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text("name: CI\n")
            (workflows / "deploy.yml").write_text("name: Deploy\n")
            result = scan_cicd(repo)
            assert result["type"] == "GitHub Actions"
            assert "ci" in result["pipelines"]
            assert "deploy" in result["pipelines"]
