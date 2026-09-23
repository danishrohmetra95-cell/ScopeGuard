<div align="center">

# 🛡️ ScopeGuard

### Intelligent Code Change Impact & Regression Risk Analysis

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19+-61dafb.svg?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![Tests](https://img.shields.io/badge/tests-221_passing-10b981.svg?style=flat-square)](backend/tests/)
[![License](https://img.shields.io/badge/license-proprietary-5a6580.svg?style=flat-square)]()

**ScopeGuard analyzes your codebase to determine blast radius, regression risk, and test impact when code changes are made. AST-powered, deterministic, zero AI required.**

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **AST Analysis** | Parses Python source files to extract functions, classes, imports, calls, API routes, and detects dynamic dependencies (`eval`, `exec`, `importlib`) |
| 🕸️ **Dependency Graph** | NetworkX-based directed graph with IMPORTS, CALLS, CONTAINS edges. Classifies dependencies as FIRST_PARTY, STANDARD_LIBRARY, THIRD_PARTY |
| 📊 **Commit Impact** | Function-level change detection with semantic classification (whitespace, documentation, code-modifications) & transitive impact traversal |
| ⚠️ **Risk Scoring** | Deterministic 0-100 risk score with transparent, weighted factors — no AI/LLM |
| 🧪 **Test Selection** | Identifies which tests should run based on dependency graph impact |
| 📈 **Historical Intelligence** | Analyzes commit history for hotspots, risk trends, and change patterns |
| 🖥️ **React Dashboard** | Premium dark-mode UI with interactive dependency graph, charts, and gauges |
| 🔧 **CLI & CI/CD** | Risk gating with configurable thresholds, JSON reports, GitHub Actions workflow |
| 🐳 **Docker** | Full-stack containerization with health checks |

---

## 🚀 Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**API:** `http://127.0.0.1:8000` · **Docs:** `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

**Dashboard:** `http://localhost:5173`

### Docker (Full Stack)

```bash
docker compose up --build
```

**Backend:** `http://localhost:8000` · **Frontend:** `http://localhost:80`

---

## 🏗️ Architecture

```
ScopeGuard/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── api/analysis.py            # REST API endpoints
│   │   ├── analyzers/                 # AST, Impact, Risk, Test, History analyzers
│   │   ├── cli/                       # CLI entry point
│   │   ├── reporting/                 # JSON report generation
│   │   ├── services/git_service.py    # Read-only Git operations
│   │   ├── models/                    # Pydantic data models
│   │   └── core/config.py            # Configuration
│   ├── tests/                         # 221 pytest tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                     # Dashboard, Commit, Graph, Tests, History
│   │   ├── components/                # MetricCard, StatusBadge, etc.
│   │   ├── layouts/AppLayout.tsx      # Premium dark sidebar layout
│   │   └── services/api.ts           # Axios API client
│   ├── Dockerfile
│   └── package.json
├── .github/workflows/scopeguard.yml   # CI/CD pipeline
├── docker-compose.yml
└── sample-repository/                 # Sample e-commerce app with Git history
```

### Analysis Pipeline

```
Git Commit
    │
    ▼
Git Diff (file-level)  →  added / modified / deleted / renamed
    │
    ▼
AST Comparison (function-level)  →  ADDED / REMOVED / MODIFIED
    │
    ▼
Changed Components  →  mapped to dependency graph node IDs
    │
    ▼
Dependency Graph (built from HEAD)
    │
    ▼
Direct Impact  →  components with a direct dependency on changed code
    │
    ▼
Transitive Impact  →  components reachable through dependency chains
    │
    ▼
Blast Radius  →  summary statistics of all affected components
    │
    ▼
Risk Score (0-100)  →  LOW / MEDIUM / HIGH / CRITICAL
    │
    ▼
Test Selection  →  HIGH / MEDIUM / LOW priority tests to run
```

### Component Overview

| Component | Responsibility |
|-----------|----------------|
| **LanguageAnalyzer** | Protocol for language-specific AST analyzers. |
| **ASTAnalyzer** | Implements `LanguageAnalyzer` for Python. Parses Python files via `ast`. Extracts functions, classes, imports, calls, routes, and dynamic dependencies. |
| **RepositoryScanner** | Discovers files, enforces scalability limits, orchestrates AST analysis. |
| **DependencyGraphBuilder** | Builds a NetworkX directed graph with IMPORTS, CALLS, CONTAINS edges, and classifies module origins. |
| **GitService** | Read-only Git operations: repo validation, commit info, file diffs. |
| **ChangeDetector** | Compares parent and current AST to detect added/removed/modified components and semantic change type. |
| **ImpactAnalyzer** | Orchestrates the full Git diff → impact → blast radius pipeline. |
| **RiskEngine** | Calculates deterministic regression risk score (0-100) with recommendations. |
| **TestAnalyzer** | Statically discovers test files and builds test-to-component mappings. |
| **TestImpactAnalyzer** | Determines which tests are affected, assigns HIGH/MEDIUM/LOW priority. |
| **HistoryAnalyzer** | Analyzes multiple commits for hotspots, risk trends, and insights. |

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness check |
| `GET` | `/api/version` | Version & build info |
| `POST` | `/api/analyze/repository` | Repository scan |
| `POST` | `/api/analyze/dependencies` | Dependency graph |
| `GET` | `/api/analyze/dependencies/{id}/impact` | Component impact |
| `POST` | `/api/analyze/commit` | Commit analysis |
| `POST` | `/api/analyze/commit/risk` | Risk scoring |
| `POST` | `/api/analyze/commit/tests` | Test impact |
| `POST` | `/api/analyze/history` | Historical analysis |

---

## 🔧 CLI

```bash
cd backend

# Analyze repository structure
python -m app.cli.main analyze <repository>
python -m app.cli.main analyze <repository> --json

# Analyze commit risk
python -m app.cli.main risk <repository> --commit HEAD
python -m app.cli.main risk <repository> --commit HEAD --threshold 75

# Analyze test impact
python -m app.cli.main tests <repository> --commit HEAD

# Analyze change history
python -m app.cli.main history <repository> --limit 20
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or risk score ≤ threshold) |
| `1` | Error |
| `2` | Risk gate failed (score > threshold) |

---

## ⚙️ Configuration

All settings can be overridden with `SCOPEGUARD_*` environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `SCOPEGUARD_ENVIRONMENT` | `development` | `development` or `production` |
| `SCOPEGUARD_DEBUG` | `false` | Enable debug mode |
| `SCOPEGUARD_LOG_LEVEL` | `INFO` | Logging level |
| `SCOPEGUARD_HOST` | `127.0.0.1` | Server bind address |
| `SCOPEGUARD_PORT` | `8000` | Server port |
| `SCOPEGUARD_CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated CORS origins |
| `SCOPEGUARD_RISK_THRESHOLD` | `75` | Default risk gate threshold |

---

## 🧪 Testing

```bash
cd backend
python -m pytest tests/ -v
```

**221 tests** covering:

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_ast_analyzer.py` | 16 | AST parsing, imports, calls, routes |
| `test_repository_scanner.py` | 22 | File discovery, scanning, API endpoints |
| `test_dependency_graph.py` | 51 | Graph nodes, edges, traversal, statistics |
| `test_git_analysis.py` | 38 | Git ops, change detection, impact, blast radius |
| `test_risk_engine.py` | 30 | Risk calculation, thresholds, factors |
| `test_test_analysis.py` | 26 | Test discovery, mapping, priority selection |
| `test_history_analysis.py` | — | Historical analytics, hotspots, trends |
| `test_cli.py` | — | CLI commands, exit codes |
| `test_config.py` | — | Configuration, environment variables |
| `test_reporting.py` | — | JSON report generation |

---

## 🔒 Design Decisions

1. **Graph from HEAD** — The dependency graph reflects the current checkout, not the historical state. This answers: *"Given the current structure, what would be affected?"*

2. **No test execution** — ScopeGuard NEVER executes tests from the analyzed repository. It only identifies and prioritises affected tests.

3. **Deterministic scoring** — Risk scores are entirely rule-based with transparent, weighted factors. No AI/LLM is used.

4. **Static analysis only** — Cannot determine runtime behavior, dynamic imports, or monkey-patching.

5. **Python only** — Currently limited to Python source files.

---

## 🗺️ Roadmap

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ | Repository Scanner |
| M2 | ✅ | Dependency Graph Engine |
| M3 | ✅ | Git Diff & Change Impact |
| M4 | ✅ | Deterministic Risk Engine |
| M5 | ✅ | Test Impact & Selection |
| M6 | ✅ | Historical Change Intelligence |
| M7 | ✅ | Interactive React Dashboard |
| M8 | ✅ | CI/CD & Production Integration |
| M9 | 🔜 | AI/LLM-powered explanations |

---

## 📄 License

This project is proprietary. All rights reserved.
t e s t  
 