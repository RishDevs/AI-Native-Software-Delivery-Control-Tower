"""Validation pipeline runners — pytest, ruff, mypy, bandit, pip-audit."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from schemas.validation import ValidationToolResult, ValidationReport, ValidationStatus

logger = logging.getLogger(__name__)


class ValidationRunner:
    """Runs a single validation tool and captures structured results."""

    def __init__(self, repo_path: str, artifacts_dir: str = "./artifacts"):
        self.repo_path = Path(repo_path).resolve()
        self.artifacts_dir = Path(artifacts_dir)

    def _run_tool(
        self,
        tool_name: str,
        cmd: list[str],
        timeout: int = 120,
    ) -> ValidationToolResult:
        """Run a validation tool and return structured result."""
        start = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.repo_path),
            )

            duration = time.time() - start
            passed = result.returncode == 0

            return ValidationToolResult(
                tool_name=tool_name,
                status=ValidationStatus.PASSED if passed else ValidationStatus.FAILED,
                passed=passed,
                return_code=result.returncode,
                duration_seconds=round(duration, 2),
                summary=self._summarize_output(tool_name, result.stdout, result.stderr),
                raw_output=result.stdout[:5000],
                findings_count=self._count_findings(tool_name, result.stdout),
            )

        except subprocess.TimeoutExpired:
            return ValidationToolResult(
                tool_name=tool_name,
                status=ValidationStatus.ERROR,
                passed=False,
                return_code=-1,
                duration_seconds=timeout,
                summary=f"{tool_name} timed out after {timeout}s",
            )
        except FileNotFoundError:
            return ValidationToolResult(
                tool_name=tool_name,
                status=ValidationStatus.SKIPPED,
                passed=False,
                return_code=-1,
                duration_seconds=0.0,
                summary=f"{tool_name} not found — install with pip",
            )
        except Exception as e:
            return ValidationToolResult(
                tool_name=tool_name,
                status=ValidationStatus.ERROR,
                passed=False,
                return_code=-1,
                duration_seconds=time.time() - start,
                summary=f"{tool_name} error: {str(e)}",
            )

    def run_pytest(self) -> ValidationToolResult:
        """Run pytest test suite."""
        return self._run_tool(
            "pytest",
            ["python3", "-m", "pytest", "-v", "--tb=short", "-q"],
        )

    def run_ruff(self) -> ValidationToolResult:
        """Run ruff linter."""
        return self._run_tool(
            "ruff",
            ["python3", "-m", "ruff", "check", "."],
        )

    def run_mypy(self) -> ValidationToolResult:
        """Run mypy type checker."""
        return self._run_tool(
            "mypy",
            ["python3", "-m", "mypy", ".", "--ignore-missing-imports"],
            timeout=180,
        )

    def run_bandit(self) -> ValidationToolResult:
        """Run bandit security scanner."""
        return self._run_tool(
            "bandit",
            ["python3", "-m", "bandit", "-r", ".", "-f", "json", "-q"],
        )

    def run_pip_audit(self) -> ValidationToolResult:
        """Run pip-audit dependency vulnerability scanner."""
        return self._run_tool(
            "pip-audit",
            ["python3", "-m", "pip_audit", "--format", "json"],
            timeout=120,
        )

    def _summarize_output(self, tool: str, stdout: str, stderr: str) -> str:
        """Create a brief summary from tool output."""
        output = stdout or stderr
        lines = output.strip().split("\n")

        if tool == "pytest":
            # Look for the summary line
            for line in reversed(lines):
                if "passed" in line or "failed" in line or "error" in line:
                    return line.strip()
            return lines[-1] if lines else "No output"

        if tool == "ruff":
            if not output.strip():
                return "No lint issues found"
            count = len([l for l in lines if l.strip() and ":" in l])
            return f"{count} lint issue(s) found"

        if tool == "mypy":
            for line in reversed(lines):
                if "error" in line.lower() or "success" in line.lower():
                    return line.strip()
            return lines[-1] if lines else "No output"

        if tool == "bandit":
            try:
                data = json.loads(stdout)
                results = data.get("results", [])
                return f"{len(results)} security issue(s) found"
            except (json.JSONDecodeError, AttributeError):
                return lines[-1] if lines else "No output"

        return lines[-1] if lines else "No output"

    def _count_findings(self, tool: str, stdout: str) -> int:
        """Count the number of findings from tool output."""
        if not stdout.strip():
            return 0

        try:
            if tool == "bandit":
                data = json.loads(stdout)
                return len(data.get("results", []))
            elif tool == "ruff":
                return len([l for l in stdout.split("\n") if l.strip() and ":" in l])
            elif tool == "pytest":
                for line in reversed(stdout.split("\n")):
                    if "failed" in line:
                        import re
                        match = re.search(r"(\d+) failed", line)
                        return int(match.group(1)) if match else 0
                return 0
        except Exception:
            return 0

        return 0


class ValidationPipeline:
    """Orchestrates the full validation pipeline."""

    def __init__(self, repo_path: str, artifacts_dir: str = "./artifacts"):
        self.runner = ValidationRunner(repo_path, artifacts_dir)

    def run_all(self, run_id: str = "") -> ValidationReport:
        """Run all validation stages and produce a consolidated report."""
        start = time.time()
        results: list[ValidationToolResult] = []

        # Run all validation tools
        logger.info("Running validation pipeline...")

        stages = [
            ("ruff", self.runner.run_ruff),
            ("mypy", self.runner.run_mypy),
            ("pytest", self.runner.run_pytest),
            ("bandit", self.runner.run_bandit),
            ("pip-audit", self.runner.run_pip_audit),
        ]

        for name, runner_fn in stages:
            logger.info(f"  Running {name}...")
            result = runner_fn()
            results.append(result)
            logger.info(f"  {name}: {result.status.value} ({result.duration_seconds:.1f}s)")

        total_duration = time.time() - start
        all_passed = all(
            r.passed or r.status == ValidationStatus.SKIPPED for r in results
        )
        blocking = [
            r.tool_name for r in results
            if not r.passed and r.status != ValidationStatus.SKIPPED
        ]

        # Build summary
        summary_parts = []
        for r in results:
            status_icon = "✅" if r.passed else "❌" if r.status == ValidationStatus.FAILED else "⚠️"
            summary_parts.append(f"{status_icon} {r.tool_name}: {r.summary}")

        return ValidationReport(
            run_id=run_id,
            all_passed=all_passed,
            results=results,
            total_duration_seconds=round(total_duration, 2),
            summary="\n".join(summary_parts),
            blocking_failures=blocking,
        )
