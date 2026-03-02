"""Artifact manager — stores and retrieves run artifacts."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.database import Database


class ArtifactManager:
    """Manages artifact storage on the filesystem and metadata in SQLite."""

    def __init__(self, base_dir: str = "./artifacts", db: Database | None = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db = db

    def _run_dir(self, run_id: str) -> Path:
        """Get the artifact directory for a specific run."""
        d = self.base_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store(
        self,
        run_id: str,
        artifact_type: str,
        content: str | dict | list,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store an artifact and return its file path."""
        run_dir = self._run_dir(run_id)

        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            ext = ".json" if isinstance(content, (dict, list)) else ".txt"
            filename = f"{artifact_type}_{timestamp}{ext}"

        file_path = run_dir / filename

        if isinstance(content, (dict, list)):
            with open(file_path, "w") as f:
                json.dump(content, f, indent=2, default=str)
        else:
            with open(file_path, "w") as f:
                f.write(str(content))

        # Store metadata in DB if available
        if self.db:
            self.db.store_artifact(
                run_id=run_id,
                artifact_type=artifact_type,
                file_path=str(file_path),
                metadata=metadata,
            )

        return str(file_path)

    def store_prompt(self, run_id: str, agent_name: str, prompt: str) -> str:
        """Store an LLM prompt as an artifact."""
        return self.store(
            run_id=run_id,
            artifact_type="prompt",
            content=prompt,
            filename=f"prompt_{agent_name}.txt",
        )

    def store_llm_output(self, run_id: str, agent_name: str, output: str) -> str:
        """Store raw LLM output as an artifact."""
        return self.store(
            run_id=run_id,
            artifact_type="raw_llm_output",
            content=output,
            filename=f"llm_output_{agent_name}.txt",
        )

    def store_diff(self, run_id: str, diff_content: str) -> str:
        """Store a patch diff."""
        return self.store(
            run_id=run_id,
            artifact_type="patch",
            content=diff_content,
            filename="patch.diff",
        )

    def store_report(self, run_id: str, report_type: str, report: dict) -> str:
        """Store a JSON report."""
        return self.store(
            run_id=run_id,
            artifact_type=report_type,
            content=report,
            filename=f"{report_type}.json",
        )

    def load(self, file_path: str) -> str | dict:
        """Load an artifact from disk."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {file_path}")

        if path.suffix == ".json":
            with open(path) as f:
                return json.load(f)
        else:
            with open(path) as f:
                return f.read()

    def list_artifacts(self, run_id: str) -> list[dict[str, str]]:
        """List all artifacts for a run."""
        run_dir = self._run_dir(run_id)
        artifacts = []
        for fpath in sorted(run_dir.iterdir()):
            if fpath.is_file():
                artifacts.append({
                    "filename": fpath.name,
                    "path": str(fpath),
                    "size_bytes": fpath.stat().st_size,
                    "type": self._infer_type(fpath.name),
                })
        return artifacts

    def _infer_type(self, filename: str) -> str:
        """Infer artifact type from filename."""
        if "prompt" in filename:
            return "prompt"
        if "llm_output" in filename:
            return "raw_llm_output"
        if "patch" in filename or "diff" in filename:
            return "patch"
        if "validation" in filename:
            return "validation_report"
        if "risk" in filename:
            return "risk_assessment"
        if "incident" in filename:
            return "incident_report"
        if "review" in filename:
            return "review"
        return "other"
