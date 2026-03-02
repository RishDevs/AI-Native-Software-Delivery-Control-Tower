#!/bin/bash
# ── AI-Native Software Delivery Control Tower — Setup Script ──
# This script sets up the local development environment (free-only).

set -e

echo "🏗️  AI-Native Software Delivery Control Tower — Setup"
echo "======================================================"

# Check Python version
echo ""
echo "📋 Checking prerequisites..."

python3 --version || {
    echo "❌ Python 3.11+ required. Install from https://python.org"
    exit 1
}

git --version || {
    echo "❌ Git required. Install from https://git-scm.com"
    exit 1
}

# Create virtual environment
echo ""
echo "🐍 Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Initialize database
echo ""
echo "🗄️  Initializing database..."
python3 -c "
from core.database import Database
db = Database('control_tower.db')
db.create_tables()
print('Database initialized: control_tower.db')
"

# Create artifacts directory
mkdir -p artifacts

# Initialize demo target repo as a git repo
echo ""
echo "📁 Initializing demo target repository..."
cd demo_target_repo
if [ ! -d ".git" ]; then
    git init
    git add -A
    git commit -m "Initial commit: demo target inventory service"
    echo "Git repository initialized for demo_target_repo"
else
    echo "Git repository already exists"
fi
cd ..

# Seed demo tasks
echo ""
echo "🌱 Seeding demo tasks..."
python3 scripts/seed_tasks.py

# Check Ollama
echo ""
echo "🤖 Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"
    echo "   Available models:"
    ollama list 2>/dev/null || echo "   (Ollama server not running)"
    echo ""
    echo "   To pull recommended model:"
    echo "   ollama pull qwen2.5-coder:7b"
else
    echo "⚠️  Ollama not found. Install from: https://ollama.ai"
    echo "   Then run: ollama pull qwen2.5-coder:7b"
fi

# Docker check
echo ""
echo "🐳 Checking Docker..."
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed"
    docker --version
else
    echo "⚠️  Docker not found (optional). Install from: https://docker.com"
fi

echo ""
echo "======================================================"
echo "✅ Setup complete!"
echo ""
echo "Quick Start:"
echo "  1. Activate venv:    source .venv/bin/activate"
echo "  2. Start Ollama:     ollama serve"
echo "  3. Pull model:       ollama pull qwen2.5-coder:7b"
echo "  4. Start API:        uvicorn apps.api.main:app --reload --port 8000"
echo "  5. Start dashboard:  streamlit run apps/dashboard/app.py"
echo "  6. Seed tasks:       python scripts/seed_tasks.py"
echo "  7. Run benchmark:    python scripts/run_benchmark.py --max-tasks 5"
echo ""
echo "API docs: http://localhost:8000/docs"
echo "Dashboard: http://localhost:8501"
echo "======================================================"
