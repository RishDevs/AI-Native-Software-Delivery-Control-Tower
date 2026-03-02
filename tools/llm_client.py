"""Ollama LLM client wrapper with structured output validation and retries."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypeVar, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when LLM interaction fails after all retries."""
    pass


class OllamaClient:
    """Client for interacting with Ollama local LLM.

    Features:
    - Structured JSON output with Pydantic validation
    - Automatic retry on malformed output
    - Prompt and output logging
    - Configurable model, temperature, and timeout
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        fallback_model: str = "llama3:8b",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        max_retries: int = 3,
        timeout: int = 120,
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.fallback_model = fallback_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url

    def _call_ollama(self, prompt: str, model: str | None = None) -> str:
        """Make a raw call to Ollama API."""
        import httpx

        target_model = model or self.model

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": target_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")

        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama. Is it running?")
            raise LLMError(
                "Cannot connect to Ollama at "
                f"{self.base_url}. Start Ollama with: ollama serve"
            )
        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise LLMError(f"Ollama request timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            raise LLMError(f"Ollama request failed: {e}")

    def generate(self, prompt: str) -> str:
        """Generate a raw text response from the LLM."""
        return self._call_ollama(prompt)

    def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        retry_prompt_template: str | None = None,
    ) -> tuple[T, int]:
        """Generate a structured response validated against a Pydantic schema.

        Returns:
            Tuple of (validated output, retry count)

        Raises:
            LLMError: If all retries are exhausted without valid output
        """
        # Build schema hint for the prompt
        schema_json = json.dumps(schema_class.model_json_schema(), indent=2)
        full_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: Respond with ONLY a valid JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n\n"
            f"Do not include any text before or after the JSON. "
            f"Do not wrap in markdown code blocks."
        )

        last_error = None
        models_to_try = [self.model, self.fallback_model]

        for model in models_to_try:
            for attempt in range(self.max_retries):
                try:
                    logger.info(
                        f"LLM call: model={model}, attempt={attempt + 1}/{self.max_retries}"
                    )

                    raw_output = self._call_ollama(full_prompt, model=model)

                    # Try to extract JSON from the output
                    json_str = self._extract_json(raw_output)
                    parsed = json.loads(json_str)
                    result = schema_class.model_validate(parsed)

                    logger.info(f"Schema validation passed on attempt {attempt + 1}")
                    return result, attempt

                except (json.JSONDecodeError, ValidationError) as e:
                    last_error = e
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {type(e).__name__}: {e}"
                    )

                    if retry_prompt_template and attempt < self.max_retries - 1:
                        error_msg = str(e)
                        full_prompt = retry_prompt_template.format(
                            original_prompt=prompt,
                            error=error_msg,
                            schema=schema_json,
                        )
                    time.sleep(1)  # Brief backoff

                except LLMError:
                    if model == self.fallback_model:
                        raise
                    logger.warning(f"Model {model} unavailable, trying fallback")
                    break  # Try next model

        raise LLMError(
            f"Failed to get valid structured output after "
            f"{self.max_retries} retries across {len(models_to_try)} models. "
            f"Last error: {last_error}"
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM output, handling common formatting issues."""
        # Try to find JSON in code blocks
        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Try to find raw JSON object
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)

        # Return as-is and let JSON parser handle the error
        return text.strip()

    def check_health(self) -> dict[str, Any]:
        """Check if Ollama is running and the model is available."""
        import httpx

        try:
            with httpx.Client(timeout=10) as client:
                # Check server
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                return {
                    "status": "healthy",
                    "server_url": self.base_url,
                    "available_models": model_names,
                    "primary_model_available": any(
                        self.model in name for name in model_names
                    ),
                    "fallback_model_available": any(
                        self.fallback_model in name for name in model_names
                    ),
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "server_url": self.base_url,
            }
