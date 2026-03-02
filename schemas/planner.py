"""Planner Agent schema — transforms ticket + repo context into execution plan."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput, RiskLevel


class ImplementationStep(BaseModel):
    """A single step in the implementation plan."""
    step_number: int
    description: str
    target_files: list[str] = Field(default_factory=list)
    action: str = Field(description="e.g. 'modify', 'create', 'delete', 'test'")
    rationale: str = ""


class TestStrategy(BaseModel):
    """Test approach for validating the implementation."""
    approach: str = Field(description="Overall test strategy description")
    test_files: list[str] = Field(default_factory=list)
    test_types: list[str] = Field(default_factory=list, description="e.g. unit, integration")
    coverage_targets: list[str] = Field(default_factory=list)


class PlannerInput(BaseModel):
    """Input to the Planner Agent."""
    task_title: str
    task_description: str
    repo_summary: dict = Field(default_factory=dict)
    file_tree: list[str] = Field(default_factory=list)
    key_modules: list[str] = Field(default_factory=list)
    language: str = "python"
    policy_constraints: dict = Field(default_factory=dict)


class PlannerOutput(AgentOutput):
    """Structured output from the Planner Agent."""
    task_summary: str = Field(description="Concise summary of what needs to be done")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made about the codebase or task"
    )
    candidate_files: list[str] = Field(
        description="Files likely to be edited"
    )
    implementation_steps: list[ImplementationStep] = Field(
        description="Ordered steps to implement the change"
    )
    test_strategy: TestStrategy = Field(
        description="How to validate the implementation"
    )
    estimated_risk: RiskLevel = Field(
        description="Estimated risk level of this change"
    )
    estimated_complexity: str = Field(
        default="medium",
        description="low, medium, high"
    )
