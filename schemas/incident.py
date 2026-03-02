"""Incident Agent schema — summarizes anomalies and recommends action."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput


class MetricSummary(BaseModel):
    """Summary of a single monitored metric."""
    name: str
    baseline_value: float
    canary_value: float
    threshold: float
    breached: bool
    breach_count: int = 0
    delta_percent: float = 0.0


class IncidentInput(BaseModel):
    """Input to the Incident Agent."""
    baseline_metrics: dict = Field(default_factory=dict)
    canary_metrics: dict = Field(default_factory=dict)
    patch_summary: str = ""
    threshold_breaches: list[dict] = Field(default_factory=list)
    deployment_id: str = ""


class IncidentOutput(AgentOutput):
    """Structured output from the Incident Agent."""
    anomaly_detected: bool = False
    metrics_summary: list[MetricSummary] = Field(default_factory=list)
    probable_causes: list[str] = Field(default_factory=list)
    action_recommendation: str = Field(
        default="monitor",
        description="'rollback', 'monitor', 'investigate', 'ignore'"
    )
    rollback_triggered: bool = False
    incident_summary: str = ""
    postmortem_draft: str = ""
