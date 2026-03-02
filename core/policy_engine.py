"""Policy engine — loads and enforces YAML-based guardrails."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

import yaml


class PolicyLoadError(Exception):
    """Raised when policy parsing fails — system should terminate safely."""
    pass


class PolicyViolation(Exception):
    """Raised when a policy constraint is violated."""

    def __init__(self, rule: str, detail: str = ""):
        self.rule = rule
        self.detail = detail
        super().__init__(f"Policy violation: {rule}. {detail}")


class PolicyEngine:
    """YAML-based policy engine for safe automation.

    Design principles:
    - If policy parsing fails, execution terminates safely.
    - If a policy is ambiguous, the stricter interpretation applies.
    - Fail-safe defaults: block rather than approve when uncertain.
    """

    def __init__(self, policy_path: str = "configs/policy.yaml"):
        self.policy_path = policy_path
        self.policy: dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load and validate policy from YAML file."""
        try:
            path = Path(self.policy_path)
            if not path.exists():
                raise PolicyLoadError(f"Policy file not found: {self.policy_path}")

            with open(path) as f:
                self.policy = yaml.safe_load(f)

            if not isinstance(self.policy, dict):
                raise PolicyLoadError("Policy file must contain a YAML mapping")

        except yaml.YAMLError as e:
            raise PolicyLoadError(f"Failed to parse policy YAML: {e}") from e

    def reload(self):
        """Reload policy from disk."""
        self._load()

    # ── Accessors ─────────────────────────────────────────────

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a policy value using dot-notation path (e.g. 'risk.weights.files_changed')."""
        keys = key_path.split(".")
        value = self.policy
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def autonomous_config(self) -> dict:
        return self.policy.get("autonomous", {})

    @property
    def blocked_paths_config(self) -> dict:
        return self.policy.get("blocked_paths", {})

    @property
    def validation_config(self) -> dict:
        return self.policy.get("validation", {})

    @property
    def risk_config(self) -> dict:
        return self.policy.get("risk", {})

    @property
    def gate_config(self) -> dict:
        return self.policy.get("gate", {})

    @property
    def canary_config(self) -> dict:
        return self.policy.get("canary", {})

    @property
    def rollback_config(self) -> dict:
        return self.policy.get("rollback", {})

    @property
    def llm_config(self) -> dict:
        return self.policy.get("llm", {})

    # ── Enforcement Methods ───────────────────────────────────

    def is_path_blocked(self, file_path: str) -> bool:
        """Check if a file path is blocked by policy."""
        blocked_files = self.blocked_paths_config.get("files", [])
        blocked_dirs = self.blocked_paths_config.get("directories", [])

        # Check file patterns
        for pattern in blocked_files:
            if fnmatch.fnmatch(file_path, pattern):
                return True
            if fnmatch.fnmatch(Path(file_path).name, pattern):
                return True

        # Check directory patterns
        for dir_pattern in blocked_dirs:
            if file_path.startswith(dir_pattern) or f"/{dir_pattern}" in file_path:
                return True

        return False

    def check_file_count(self, count: int) -> bool:
        """Check if number of changed files exceeds limit. Returns True if within limit."""
        max_files = self.autonomous_config.get("max_files_changed", 5)
        return count <= max_files

    def check_patch_size(self, lines: int) -> bool:
        """Check if patch size is within limit. Returns True if within limit."""
        max_lines = self.autonomous_config.get("max_patch_size_lines", 500)
        return lines <= max_lines

    def requires_human_approval(self, changed_paths: list[str]) -> bool:
        """Check if any changed path requires human approval."""
        approval_patterns = self.autonomous_config.get("require_human_approval_for", [])
        for path in changed_paths:
            for pattern in approval_patterns:
                if pattern in path:
                    return True
        return False

    def should_block_security(self, max_severity: str, finding_counts: dict[str, int]) -> bool:
        """Determine if security findings should block deployment."""
        sec_config = self.validation_config.get("security", {})
        block_severities = sec_config.get("block_on_severity", ["HIGH", "CRITICAL"])

        if max_severity in block_severities:
            return True

        max_medium = sec_config.get("max_medium_findings", 3)
        if finding_counts.get("MEDIUM", 0) > max_medium:
            return True

        return False

    def get_risk_weights(self) -> dict[str, float]:
        """Get risk scoring weights."""
        return self.risk_config.get("weights", {})

    def get_risk_thresholds(self) -> dict[str, float]:
        """Get risk level thresholds."""
        return self.risk_config.get("thresholds", {"low": 20, "medium": 50, "high": 100})

    def get_critical_modules(self) -> list[str]:
        """Get list of critical module paths."""
        return self.risk_config.get("critical_modules", [])

    def evaluate_gate_decision(
        self,
        risk_level: str,
        all_validations_pass: bool,
        security_block: bool,
        test_failure: bool,
    ) -> str:
        """Evaluate gate decision based on policy rules.

        Returns: 'approve', 'canary', 'human_review', or 'block'
        """
        rules = self.gate_config.get("rules", [])
        default = self.gate_config.get("default_decision", "block")

        for rule in rules:
            condition = rule.get("condition", "")
            decision = rule.get("decision", default)

            # Simple rule evaluation
            if self._evaluate_condition(
                condition, risk_level, all_validations_pass, security_block, test_failure
            ):
                return decision

        return default

    def _evaluate_condition(
        self,
        condition: str,
        risk_level: str,
        all_validations_pass: bool,
        security_block: bool,
        test_failure: bool,
    ) -> bool:
        """Evaluate a simple policy condition string."""
        context = {
            "risk_level": risk_level,
            "all_validations_pass": all_validations_pass,
            "security_block": security_block,
            "test_failure": test_failure,
        }

        try:
            # Safe evaluation of simple conditions
            # We only support specific patterns
            if "security_block" in condition and security_block:
                return True
            if "test_failure" in condition and test_failure:
                return True

            if "risk_level" in condition:
                for level in ("low", "medium", "high"):
                    if f"'{level}'" in condition and risk_level == level:
                        if "all_validations_pass" in condition:
                            if "not all_validations_pass" in condition:
                                return not all_validations_pass
                            else:
                                return all_validations_pass
                        return True

            return False
        except Exception:
            # Ambiguous → stricter interpretation → block
            return False

    def get_canary_metrics_config(self) -> list[dict]:
        """Get canary metrics monitoring configuration."""
        return self.canary_config.get("metrics", [])

    def get_canary_duration(self) -> int:
        """Get canary duration in seconds."""
        return self.canary_config.get("duration_seconds", 60)

    def get_canary_interval(self) -> int:
        """Get canary check interval in seconds."""
        return self.canary_config.get("check_interval_seconds", 10)

    def auto_rollback_enabled(self) -> bool:
        """Check if automatic rollback is enabled."""
        return self.rollback_config.get("auto_rollback", True)

    def validate_patch_safety(
        self,
        changed_files: list[str],
        patch_lines: int,
    ) -> list[PolicyViolation]:
        """Validate a patch against all safety policies. Returns list of violations."""
        violations = []

        # Check blocked paths
        for fpath in changed_files:
            if self.is_path_blocked(fpath):
                violations.append(PolicyViolation(
                    "blocked_path", f"File '{fpath}' is blocked by policy"
                ))

        # Check file count
        if not self.check_file_count(len(changed_files)):
            max_files = self.autonomous_config.get("max_files_changed", 5)
            violations.append(PolicyViolation(
                "max_files_exceeded",
                f"Changed {len(changed_files)} files (max: {max_files})"
            ))

        # Check patch size
        if not self.check_patch_size(patch_lines):
            max_lines = self.autonomous_config.get("max_patch_size_lines", 500)
            violations.append(PolicyViolation(
                "max_patch_size_exceeded",
                f"Patch has {patch_lines} lines (max: {max_lines})"
            ))

        return violations
