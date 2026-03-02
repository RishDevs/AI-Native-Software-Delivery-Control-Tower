# AI-Native Software Delivery Control Tower

> **Agentic Code Changes, Risk-Aware CI/CD Gating, and Observability-Driven Rollbacks**

A local-first platform that accepts engineering tasks, performs AI-assisted code modification through an agent workflow, validates changes with automated checks, computes deployment risk, simulates canary rollouts, monitors runtime signals, and triggers rollback when regressions are detected.

Built entirely with **free and open-source tools** — no paid APIs or cloud dependencies.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTROL TOWER API (FastAPI)                   │
├─────────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Ingestion  │  Agent   │   Tool   │ Decision │  Observability  │
│   Layer     │ Orchestr.│ Execution│  Layer   │   & Reliability │
├─────────────┼──────────┼──────────┼──────────┼─────────────────┤
│ • Ticket    │ • Plan   │ • Git    │ • Risk   │ • Canary Sim    │
│ • Repo Scan │ • Code   │ • Tests  │ • Policy │ • Regression    │
│ • Policy    │ • Review │ • Lint   │ • Gate   │ • Rollback      │
│   Load      │ • Secur. │ • Bandit │ • Release│ • Incident      │
│             │ • Release│ • mypy   │          │   Report        │
│             │ • Incid. │ • Patch  │          │                 │
├─────────────┴──────────┴──────────┴──────────┴─────────────────┤
│                  Persistence (SQLite + Artifacts)               │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Git
- [Ollama](https://ollama.ai) (for local LLM)
- Docker + Docker Compose (optional, for canary simulation)

### Setup
```bash
# Clone and enter the project
cd "AI-Native Software Delivery Control Tower"

# Run the setup script
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh

# Or manual setup:
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Start Ollama
```bash
ollama serve &
ollama pull qwen2.5-coder:7b
```

### Run the Control Tower
```bash
# Start the API server
source .venv/bin/activate
uvicorn apps.api.main:app --reload --port 8000

# In another terminal — start the dashboard
streamlit run apps/dashboard/app.py
```

### Create and Execute a Task
```bash
# Seed demo tasks
python scripts/seed_tasks.py

# Or create via API
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fix case-sensitive product search",
    "description": "The search function uses case-sensitive matching. Fix it to be case-insensitive.",
    "repo_path": "./demo_target_repo"
  }'

# Start a run (replace TASK_ID)
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK_ID"}'

# Check run status
curl http://localhost:8000/runs/RUN_ID
```

---

## 📋 Technology Stack (100% Free)

| Component | Technology |
|-----------|-----------|
| **Backend API** | FastAPI + Uvicorn |
| **LLM Runtime** | Ollama (Qwen2.5-Coder 7B) |
| **Database** | SQLite + SQLAlchemy |
| **Validation** | pytest, ruff, mypy, bandit, pip-audit |
| **Observability** | Prometheus + Grafana |
| **Deployment Sim** | Docker Compose |
| **Dashboard** | Streamlit |
| **Schemas** | Pydantic v2 |

---

## 🤖 Agent Pipeline

The system uses a multi-agent architecture where each agent has a specialized role:

| Agent | Type | Purpose |
|-------|------|---------|
| **Planner** | LLM-powered | Transforms task → implementation plan |
| **Coder** | LLM-powered | Generates code patches from plan |
| **Reviewer** | LLM-powered | Evaluates patch correctness |
| **Security** | Rule-based | Normalizes security scan findings |
| **Release** | Rule-based | Determines deployment gate strategy |
| **Incident** | Rule-based | Analyzes canary anomalies + postmortem |

### Pipeline Lifecycle
```
PENDING → PLANNING → CODING → VALIDATING → REVIEWING
    → RISK_SCORING → GATING → DEPLOYING → MONITORING
        → COMPLETED | ROLLING_BACK → COMPLETED
        OR → BLOCKED | AWAITING_APPROVAL
```

---

## 🔒 Safety Guardrails

- **YAML Policy Engine** — Configurable blocked paths, file limits, risk thresholds
- **Structured Outputs** — All LLM outputs validated against Pydantic schemas
- **Fail-Safe Defaults** — Block rather than approve when uncertain
- **Human Approval** — Required for high-risk or auth/security changes
- **Automatic Rollback** — Canary regression triggers immediate rollback

---

## 📊 Risk Scoring

Transparent, rule-based scoring with full explainability:

```
Risk Score: 45.0/100 → Level: MEDIUM

