"""Shared base models and enumerations used across all schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────

class RunStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    CODING = "coding"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    RISK_SCORING = "risk_scoring"
    GATING = "gating"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GateDecision(str, Enum):
    APPROVE = "approve"
    CANARY = "canary"
    HUMAN_REVIEW = "human_review"
    BLOCK = "block"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    INFO = "INFO"


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ArtifactType(str, Enum):
    PLAN = "plan"
    PATCH = "patch"
    VALIDATION_REPORT = "validation_report"
    REVIEW = "review"
    SECURITY_REPORT = "security_report"
    RISK_ASSESSMENT = "risk_assessment"
    GATE_DECISION = "gate_decision"
    CANARY_REPORT = "canary_report"
    INCIDENT_REPORT = "incident_report"
    POSTMORTEM = "postmortem"
    LOG = "log"
    PROMPT = "prompt"
    RAW_LLM_OUTPUT = "raw_llm_output"


# ── Base Models ───────────────────────────────────────────────

class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentOutput(BaseModel):
    """Base model for all agent outputs with common fields."""
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Agent's confidence in the output quality (0.0 to 1.0)"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes, warnings, or observations"
    )


class TaskInput(BaseModel):
    """Input for creating a new engineering task."""
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    repo_path: str = Field(min_length=1)
    policy_path: str = Field(default="configs/policy.yaml")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(TimestampedModel):
    """Stored task record."""
    id: str
    title: str
    description: str
    repo_path: str
    policy_path: str
    status: str = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunRecord(TimestampedModel):
    """Stored run record."""
    id: str
    task_id: str
    status: RunStatus = RunStatus.PENDING
    current_state: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(TimestampedModel):
    """Stored artifact record."""
    id: str
    run_id: str
    artifact_type: ArtifactType
    file_path: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
