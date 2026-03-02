"""Reviewer Agent — evaluates patch correctness and alignment."""

from __future__ import annotations

import logging
from typing import Any

from schemas.reviewer import ReviewerInput, ReviewerOutput
from tools.llm_client import OllamaClient

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are an expert code reviewer. Evaluate the given patch for correctness, edge cases, and alignment with the original task requirements.

Your review should:
1. Check for logic errors and bugs
2. Identify missing edge cases
3. Verify the patch addresses the task requirements
4. Assess code quality and maintainability
5. Flag potential performance issues
6. Check for security concerns

For each finding, assign a severity:
- INFO: Minor style/documentation suggestions
- LOW: Non-critical quality improvements
- MEDIUM: Potential issues that should be addressed
- HIGH: Likely bugs or significant problems
- CRITICAL: Breaking changes or security vulnerabilities

Provide a recommendation: 'approve', 'revise', or 'reject'

RESPOND WITH ONLY valid JSON matching the required schema.
"""


class ReviewerAgent:
    """Agent that reviews code patches for quality and correctness."""

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def review(self, input_data: ReviewerInput) -> tuple[ReviewerOutput, int]:
        """Review a code patch.

        Returns:
            Tuple of (ReviewerOutput, retry_count)
        """
        prompt = self._build_prompt(input_data)
        logger.info("Reviewer evaluating patch...")

        output, retries = self.llm.generate_structured(
            prompt=prompt,
            schema_class=ReviewerOutput,
            retry_prompt_template=(
                "The previous response was not valid JSON.\n"
                "Error: {error}\n\n"
                "Original request:\n{original_prompt}\n\n"
                "Please respond with ONLY valid JSON matching the schema:\n{schema}"
            ),
        )

        # Post-process: compute severity counts
        counts: dict[str, int] = {}
        for finding in output.findings:
            sev = finding.severity.value
            counts[sev] = counts.get(sev, 0) + 1
        output.severity_counts = counts

        logger.info(
            f"Review complete: {len(output.findings)} findings, "
            f"recommendation={output.recommendation}, "
            f"confidence={output.confidence:.2f}"
        )
        return output, retries

    def _build_prompt(self, data: ReviewerInput) -> str:
        """Build the review prompt."""
        diff = data.patch_diff
        if len(diff) > 5000:
            diff = diff[:5000] + "\n... (diff truncated)"

        return f"""{REVIEWER_SYSTEM_PROMPT}

## Original Task
{data.task_description}

## Planner Summary
{data.planner_summary}

## Files Changed
{', '.join(data.files_changed)}

## Patch Diff
```diff
{diff}
```

Review the patch and respond with JSON.
"""
