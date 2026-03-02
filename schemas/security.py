"""Security Agent schema — aggregates security tool findings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput, Severity


class SecurityFinding(BaseModel):
    """A single security finding."""
    tool: str = Field(description="e.g. 'bandit', 'pip-audit', 'semgrep'")
    rule_id: str = ""
    severity: Severity
    file_path: str = ""
    line_number: int | None = None
    description: str
    remediation: str = ""
    cwe: str = ""


class SecurityInput(BaseModel):
    """Input to the Security Agent."""
    bandit_results: dict = Field(default_factory=dict)
    pip_audit_results: dict = Field(default_factory=dict)
    patch_diff: str = ""
    changed_files: list[str] = Field(default_factory=list)


class SecurityOutput(AgentOutput):
    """Structured output from the Security Agent."""
    findings: list[SecurityFinding] = Field(default_factory=list)
    max_severity: Severity = Severity.INFO
    total_findings: int = 0
    block_recommended: bool = False
    remediation_notes: list[str] = Field(default_factory=list)
    summary: str = ""
