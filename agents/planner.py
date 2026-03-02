"""Planner Agent — transforms ticket + repo context into an execution plan."""

from __future__ import annotations

import logging
from typing import Any

from schemas.planner import PlannerInput, PlannerOutput
from tools.llm_client import OllamaClient

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are an expert software engineering planning agent. Given an engineering task and repository context, produce a detailed implementation plan.

Your plan should:
1. Summarize the task concisely
2. List assumptions about the codebase
3. Identify which files need to be modified
4. Provide ordered implementation steps
5. Define a test strategy
6. Estimate the risk level (low/medium/high)

CRITICAL RULES:
- Do NOT issue direct file modifications — only plan
- Identify uncertainty explicitly
- Be specific about file paths and function names
- Consider edge cases and potential breaking changes

RESPOND WITH ONLY valid JSON matching the required schema.
"""


class PlannerAgent:
    """Agent that generates implementation plans from engineering tasks."""

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def plan(self, input_data: PlannerInput) -> tuple[PlannerOutput, int]:
        """Generate an implementation plan.

        Returns:
            Tuple of (PlannerOutput, retry_count)
        """
        prompt = self._build_prompt(input_data)
        logger.info(f"Planner processing task: {input_data.task_title}")

        output, retries = self.llm.generate_structured(
            prompt=prompt,
            schema_class=PlannerOutput,
            retry_prompt_template=(
                "The previous response was not valid JSON.\n"
                "Error: {error}\n\n"
                "Original request:\n{original_prompt}\n\n"
                "Please respond with ONLY valid JSON matching the schema:\n{schema}"
            ),
        )

        logger.info(
            f"Plan generated: {len(output.implementation_steps)} steps, "
            f"risk={output.estimated_risk.value}, "
            f"confidence={output.confidence:.2f}"
        )
        return output, retries

    def _build_prompt(self, data: PlannerInput) -> str:
        """Build the planning prompt."""
        file_tree_str = "\n".join(data.file_tree[:100])  # Limit tree size
        modules_str = ", ".join(data.key_modules[:20])

        return f"""{PLANNER_SYSTEM_PROMPT}

## Engineering Task
**Title:** {data.task_title}
**Description:** {data.task_description}

## Repository Context
- **Language:** {data.language}
- **Key modules:** {modules_str}

### File Tree (truncated):
```
{file_tree_str}
```

## Policy Constraints
{self._format_constraints(data.policy_constraints)}

Generate a detailed implementation plan as JSON.
"""

    def _format_constraints(self, constraints: dict) -> str:
        """Format policy constraints for the prompt."""
        if not constraints:
            return "- No additional constraints"

        lines = []
        for key, value in constraints.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
