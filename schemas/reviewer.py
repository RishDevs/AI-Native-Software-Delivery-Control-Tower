"""Reviewer Agent schema — evaluates patch for correctness and alignment."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput, Severity


class ReviewFinding(BaseModel):
    """A single finding from the review."""
    category: str = Field(description="e.g. 'bug', 'edge_case', 'style', 'logic', 'performance'")
    severity: Severity
    file_path: str = ""
    line_range: str = ""
    description: str
    suggestion: str = ""


class ReviewerInput(BaseModel):
    """Input to the Reviewer Agent."""
    task_description: str
    planner_summary: str
    patch_diff: str
    files_changed: list[str] = Field(default_factory=list)
    validation_report: dict | None = None


class ReviewerOutput(AgentOutput):
    """Structured output from the Reviewer Agent."""
    findings: list[ReviewFinding] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count per severity level"
    )
    recommendation: str = Field(
        description="'approve', 'revise', or 'reject'"
    )
    summary: str = Field(
        default="",
        description="Overall review summary"
    )
