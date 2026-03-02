"""Validation pipeline schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import ValidationStatus


class ValidationToolResult(BaseModel):
    """Result from a single validation tool run."""
    tool_name: str
    status: ValidationStatus
    passed: bool
    return_code: int = 0
    duration_seconds: float = 0.0
    summary: str = ""
    findings_count: int = 0
    stdout_path: str = ""
    stderr_path: str = ""
    raw_output: str = ""


class ValidationReport(BaseModel):
    """Consolidated validation report across all tools."""
    run_id: str
    all_passed: bool = False
    results: list[ValidationToolResult] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    summary: str = ""
    blocking_failures: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Output from the risk scoring engine."""
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: str
    contributing_factors: list[dict] = Field(default_factory=list)
    explanation: str = ""
    gate_recommendation: str = ""
