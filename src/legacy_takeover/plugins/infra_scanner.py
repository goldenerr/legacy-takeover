"""Infrastructure scanner: Docker, K8s, CI/CD."""
from __future__ import annotations
import re
from pathlib import Path

def scan_docker(repo_path: Path) -> dict:
    result: dict = {"dockerfiles": [], "docker_compose": None}
    for df in repo_path.rglob("Dockerfile*"):
        info: dict = {"path": str(df.relative_to(repo_path)), "base_image": "", "exposed_ports": [], "entrypoint": ""}
        for line in df.read_text().splitlines():
            if line.startswith("FROM "):
                info["base_image"] = line[5:].split()[0]
            elif line.startswith("EXPOSE "):
                info["exposed_ports"].append(line[7:].strip())
            elif line.startswith("CMD ") or line.startswith("ENTRYPOINT "):
                info["entrypoint"] += line.strip() + " "
        result["dockerfiles"].append(info)

    dc = repo_path / "docker-compose.yml"
    if not dc.exists():
        dc = repo_path / "docker-compose.yaml"
    if dc.exists():
        try:
            import yaml
            data = yaml.safe_load(dc.read_text())
            result["docker_compose"] = {
                "services": list(data.get("services", {}).keys()),
                "volumes": list(data.get("volumes", {}).keys()) if data.get("volumes") else [],
            }
        except Exception:
            pass

    # K8s
    k8s_dir = repo_path / "k8s"
    if not k8s_dir.exists():
        k8s_dir = repo_path / "kubernetes"
    k8s_files = list(k8s_dir.rglob("*.yaml")) + list(k8s_dir.rglob("*.yml")) if k8s_dir.exists() else []
    result["kubernetes"] = {"manifests": len(k8s_files)} if k8s_files else None

    return result


def scan_cicd(repo_path: Path) -> dict:
    ci: dict = {"type": "unknown", "pipelines": []}
    if (repo_path / "Jenkinsfile").exists():
        ci["type"] = "Jenkins"
        content = (repo_path / "Jenkinsfile").read_text()
        ci["pipelines"] = re.findall(r"stage\s*\(\s*'([^']+)'\s*\)", content)
    gh = repo_path / ".github" / "workflows"
    if gh.exists():
        ci["type"] = "GitHub Actions"
        ci["pipelines"] = [wf.stem for wf in gh.glob("*.yml")]
    if (repo_path / ".gitlab-ci.yml").exists():
        ci["type"] = "GitLab CI"
    return ci
