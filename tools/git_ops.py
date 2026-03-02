"""Git operations — branch management and patch workflows."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitOpsError(Exception):
    """Raised when a Git operation fails."""
    pass


class GitOps:
    """Manages Git operations for the control tower pipeline.

    Uses Git CLI directly for maximum compatibility and transparency.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise GitOpsError(f"Not a Git repository: {repo_path}")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ["git", "-C", str(self.repo_path)] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if check and result.returncode != 0:
                raise GitOpsError(
                    f"Git command failed: {' '.join(args)}\n"
                    f"stderr: {result.stderr}"
                )
            return result
        except subprocess.TimeoutExpired:
            raise GitOpsError(f"Git command timed out: {' '.join(args)}")

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def create_branch(self, branch_name: str, from_branch: str | None = None) -> str:
        """Create and checkout a new branch."""
        if from_branch:
            self._run(["checkout", from_branch])
        self._run(["checkout", "-b", branch_name])
        logger.info(f"Created and checked out branch: {branch_name}")
        return branch_name

    def checkout(self, branch: str):
        """Checkout an existing branch."""
        self._run(["checkout", branch])

    def get_diff(self, staged: bool = False) -> str:
        """Get the current diff."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        result = self._run(args)
        return result.stdout

    def stage_files(self, files: list[str] | None = None):
        """Stage files for commit."""
        if files:
            self._run(["add"] + files)
        else:
            self._run(["add", "-A"])

    def commit(self, message: str) -> str:
        """Create a commit and return the hash."""
        self._run(["commit", "-m", message])
        result = self._run(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def reset_hard(self, ref: str = "HEAD"):
        """Hard reset to a ref."""
        self._run(["reset", "--hard", ref])

    def stash(self):
        """Stash current changes."""
        self._run(["stash"])

    def stash_pop(self):
        """Pop stashed changes."""
        self._run(["stash", "pop"], check=False)

    def get_status(self) -> dict[str, Any]:
        """Get repository status as a structured dict."""
        result = self._run(["status", "--porcelain"], check=False)
        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                status = line[:2].strip()
                filepath = line[3:].strip()
                files.append({"status": status, "path": filepath})

        return {
            "branch": self.get_current_branch(),
            "clean": len(files) == 0,
            "changed_files": files,
        }

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists."""
        result = self._run(
            ["rev-parse", "--verify", branch_name],
            check=False,
        )
        return result.returncode == 0

    def delete_branch(self, branch_name: str, force: bool = False):
        """Delete a branch."""
        flag = "-D" if force else "-d"
        self._run([branch_name, flag, branch_name])

    def get_log(self, n: int = 5) -> list[dict[str, str]]:
        """Get recent commits."""
        result = self._run([
            "log", f"-{n}", "--pretty=format:%H|%s|%an|%ad",
            "--date=short"
        ])
        commits = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                parts = line.split("|", 3)
                commits.append({
                    "hash": parts[0],
                    "message": parts[1] if len(parts) > 1 else "",
                    "author": parts[2] if len(parts) > 2 else "",
                    "date": parts[3] if len(parts) > 3 else "",
                })
        return commits
