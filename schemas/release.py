"""Release Agent schema — recommends deployment gate strategy."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput, GateDecision


class CanaryConfig(BaseModel):
    """Configuration for canary deployment if recommended."""
    duration_seconds: int = 60
    check_interval_seconds: int = 10
    traffic_split_percent: int = 10
    metrics_to_monitor: list[str] = Field(default_factory=list)


class ReleaseInput(BaseModel):
    """Input to the Release Agent."""
    risk_score: float
    risk_level: str
    validation_passed: bool
    validation_summary: dict = Field(default_factory=dict)
    security_block: bool = False
    security_max_severity: str = "INFO"
    reviewer_recommendation: str = ""
    policy_thresholds: dict = Field(default_factory=dict)


class ReleaseOutput(AgentOutput):
    """Structured output from the Release Agent."""
    gate_decision: GateDecision
    decision_reasons: list[str] = Field(default_factory=list)
    canary_config: CanaryConfig | None = None
    required_approvals: list[str] = Field(default_factory=list)
    summary: str = ""
