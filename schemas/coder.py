"""Code Agent schema — generates patches aligned with planner output."""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.common import AgentOutput


class FileChange(BaseModel):
    """A single file modification."""
    file_path: str
    action: str = Field(description="'modify', 'create', or 'delete'")
    original_content: str = Field(default="", description="Original content (for modify)")
    new_content: str = Field(default="", description="New content after change")
    diff: str = Field(default="", description="Unified diff of the change")


class CoderInput(BaseModel):
    """Input to the Code Agent."""
    task_summary: str
    implementation_steps: list[dict] = Field(default_factory=list)
    target_files: list[dict] = Field(
        default_factory=list,
        description="List of {path: str, content: str} for files to modify"
    )
    style_rules: list[str] = Field(default_factory=list)
    blocked_paths: list[str] = Field(default_factory=list)
    max_files: int = 5
    max_patch_lines: int = 500


class CoderOutput(AgentOutput):
    """Structured output from the Code Agent."""
    files_changed: list[FileChange] = Field(
        description="List of file changes"
    )
    patch_diff: str = Field(
        default="",
        description="Combined unified diff of all changes"
    )
    rationale: str = Field(
        default="",
        description="Explanation of the approach taken"
    )
    unresolved_issues: list[str] = Field(
        default_factory=list,
        description="Known issues not addressed in this patch"
    )
    files_count: int = Field(
        default=0,
        description="Number of files changed"
    )
    total_lines_changed: int = Field(
        default=0,
        description="Total lines added + removed"
    )
