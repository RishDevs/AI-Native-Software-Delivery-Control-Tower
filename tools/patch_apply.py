"""Patch application module — applies code changes with safety checks."""

from __future__ import annotations

import difflib
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PatchError(Exception):
    """Raised when patch application fails."""
    pass


class PatchApplicator:
    """Applies code patches with safety validation.

    Supports:
    - Direct file writes (small files / whole file replacement)
    - Unified diff application
    - Syntax validation after apply
    - Blocked path enforcement
    """

    def __init__(self, repo_path: str, blocked_paths: list[str] | None = None):
        self.repo_path = Path(repo_path).resolve()
        self.blocked_paths = blocked_paths or []

    def apply_file_changes(
        self,
        changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply a list of file changes.

        Each change dict should have:
        - file_path: relative path
        - action: 'modify', 'create', 'delete'
        - new_content: full new content (for modify/create)
        - diff: unified diff (optional, for modify)

        Returns summary of applied changes.
        """
        results = {
            "applied": [],
            "failed": [],
            "blocked": [],
            "total_lines_changed": 0,
        }

        for change in changes:
            file_path = change.get("file_path", "")
            action = change.get("action", "modify")

            # Check blocked paths
            if self._is_blocked(file_path):
                results["blocked"].append({
                    "file": file_path,
                    "reason": "path blocked by policy",
                })
                logger.warning(f"Blocked: {file_path} (policy)")
                continue

            try:
                full_path = self.repo_path / file_path

                if action == "create":
                    self._create_file(full_path, change.get("new_content", ""))
                    results["applied"].append({"file": file_path, "action": "created"})

                elif action == "modify":
                    new_content = change.get("new_content", "")
                    if new_content:
                        old_content = ""
                        if full_path.exists():
                            old_content = full_path.read_text()
                        self._write_file(full_path, new_content)

                        # Count changed lines
                        old_lines = old_content.split("\n")
                        new_lines = new_content.split("\n")
                        diff = list(difflib.unified_diff(old_lines, new_lines))
                        lines_changed = sum(
                            1 for line in diff
                            if line.startswith("+") or line.startswith("-")
                        )
                        results["total_lines_changed"] += lines_changed
                        results["applied"].append({
                            "file": file_path,
                            "action": "modified",
                            "lines_changed": lines_changed,
                        })
                    else:
                        results["failed"].append({
                            "file": file_path,
                            "reason": "no content provided for modification",
                        })

                elif action == "delete":
                    if full_path.exists():
                        full_path.unlink()
                        results["applied"].append({"file": file_path, "action": "deleted"})
                    else:
                        results["failed"].append({
                            "file": file_path,
                            "reason": "file does not exist",
                        })

            except Exception as e:
                logger.error(f"Failed to apply change to {file_path}: {e}")
                results["failed"].append({
                    "file": file_path,
                    "reason": str(e),
                })

        return results

    def validate_syntax(self, file_path: str) -> dict[str, Any]:
        """Validate Python syntax of a file."""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return {"valid": False, "error": "File not found"}

        if not file_path.endswith(".py"):
            return {"valid": True, "note": "Non-Python file, skipping syntax check"}

        try:
            result = subprocess.run(
                ["python3", "-c", f"import ast; ast.parse(open('{full_path}').read())"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {"valid": True}
            else:
                return {"valid": False, "error": result.stderr}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def generate_unified_diff(
        self,
        original_content: str,
        new_content: str,
        file_path: str,
    ) -> str:
        """Generate a unified diff between original and new content."""
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    def _is_blocked(self, file_path: str) -> bool:
        """Check if a file path is in the blocked list."""
        for blocked in self.blocked_paths:
            if blocked in file_path or file_path.endswith(blocked):
                return True
        return False

    def _create_file(self, full_path: Path, content: str):
        """Create a new file with parent directories."""
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        logger.info(f"Created file: {full_path}")

    def _write_file(self, full_path: Path, content: str):
        """Write content to an existing file."""
        if not full_path.parent.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        logger.info(f"Modified file: {full_path}")
