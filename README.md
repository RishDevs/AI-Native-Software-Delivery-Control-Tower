<img src=".github/header.svg" width="100%" alt="AI-Native-Software-Delivery-Control-Tower — Delivery Control Tower — README header">

<div align="center">

# 🏗️ AI-Native Software Delivery Control Tower

### Agentic Code Changes · Risk-Aware CI/CD Gating · Observability-Driven Rollbacks

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?style=for-the-badge)](https://ollama.ai)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br>

*A local-first AI platform that accepts engineering tasks, generates code patches via LLM agents,*  
*validates with automated CI/CD checks, computes deployment risk, simulates canary rollouts,*  
*monitors runtime signals, and triggers rollback when regressions are detected.*

**100% Free & Open Source — No paid APIs, no cloud dependencies.**

<br>

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [Agent Pipeline](#-agent-pipeline) · [API Reference](#-api-reference) · [Benchmarks](#-benchmark-suite) · [Documentation](#-documentation)

</div>

---

## ✨ Highlights

- 🤖 **Multi-Agent Orchestration** — 6 specialized agents (3 LLM-powered, 3 rule-based) with structured Pydantic-validated outputs
- 🛡️ **Policy Guardrails** — YAML-driven safety engine with blocked paths, file limits, and fail-safe defaults
- ⚖️ **Explainable Risk Scoring** — Weighted rule-based engine that shows exactly *why* a score was given
- 🔄 **Full CI/CD Simulation** — Automated tests, lint, type-check, security scans, canary deployment, and rollback
- 📊 **Real-Time Dashboard** — Streamlit-powered UI for run tracking, metrics, and incident summaries
- 🧪 **20-Task Benchmark Suite** — Reproducible evaluation across 8 categories with quantitative KPIs
- 💰 **$0 Cost** — Runs entirely on local hardware with Ollama, SQLite, and open-source tools

---

## 🏛️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     CONTROL TOWER API (FastAPI)                      │
├───────────────┬────────────┬────────────┬────────────┬──────────────┤
│   Ingestion   │   Agent    │    Tool    │  Decision  │ Observability│
│    Layer      │ Orchestra. │  Execution │   Layer    │ & Reliability│
├───────────────┼────────────┼────────────┼────────────┼──────────────┤
│ • Ticket      │ • Planner  │ • Git Ops  │ • Risk     │ • Canary Sim │
│   Parser      │   (LLM)    │ • pytest   │   Engine   │ • Regression │
│ • Repo        │ • Coder    │ • ruff     │ • Policy   │   Detection  │
│   Scanner     │   (LLM)    │ • mypy     │   Engine   │ • Auto       │
│ • Policy      │ • Reviewer │ • bandit   │ • Gate     │   Rollback   │
│   Loader      │   (LLM)    │ • pip-audit│   Decision │ • Incident   │
│               │ • Security │ • Patch    │            │   Report     │
│               │ • Release  │   Apply    │            │ • Postmortem │
│               │ • Incident │            │            │   Draft      │
├───────────────┴────────────┴────────────┴────────────┴──────────────┤
│                Persistence (SQLite + Filesystem Artifacts)           │
└──────────────────────────────────────────────────────────────────────┘
```

### Pipeline Lifecycle (State Machine)

```
PENDING ──▶ PLANNING ──▶ CODING ──▶ VALIDATING ──▶ REVIEWING
                                                       │
              ┌────────────────────────────────────────┘
              ▼
         RISK_SCORING ──▶ GATING ──┬──▶ APPROVE ──▶ COMPLETED
                                   ├──▶ CANARY  ──▶ DEPLOYING ──▶ MONITORING
                                   │                                  │
                                   ├──▶ HUMAN_REVIEW ──▶ AWAITING    ├──▶ COMPLETED
                                   │                                  │
                                   └──▶ BLOCK ──▶ BLOCKED            └──▶ ROLLING_BACK ──▶ COMPLETED
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Python](https://python.org) | 3.11+ | Runtime |
| [Git](https://git-scm.com) | Any | Version control |
| [Ollama](https://ollama.ai) | Latest | Local LLM inference |
| [Docker](https://docker.com) | Optional | Containerized canary sim |

### 1. Clone & Install

```bash
git clone https://github.com/RishDevs/AI-Native-Software-Delivery-Control-Tower.git
cd AI-Native-Software-Delivery-Control-Tower

# Automated setup
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh

# Or manual setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Start Ollama

```bash
ollama serve                    # Start the LLM server
ollama pull qwen2.5-coder:7b   # Pull the recommended model
```

### 3. Initialize & Run

```bash
source .venv/bin/activate

# Initialize database & seed demo tasks
python3 scripts/seed_tasks.py

# Start the API server
uvicorn apps.api.main:app --reload --port 8000

# Start the dashboard (new terminal)
streamlit run apps/dashboard/app.py
```

### 4. Create Your First Run

```bash
# Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fix case-sensitive product search",
    "description": "The search_products function uses case-sensitive matching. Fix it to be case-insensitive.",
    "repo_path": "./demo_target_repo"
  }'

# Start a run (use the task_id from response)
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"task_id": "YOUR_TASK_ID"}'

# Monitor the run
curl http://localhost:8000/runs/YOUR_RUN_ID
```

> 📖 **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)  
> 📊 **Dashboard:** [http://localhost:8501](http://localhost:8501)

---

## 🤖 Agent Pipeline

The system employs a **multi-agent architecture** where each agent has a specialized role, structured I/O schemas, and clear handoff contracts.

| Agent | Type | Input | Output | Safety |
|-------|------|-------|--------|--------|
| **🗺️ Planner** | LLM (Qwen2.5-Coder) | Task + repo context | Implementation plan | No file modifications allowed |
| **💻 Coder** | LLM (Qwen2.5-Coder) | Plan + file contents | Code patches (diff) | Max files/lines enforced |
| **🔍 Reviewer** | LLM (Qwen2.5-Coder) | Patch + task desc. | Findings + recommendation | Severity categorization |
| **🔒 Security** | Rule-based | Bandit + pip-audit | Normalized findings | Block on HIGH/CRITICAL |
| **🚀 Release** | Rule-based | Risk + validation | Gate decision | Fail-safe to BLOCK |
| **🚨 Incident** | Rule-based | Canary metrics | Rollback + postmortem | Auto-rollback on breach |

### Structured Output Flow

All LLM outputs are **validated against Pydantic schemas** with automatic retry on malformed JSON:

```
LLM Prompt → Raw JSON Response → JSON Extraction → Pydantic Validation
                                                          │
                                              ┌───── Valid ✅ ──▶ Pipeline
                                              │
                                              └── Invalid ❌ ──▶ Retry (up to 3x)
                                                                    │
                                                              Fallback Model ──▶ Retry
```

---

## 🛡️ Safety & Policy Engine

A YAML-based policy engine enforces guardrails at every stage:

```yaml
# Key safety constraints
autonomous:
  max_files_changed: 5          # Limit blast radius
  max_patch_size_lines: 500     # Prevent runaway generation

blocked_paths:
  files: [".env", "*.key", "*.pem"]  # Protect secrets
  directories: [".git", "production/"]

gate:
  default_decision: "block"     # Fail-safe: block when uncertain

rollback:
  auto_rollback: true           # Automatic on threshold breach
```

> **Design Principle:** If a policy is ambiguous, the stricter interpretation always applies.

---

## ⚖️ Risk Scoring Engine

Transparent, weighted, fully explainable:

```
Risk Score: 45.0/100 → Level: MEDIUM

Contributing Factors:
  • files_changed:    +10 — 2 files changed (penalty per file beyond 1)
  • critical_module:  +20 — Critical module path detected (auth/)
  • low_confidence:   +15 — Agent confidence is 0.35 (< 0.5 threshold)

Gate Recommendation: CANARY
```

| Risk Level | Score Range | Action |
|-----------|------------|--------|
| 🟢 **Low** | 0–20 | Auto-approve |
| 🟡 **Medium** | 21–50 | Canary deployment |
| 🔴 **High** | 51–100 | Human review required |

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info |
| `GET` | `/health` | System health (Ollama, DB, policy) |
| `POST` | `/tasks` | Create engineering task |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/tasks/{id}` | Get task details |
| `POST` | `/runs` | Start pipeline run |
| `GET` | `/runs/{id}` | Get run status + summary |
| `GET` | `/runs/{id}/artifacts` | List run artifacts |
| `POST` | `/runs/{id}/approve` | Human approval action |
| `POST` | `/runs/{id}/rollback` | Manual rollback trigger |
| `GET` | `/policies` | Current policy config |
| `GET` | `/metrics/summary` | Aggregate metrics |

---

## 🧪 Benchmark Suite

20 reproducible tasks across 8 categories targeting the demo inventory microservice:

| Category | Tasks | Difficulty | Example |
|----------|-------|------------|---------|
| 🐛 Bug Fixes | 4 | Easy | Fix case-sensitive search |
| ✅ Input Validation | 3 | Medium | Add pagination, uniqueness checks |
| 🔒 Security Hardening | 3 | Medium–Hard | Rate limiting, input sanitization |
| 🔧 API Corrections | 3 | Easy–Medium | HTTP status codes, sorting |
| ♻️ Refactors | 2 | Medium | Module extraction, repository pattern |
| 🛡️ Reliability | 3 | Medium | Request timeouts, structured logging |
| 🧪 Test Generation | 2 | Easy–Medium | Edge case tests, integration tests |

```bash
# Run all 20 benchmarks
python scripts/run_benchmark.py

# Run by category
python scripts/run_benchmark.py --categories bug_fix security

# Run limited set
python scripts/run_benchmark.py --max-tasks 5
```

### Success Criteria (per task)
- ✅ Patch applies successfully
- ✅ Tests pass after patch
- ✅ No new lint/type-check errors
- ✅ No HIGH/CRITICAL security findings
- ✅ Canary metrics within thresholds

---

## 📁 Project Structure

```
📦 AI-Native-Software-Delivery-Control-Tower
├── 🌐 apps/
│   ├── api/main.py                 # FastAPI control plane (11 endpoints)
│   └── dashboard/app.py            # Streamlit dashboard (5 pages)
├── 🤖 agents/
│   ├── planner.py                  # LLM → implementation plan
│   ├── coder.py                    # LLM → code patches
│   ├── reviewer.py                 # LLM → code review
│   ├── security.py                 # Rule-based security analysis
│   ├── release.py                  # Rule-based gate decisions
│   └── incident.py                 # Rule-based incident handling
├── ⚙️ core/
│   ├── orchestrator.py             # Pipeline lifecycle (10 stages)
│   ├── state_machine.py            # 14-state validated transitions
│   ├── policy_engine.py            # YAML guardrails enforcement
│   ├── risk_engine.py              # Weighted explainable scoring
│   ├── database.py                 # SQLite (9 tables, WAL mode)
│   └── artifacts.py                # Filesystem artifact storage
├── 🔧 tools/
│   ├── llm_client.py               # Ollama + structured output + retries
│   ├── repo_scanner.py             # Repository context extraction
│   ├── git_ops.py                  # Branch, commit, reset, diff
│   ├── patch_apply.py              # Safe patch application
│   ├── validation_runner.py        # pytest/ruff/mypy/bandit/pip-audit
│   └── deploy_simulator.py         # Canary deployment + metrics
├── 📐 schemas/                     # Pydantic v2 schemas for all agents
│   ├── common.py                   # 14 enums + base models
│   ├── planner.py / coder.py       # Agent I/O contracts
│   ├── reviewer.py / security.py   # Review & security schemas
│   ├── release.py / incident.py    # Release & incident schemas
│   └── validation.py               # Validation + risk schemas
├── 📋 configs/
│   ├── policy.yaml                 # Safety policy configuration
│   ├── prometheus.yml              # Metrics scrape config
│   └── prompts/                    # LLM system prompt templates
├── 🧪 benchmarks/
│   └── tasks/benchmark_tasks.yaml  # 20 benchmark tasks
├── 🎯 demo_target_repo/            # Target microservice (5 seeded bugs)
│   ├── app/main.py                 # FastAPI inventory service
│   ├── tests/test_main.py          # Unit test suite
│   └── Dockerfile
├── 📜 scripts/
│   ├── setup_env.sh                # Automated environment setup
│   ├── seed_tasks.py               # Seed demo tasks
│   └── run_benchmark.py            # Benchmark runner + metrics
├── 📚 docs/
│   ├── architecture.md             # 6-layer architecture deep dive
│   ├── setup.md                    # Free-only local setup guide
│   └── evaluation.md               # Benchmark methodology + KPIs
├── 🐳 docker-compose.yml           # Full stack (API + Prometheus + Grafana)
├── Dockerfile
└── pyproject.toml
```

---

## 🔧 Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | FastAPI + Uvicorn | Async, auto-docs, Pydantic-native |
| **LLM Runtime** | Ollama (Qwen2.5-Coder 7B) | Free, local, fast for coding tasks |
| **Database** | SQLite + SQLAlchemy | Zero-config, WAL mode, reliable |
| **Validation** | pytest · ruff · mypy · bandit · pip-audit | Industry-standard toolchain |
| **Observability** | Prometheus + Grafana | OSS monitoring stack |
| **Dashboard** | Streamlit | Rapid data UI with zero frontend build |
| **Schemas** | Pydantic v2 | Strict validation, JSON schema generation |
| **Containers** | Docker Compose | Multi-service orchestration |

---

## 🏆 Key Differentiators

| Feature | This Project | Naive "Call LLM" Approach |
|---------|-------------|--------------------------|
| Agent Design | 6 specialized agents with contracts | Single prompt, hope for the best |
| Safety | Policy engine + blocked paths + fail-safe | No guardrails |
| Risk Scoring | Weighted, explainable, configurable | None |
| Validation | 5-tool CI/CD pipeline | Maybe run tests |
| Deployment | Canary simulation + auto-rollback | Direct deploy |
| Auditability | Full artifact trail + state history | Nothing saved |
| Evaluation | 20-task benchmark with KPIs | Ad-hoc testing |

---

## 📚 Documentation

- [**Architecture Guide**](docs/architecture.md) — 6-layer system design, data flow, security model
- [**Setup Guide**](docs/setup.md) — Step-by-step local installation (free-only)
- [**Evaluation Methodology**](docs/evaluation.md) — Benchmark design, KPIs, comparison baselines

---

## 🗺️ Roadmap

- [ ] Multi-agent parallel execution
- [ ] Test generation agent
- [ ] Historical risk scoring with ML
- [ ] Multi-language support (Python + JS/TS)
- [ ] React/Next.js frontend upgrade
- [ ] Kubernetes (kind) deployment target

---

## 📝 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with** ❤️ **as an AI-native software engineering demonstration**

*Structured agent design · Policy guardrails · Reliability mechanisms · Measurable evaluation*

</div>
