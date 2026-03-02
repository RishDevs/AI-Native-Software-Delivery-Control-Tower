# Setup Guide (Free-Only)

This guide walks through setting up the AI-Native Software Delivery Control Tower
on a local machine with $0 cost.

## Prerequisites

### Required
- **Python 3.11+** — [python.org](https://python.org)
- **Git** — [git-scm.com](https://git-scm.com)
- **Ollama** — [ollama.ai](https://ollama.ai)

### Optional
- **Docker + Docker Compose** — For containerized deployment simulation
- **Grafana** — For observability dashboards (via Docker Compose)

## Step 1: Clone the Repository

```bash
cd ~/projects
git clone <repository-url> "AI-Native Software Delivery Control Tower"
cd "AI-Native Software Delivery Control Tower"
```

## Step 2: Python Environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install --upgrade pip
pip install -e ".[dev]"
```

## Step 3: Install Ollama

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai

# Start Ollama server
ollama serve

# Pull recommended model (in another terminal)
ollama pull qwen2.5-coder:7b

# Optional: pull fallback model
ollama pull llama3:8b
```

### Hardware Notes
- **Minimum:** 8GB RAM, any modern CPU (2020+)
- **Recommended:** 16GB RAM, Apple M1/M2+ or NVIDIA GPU
- Smaller models like `qwen2.5-coder:3b` work on constrained hardware
- Adjust `llm.max_tokens` in `configs/policy.yaml` if responses are slow

## Step 4: Initialize the System

```bash
# Initialize database
python3 -c "
from core.database import Database
db = Database('control_tower.db')
db.create_tables()
print('Database initialized')
"

# Initialize demo target repo
cd demo_target_repo
git init
git add -A
git commit -m 'Initial commit'
cd ..

# Seed demo tasks
python3 scripts/seed_tasks.py
```

## Step 5: Start the Services

### API Server
```bash
uvicorn apps.api.main:app --reload --port 8000
```

### Dashboard (separate terminal)
```bash
streamlit run apps/dashboard/app.py
```

### Verify
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501
- Health check: http://localhost:8000/health

## Step 6: Run Your First Task

```bash
# Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fix case-sensitive search",
    "description": "Make the product search case-insensitive",
    "repo_path": "./demo_target_repo"
  }'

# Note the task_id from the response, then start a run
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"task_id": "<TASK_ID>"}'

# Monitor the run
curl http://localhost:8000/runs/<RUN_ID>
```

## Step 7: Docker Compose (Optional)

For full containerized setup with Prometheus and Grafana:

```bash
docker-compose up -d

# Services:
# - Control Tower API: http://localhost:8000
# - Target Baseline:   http://localhost:8001
# - Target Canary:     http://localhost:8002
# - Prometheus:        http://localhost:9090
# - Grafana:           http://localhost:3000 (admin/admin)
```

## Troubleshooting

### Ollama Connection Error
```
Cannot connect to Ollama at http://localhost:11434
```
→ Ensure `ollama serve` is running

### Model Not Found
```
model 'qwen2.5-coder:7b' not found
```
→ Run `ollama pull qwen2.5-coder:7b`

### Slow LLM Responses
→ Reduce `llm.max_tokens` in `configs/policy.yaml`
→ Use a smaller model: `ollama pull qwen2.5-coder:3b`

### Git Errors on Demo Repo
→ Ensure demo_target_repo has a git init + initial commit
