# Legacy Takeover Assistant — Design Spec

**Date:** 2026-06-10  
**Status:** Draft → Awaiting review  
**Project path:** `/home/hermes/.hermes/projects/legacy-takeover`

## 1. Overview

A tool that scans any Git repository and generates a **system takeover manual** containing:
- System overview document (Markdown)
- Architecture diagram (Mermaid)
- Database ER diagram (Mermaid)
- Upstream/downstream dependency map
- Risk assessment report with severity scoring

Three delivery channels share one core engine: **CLI · Hermes Skill · Web service**.

## 2. Architecture: 4-Layer Plugin Design

```
┌──────────────────────────────────────────────────────┐
│  Entry Layer                                          │
│  CLI (Click)  │  Hermes Skill  │  Web (FastAPI)       │
├──────────────────────────────────────────────────────┤
│  Core Engine                                          │
│  git clone → language detect → dispatch → aggregate   │
│  Risk scoring engine (configurable rules)             │
├──────────────────────────────────────────────────────┤
│  Plugin Layer (LanguageAnalyzer interface)            │
│  Java/Spring  │  Python/FastAPI  │  Go  │  (future)   │
├──────────────────────────────────────────────────────┤
│  Report Layer (Jinja2 templates)                      │
│  MD doc  │  Mermaid diagrams  │  HTML index           │
└──────────────────────────────────────────────────────┘
```

## 3. Plugin Interface

Every language plugin implements this protocol (Python ABC + Pydantic models):

```python
class LanguageAnalyzer(ABC):
    name: str              # "java", "python", "go"
    
    def detect(self, repo_path: Path) -> float           # confidence 0-1
    def extract_structure(self) -> ModuleGraph            # modules, classes, layers
    def extract_dependencies(self) -> DependencyTree      # internal + external deps
    def extract_db_schema(self) -> ERDiagram              # tables, relationships
    def assess_risks(self) -> list[Risk]                  # scored risks with evidence
```

Plugins discovered via Python `entry_points` group `legacy_takeover.analyzers`. Adding a language = implement one class + register entry point. Core engine never changes.

## 4. Core Engine Pipeline

```
1. Clone repo (shallow: --depth=1) → temp directory
2. Walk file tree, collect extensions + build files
3. For each registered plugin: call detect() → score
4. Select plugins with confidence > 0.3 (multi-language repos get multiple)
5. Run selected plugins in parallel (asyncio):
   a. extract_structure()
   b. extract_dependencies()
   c. extract_db_schema()
   d. assess_risks()
6. Aggregate → normalized intermediate representation (IR)
7. Feed IR to report templates
8. Cleanup temp repo
```

**Configurable depth** (`.legacy-takeover.yaml` in repo or CLI flag):
- `quick`: structure + dependencies only (~30s for 100k LOC)
- `standard`: + DB schema + basic risks (~2min)
- `deep`: + AST analysis, call graphs, security scanning (~5min)

## 5. Risk Engine

Risk scoring formula: `severity (1-10) × confidence (0-1) = risk_score (0-10)`

Built-in risk categories:

| Category | Checks | Detection method |
|----------|--------|------------------|
| Security | Known vulns in deps, hardcoded secrets, unsafe deserialization | dependency scan + regex + AST |
| Tech debt | TODO/FIXME density, commented-out code, circular imports | AST + grep patterns |
| Single point of failure | No replicas, no load balancer, single DB instance | config file heuristics |
| Bus factor | Files with single author (git blame), undocumented modules | git log analysis |
| License compliance | GPL in proprietary, missing licenses | `pip-licenses` / `mvn license:aggregate` |
| Performance | N+1 queries, missing indexes, sync I/O in hot path | AST pattern matching |

**Custom rules:** YAML config file, user defines `pattern → category → severity`. Example:
```yaml
custom_rules:
  - pattern: "Thread\\.sleep"
    file_glob: "*.java"
    category: "performance"
    severity: 4
    message: "Thread.sleep() in request path — use async alternatives"
```

## 6. Report Structure

Output directory: `legacy-report/{repo_name}-{timestamp}/`