Contributing Factors:
  • files_changed: +10 — 2 files changed
  • critical_module: +20 — auth module touched
  • low_confidence: +15 — Agent confidence 0.35
```

Risk levels drive gate decisions:
- **Low (≤20)** → Auto-approve
- **Medium (21-50)** → Canary deployment
- **High (>50)** → Human review required

---

## 📦 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tasks` | Create a task |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/tasks/{id}` | Get task details |
| `POST` | `/runs` | Start a pipeline run |
| `GET` | `/runs/{id}` | Get run status + summary |
| `GET` | `/runs/{id}/artifacts` | List run artifacts |
| `POST` | `/runs/{id}/approve` | Human approval action |
| `POST` | `/runs/{id}/rollback` | Manual rollback |
| `GET` | `/policies` | Get policy config |
| `GET` | `/metrics/summary` | Aggregate metrics |
| `GET` | `/health` | System health check |

Interactive docs: `http://localhost:8000/docs`

---

## 🧪 Benchmark Suite

20 tasks across 8 categories:

| Category | Count | Examples |
|----------|-------|---------|
| Bug Fixes | 4 | Case-sensitive search, missing validation |
| Input Validation | 3 | Pagination, uniqueness checks |
| Security Hardening | 3 | Rate limiting, sanitization |
| API Corrections | 3 | Status codes, sorting, error format |
| Refactors | 2 | Module extraction, repository pattern |
| Reliability | 3 | Timeouts, structured logging |
| Test Generation | 2 | Edge cases, integration tests |

```bash
# Run full benchmark
python scripts/run_benchmark.py

# Run specific categories
python scripts/run_benchmark.py --categories bug_fix input_validation

# Run limited tasks
python scripts/run_benchmark.py --max-tasks 5
```

---

## 📁 Project Structure

```
control-tower/
├── apps/
│   ├── api/main.py              # FastAPI control plane
│   └── dashboard/app.py         # Streamlit dashboard
├── agents/
│   ├── planner.py               # LLM-powered planning
│   ├── coder.py                 # LLM-powered code generation
│   ├── reviewer.py              # LLM-powered code review
│   ├── security.py              # Rule-based security analysis
│   ├── release.py               # Rule-based gate decisions
│   └── incident.py              # Rule-based incident handling
├── core/
│   ├── orchestrator.py          # Pipeline lifecycle manager
│   ├── state_machine.py         # Run state transitions
│   ├── policy_engine.py         # YAML policy enforcement
│   ├── risk_engine.py           # Weighted risk scoring
│   ├── database.py              # SQLite persistence
│   └── artifacts.py             # Artifact storage
├── tools/
│   ├── llm_client.py            # Ollama client wrapper
│   ├── repo_scanner.py          # Repository context extraction
│   ├── git_ops.py               # Git operations
│   ├── patch_apply.py           # Patch application + safety
│   ├── validation_runner.py     # Test/lint/security runners
│   └── deploy_simulator.py      # Canary deployment simulation
├── schemas/                     # Pydantic schemas for all agents
├── configs/
│   ├── policy.yaml              # Policy configuration
│   └── prometheus.yml           # Prometheus scrape config
├── benchmarks/
│   └── tasks/benchmark_tasks.yaml
├── demo_target_repo/            # Target microservice with bugs
├── scripts/
│   ├── setup_env.sh
│   ├── seed_tasks.py
│   └── run_benchmark.py
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## 🏆 Key Differentiators

1. **Structured Agent Design** — Not just "call an LLM" — multi-agent pipeline with specialized roles, validated schemas, and clear handoffs
2. **Policy Guardrails** — YAML-based safety rules prevent autonomous harm
3. **Reliability Mechanisms** — Retry loops, fail-safe defaults, schema validation, rollback triggers
4. **Measurable Evaluation** — 20-task benchmark suite with quantitative metrics
5. **Full Explainability** — Risk scores show exactly why a decision was made
6. **$0 Cost** — Entire stack runs locally with open-source tools

---

## 📝 License

MIT License

---

*Built with ❤️ as an AI-native software engineering demonstration*
