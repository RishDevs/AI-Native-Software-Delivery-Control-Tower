"""Code Agent — generates code patches from planner output."""

from __future__ import annotations

import logging
from typing import Any

from schemas.coder import CoderInput, CoderOutput
from tools.llm_client import OllamaClient

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are an expert code modification agent. Given an implementation plan and file contents, generate precise code changes.

Your code changes should:
1. Implement ONLY the changes specified in the plan
2. Maintain existing code style and conventions
3. Preserve all existing functionality (no regressions)
4. Include proper error handling
5. Be minimal — change only what's necessary

CRITICAL RULES:
- Each file change must include the complete new file content
- Do NOT modify files not listed in the plan
- Do NOT introduce unnecessary dependencies
- Respect blocked path restrictions
- Keep changes focused and small

For each file, provide:
- file_path: relative path from repo root
- action: "modify", "create", or "delete"
- new_content: the COMPLETE new file content

RESPOND WITH ONLY valid JSON matching the required schema.
"""


class CoderAgent:
    """Agent that generates code patches aligned with an implementation plan."""

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def generate_patch(self, input_data: CoderInput) -> tuple[CoderOutput, int]:
        """Generate code changes based on plan and file contents.

        Returns:
            Tuple of (CoderOutput, retry_count)
        """
        prompt = self._build_prompt(input_data)
        logger.info(f"Code agent processing: {input_data.task_summary[:80]}")

        output, retries = self.llm.generate_structured(
            prompt=prompt,
            schema_class=CoderOutput,
            retry_prompt_template=(
                "The previous response was not valid JSON.\n"
                "Error: {error}\n\n"
                "Original request:\n{original_prompt}\n\n"
                "Please respond with ONLY valid JSON matching the schema:\n{schema}"
            ),
        )

        # Post-process: count files and lines
        output.files_count = len(output.files_changed)
        total_lines = sum(
            len(fc.new_content.split("\n")) for fc in output.files_changed
        )
        output.total_lines_changed = total_lines

        logger.info(
            f"Patch generated: {output.files_count} files, "
            f"~{output.total_lines_changed} lines, "
            f"confidence={output.confidence:.2f}"
        )
        return output, retries

    def _build_prompt(self, data: CoderInput) -> str:
        """Build the code generation prompt."""
        # Format implementation steps
        steps_str = ""
        for i, step in enumerate(data.implementation_steps, 1):
            desc = step.get("description", "")
            target = step.get("target_files", [])
            steps_str += f"\n{i}. {desc}"
            if target:
                steps_str += f"   Files: {', '.join(target)}"

        # Format target files
        files_str = ""
        for file_info in data.target_files:
            path = file_info.get("path", "unknown")
            content = file_info.get("content", "")
            # Limit content size to avoid overwhelming the model
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"
            files_str += f"\n### {path}\n```\n{content}\n```\n"

        # Format blocked paths
        blocked_str = ", ".join(data.blocked_paths) if data.blocked_paths else "None"

        return f"""{CODER_SYSTEM_PROMPT}

## Task Summary
{data.task_summary}

## Implementation Steps
{steps_str}

## Current File Contents
{files_str}

## Constraints
- Maximum files to change: {data.max_files}
- Maximum patch size: {data.max_patch_lines} lines
- Blocked paths: {blocked_str}
- Style rules: {', '.join(data.style_rules) if data.style_rules else 'Follow existing style'}

Generate the code changes as JSON.
"""
