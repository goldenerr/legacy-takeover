---
name: legacy-takeover
description: Legacy system takeover assistant — scan any Git repo and generate system manual, architecture diagrams, dependency maps, and risk reports
---

# Legacy Takeover Assistant

Scan a Git repository and generate comprehensive documentation for system handover.

## Trigger

When the user asks to analyze, scan, or document a codebase:
- "分析一下 https://github.com/foo/bar"
- "给我生成这个项目的架构文档"
- "Scan this repo and tell me the risks"
- "评估这个仓库的风险"

## Workflow

1. Identify the repo URL (Git URL or local path)
2. Run: `cd /home/hermes/.hermes/projects/legacy-takeover && python3 -m legacy_takeover.cli <repo_url> --depth standard -o /tmp/legacy-reports`
3. Read the generated SYSTEM_MANUAL.md for a summary
4. Present key findings directly to the user: languages detected, module count, top 5 risks by severity
5. Tell the user where the full report is saved

## Quick Mode

For fast overviews: `python3 -m legacy_takeover.cli <repo_url> --depth quick --no-report`

## Tips

- Outputs: MD docs, Mermaid diagrams, interactive HTML index
- Custom risk rules: add `.legacy-takeover.yaml` in the target repo
- Supports 7 languages: Python, Java, Go, TypeScript, C#, C, C++
