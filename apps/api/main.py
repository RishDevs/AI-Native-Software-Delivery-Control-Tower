"""FastAPI Control Tower API — the control plane for managing tasks and runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.artifacts import ArtifactManager
from core.database import Database
from core.orchestrator import Orchestrator
from core.policy_engine import PolicyEngine
from tools.llm_client import OllamaClient

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("control-tower")

# ── Global instances ──────────────────────────────────────────
db: Database | None = None
policy: PolicyEngine | None = None
artifacts: ArtifactManager | None = None
orchestrator: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown global resources."""
    global db, policy, artifacts, orchestrator

    logger.info("🚀 Initializing Control Tower...")

    db = Database("control_tower.db")
    db.create_tables()

    policy = PolicyEngine("configs/policy.yaml")
    artifacts = ArtifactManager("./artifacts", db)

    llm = OllamaClient(
        model=policy.get("llm.model", "qwen2.5-coder:7b"),
        fallback_model=policy.get("llm.fallback_model", "llama3:8b"),
        temperature=policy.get("llm.temperature", 0.2),
        max_tokens=policy.get("llm.max_tokens", 4096),
        max_retries=policy.get("llm.max_retries", 3),
        timeout=policy.get("llm.timeout_seconds", 120),
    )

    orchestrator = Orchestrator(db, policy, artifacts, llm)

    logger.info("✅ Control Tower initialized successfully")
    yield
    logger.info("👋 Control Tower shutting down...")


# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title="AI-Native Software Delivery Control Tower",
    description=(
        "Agentic Code Changes, Risk-Aware CI/CD Gating, "
        "and Observability-Driven Rollbacks"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ───────────────────────────────────

class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    repo_path: str = Field(min_length=1)
    policy_path: str = Field(default="configs/policy.yaml")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateRunRequest(BaseModel):
    task_id: str


class ApproveRunRequest(BaseModel):
    approved: bool = True
    approver: str = "human"
    notes: str = ""


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    repo_path: str
    status: str
    created_at: str


class RunResponse(BaseModel):
    id: str
    task_id: str
    status: str
    current_state: str
    started_at: str | None
    finished_at: str | None
    error_message: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    version: str
    ollama: dict[str, Any]
    database: str
    policy_loaded: bool


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/", tags=["info"])
async def root():
    """API root with basic info."""
    return {
        "name": "AI-Native Software Delivery Control Tower",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["info"])
async def health_check():
    """Check system health including Ollama, database, and policy."""
    llm = OllamaClient()
    ollama_health = llm.check_health()

    return HealthResponse(
        status="healthy" if ollama_health.get("status") == "healthy" else "degraded",
        version="0.1.0",
        ollama=ollama_health,
        database="connected" if db else "disconnected",
        policy_loaded=policy is not None,
    )


# ── Task Endpoints ────────────────────────────────────────────

@app.post("/tasks", response_model=TaskResponse, tags=["tasks"])
async def create_task(request: CreateTaskRequest):
    """Create a new engineering task."""
    task = db.create_task(
        title=request.title,
        description=request.description,
        repo_path=request.repo_path,
        policy_path=request.policy_path,
        metadata=request.metadata,
    )
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        repo_path=task.repo_path,
        status=task.status,
        created_at=str(task.created_at),
    )


@app.get("/tasks", tags=["tasks"])
async def list_tasks(limit: int = 50):
    """List all tasks."""
    tasks = db.list_tasks(limit=limit)
    return [
        TaskResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            repo_path=t.repo_path,
            status=t.status,
            created_at=str(t.created_at),
        )
        for t in tasks
    ]


@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
async def get_task(task_id: str):
    """Get a specific task."""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        repo_path=task.repo_path,
        status=task.status,
        created_at=str(task.created_at),
    )


# ── Run Endpoints ─────────────────────────────────────────────

@app.post("/runs", tags=["runs"])
async def create_run(request: CreateRunRequest, background_tasks: BackgroundTasks):
    """Start a control tower run for a task."""
    task = db.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    run = db.create_run(task.id)

    # Execute run in background
    background_tasks.add_task(
        orchestrator.execute_run,
        run_id=run.id,
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        repo_path=task.repo_path,
    )

    return {
        "run_id": run.id,
        "task_id": task.id,
        "status": "started",
        "message": "Run started in background. Poll GET /runs/{run_id} for status.",
    }