```
legacy-report/my-service-20260610-143022/
├── index.html              ← HTML index page (dashboard)
├── SYSTEM_MANUAL.md        ← Full system takeover manual
├── ARCHITECTURE.md         ← Architecture diagram + component descriptions
├── DATABASE.md             ← ER diagram + table descriptions
├── DEPENDENCIES.md         ← Upstream/downstream graph
├── RISK_REPORT.md          ← Prioritized risk matrix
├── diagrams/
│   ├── architecture.mmd    ← Mermaid source (editable)
│   ├── er_diagram.mmd
│   └── dependency_graph.mmd
└── data/
    ├── modules.json         ← Structured IR (for programmatic consumption)
    ├── dependencies.json
    └── risks.json
```

HTML index page: dark-themed dashboard, tabs for each section, interactive Mermaid diagrams, searchable risk table. Self-contained single HTML file (Mermaid.js loaded from CDN).

## 7. Entry Points

### CLI
```bash
legacy-scan https://github.com/org/repo
legacy-scan /path/to/local/repo --depth deep
legacy-scan git@github.com:org/repo.git --output ./my-report
```

### Hermes Skill
```
User: "分析一下 https://github.com/foo/bar"
Agent: loads legacy-takeover skill → runs CLI → returns report summary + file paths
```

### Web Service
```
POST /api/scan  {"repo_url": "...", "depth": "standard"}
GET  /api/scan/{id}/status   ← polling
GET  /api/scan/{id}/report   ← download
```
Simple SPA frontend served by same FastAPI instance.

## 8. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Core | Python 3.11+ | Hermes native, rich ecosystem |
| AST | tree-sitter | Multi-language, no per-language parser needed |
| Plugin discovery | entry_points | Python standard, no custom registry |
| Data models | Pydantic v2 | Validation, serialization, JSON Schema |
| Async | asyncio | Parallel plugin execution |
| CLI | Click | Mature, composable |
| Web | FastAPI + Jinja2 | Shared templates, async-native |
| Mermaid | Inline in MD + CDN in HTML | Git-friendly, renders everywhere |
| Container | Optional Docker | For web deployment |

## 9. MVP Scope (v0.1.0)

**Plugins:** Java/Spring Boot · Python/FastAPI/Django · Go  
**Depth:** `quick` + `standard` (deep mode deferred to v0.2.0)  
**Risk:** Security + Tech debt + Bus factor (remaining categories to v0.2.0)  
**Channels:** CLI + Hermes Skill (Web service to v0.2.0)  
**Tests:** Unit tests for each plugin, integration test for full pipeline

## 10. Project File Structure

```
legacy-takeover/
├── pyproject.toml              # Package metadata + entry_points
├── src/
│   └── legacy_takeover/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entry
│       ├── core/
│       │   ├── engine.py       # Pipeline orchestrator
│       │   ├── git.py          # Clone, shallow fetch
│       │   ├── detector.py     # Language detection dispatcher
│       │   └── aggregator.py   # IR normalization
│       ├── plugins/
│       │   ├── base.py         # LanguageAnalyzer ABC + models
│       │   ├── java.py         # Java/Spring analyzer
│       │   ├── python.py       # Python/FastAPI/Django analyzer
│       │   └── go.py           # Go analyzer
│       ├── risk/
│       │   ├── engine.py       # Rule matching engine
│       │   ├── builtin.py      # Built-in rules
│       │   └── loader.py       # Custom YAML rule loader
│       ├── report/
│       │   ├── renderer.py     # Jinja2 template renderer
│       │   ├── templates/      # .j2 templates for MD + HTML
│       │   └── static/         # CSS, JS for HTML report
│       └── web/                # FastAPI app (v0.2.0)
│           ├── app.py
│           └── routes.py
├── tests/
│   ├── test_engine.py
│   ├── test_plugins/
│   └── fixtures/               # Sample repos for testing
├── skills/
│   └── legacy-takeover.md      # Hermes skill definition
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-10-legacy-takeover-design.md  ← this file
```

## 11. Open Questions (for later)

- Should we cache analysis results to avoid re-scanning?
- Authentication for Web service?
- Multi-repo / monorepo support?
- Incremental scan (only changed files)?