@app.get("/runs/{run_id}", tags=["runs"])
async def get_run(run_id: str):
    """Get run status and summary."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get associated data
    validations = db.get_validation_results(run_id)
    artifacts_list = db.get_artifacts(run_id)

    return {
        "id": run.id,
        "task_id": run.task_id,
        "status": run.status,
        "current_state": run.current_state,
        "started_at": str(run.started_at) if run.started_at else None,
        "finished_at": str(run.finished_at) if run.finished_at else None,
        "error_message": run.error_message,
        "validations": [
            {
                "tool": v.tool_name,
                "status": v.status,
                "passed": bool(v.passed),
                "duration": v.duration_seconds,
                "summary": v.summary,
            }
            for v in validations
        ],
        "artifacts_count": len(artifacts_list),
    }


@app.get("/runs", tags=["runs"])
async def list_runs(task_id: str | None = None, limit: int = 50):
    """List runs, optionally filtered by task."""
    runs = db.list_runs(task_id=task_id, limit=limit)
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "status": r.status,
            "current_state": r.current_state,
            "started_at": str(r.started_at) if r.started_at else None,
            "finished_at": str(r.finished_at) if r.finished_at else None,
        }
        for r in runs
    ]


@app.get("/runs/{run_id}/artifacts", tags=["runs"])
async def get_run_artifacts(run_id: str):
    """List all artifacts for a run."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    artifact_rows = db.get_artifacts(run_id)
    fs_artifacts = artifacts.list_artifacts(run_id)

    return {
        "run_id": run_id,
        "db_artifacts": [
            {
                "id": a.id,
                "type": a.artifact_type,
                "path": a.file_path,
                "created_at": str(a.created_at),
            }
            for a in artifact_rows
        ],
        "filesystem_artifacts": fs_artifacts,
    }


@app.post("/runs/{run_id}/approve", tags=["runs"])
async def approve_run(run_id: str, request: ApproveRunRequest, background_tasks: BackgroundTasks):
    """Approve a run that is awaiting human review."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (current status: {run.status})"
        )

    if request.approved:
        db.update_run_status(run_id, "deploying", "deploying")
        return {
            "run_id": run_id,
            "status": "approved",
            "message": "Run approved — proceeding to deployment",
        }
    else:
        db.update_run_status(
            run_id, "blocked", "blocked",
            error=f"Rejected by {request.approver}: {request.notes}"
        )
        return {
            "run_id": run_id,
            "status": "rejected",
            "message": "Run rejected by human reviewer",
        }


@app.post("/runs/{run_id}/rollback", tags=["runs"])
async def rollback_run(run_id: str):
    """Manually trigger a rollback for a run."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    db.update_run_status(run_id, "rolling_back", "rolling_back")

    # Record the manual rollback
    db.create_incident(
        run_id=run_id,
        anomaly_detected=False,
        action_taken="manual_rollback",
        summary="Manual rollback triggered via API",
    )

    db.update_run_status(run_id, "completed", "completed")

    return {
        "run_id": run_id,
        "status": "rolled_back",
        "message": "Manual rollback completed",
    }


# ── Policy Endpoints ──────────────────────────────────────────

@app.get("/policies", tags=["policies"])
async def get_policies():
    """Get current policy configuration."""
    return policy.policy


# ── Metrics Endpoint ──────────────────────────────────────────

@app.get("/metrics/summary", tags=["metrics"])
async def get_metrics_summary():
    """Get aggregated metrics summary."""
    all_runs = db.list_runs(limit=1000)

    total = len(all_runs)
    completed = sum(1 for r in all_runs if r.status == "completed")
    failed = sum(1 for r in all_runs if r.status == "failed")
    blocked = sum(1 for r in all_runs if r.status == "blocked")

    return {
        "total_runs": total,
        "completed": completed,
        "failed": failed,
        "blocked": blocked,
        "success_rate": completed / total if total > 0 else 0,
    }
