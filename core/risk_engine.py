"""Risk scoring engine — transparent, rule-based, configurable."""

from __future__ import annotations

from typing import Any

from core.policy_engine import PolicyEngine
from schemas.validation import RiskAssessment


class RiskEngine:
    """Computes deployment risk using weighted rule-based scoring.

    Key properties:
    - Transparent: every contributing factor is listed with its weight
    - Configurable: weights and thresholds come from policy
    - Reproducible: same inputs always produce the same score
    - Explainable: output includes human-readable explanation
    """

    def __init__(self, policy: PolicyEngine):
        self.policy = policy
        self.weights = policy.get_risk_weights()
        self.thresholds = policy.get_risk_thresholds()
        self.critical_modules = policy.get_critical_modules()

    def compute(
        self,
        files_changed: int = 0,
        changed_paths: list[str] | None = None,
        test_passed: bool = True,
        lint_passed: bool = True,
        type_check_passed: bool = True,
        security_findings: dict[str, int] | None = None,
        reviewer_severity_counts: dict[str, int] | None = None,
        agent_confidence: float = 1.0,
        patch_lines: int = 0,
        coverage_delta: float = 0.0,
    ) -> RiskAssessment:
        """Compute risk score and return assessment with full explainability."""
        factors: list[dict[str, Any]] = []
        score = 0.0

        changed_paths = changed_paths or []
        security_findings = security_findings or {}
        reviewer_severity_counts = reviewer_severity_counts or {}

        # ── Files changed ─────────────────────────────────────
        w = self.weights.get("files_changed", 10)
        if files_changed > 1:
            penalty = (files_changed - 1) * w
            score += penalty
            factors.append({
                "factor": "files_changed",
                "value": files_changed,
                "weight": w,
                "penalty": penalty,
                "detail": f"{files_changed} files changed (penalty per file beyond 1)",
            })

        # ── Critical module touched ──────────────────────────
        w = self.weights.get("critical_module", 20)
        critical_touched = any(
            any(cm in path for cm in self.critical_modules)
            for path in changed_paths
        )
        if critical_touched:
            score += w
            factors.append({
                "factor": "critical_module",
                "value": True,
                "weight": w,
                "penalty": w,
                "detail": "Critical module path detected in changed files",
            })

        # ── Test failure ──────────────────────────────────────
        w = self.weights.get("test_failure", 30)
        if not test_passed:
            score += w
            factors.append({
                "factor": "test_failure",
                "value": True,
                "weight": w,
                "penalty": w,
                "detail": "One or more tests failed",
            })

        # ── Lint failure ──────────────────────────────────────
        w = self.weights.get("lint_failure", 10)
        if not lint_passed:
            score += w
            factors.append({
                "factor": "lint_failure",
                "value": True,
                "weight": w,
                "penalty": w,
                "detail": "Lint check did not pass",
            })

        # ── Type-check failure ────────────────────────────────
        w = self.weights.get("type_check_failure", 10)
        if not type_check_passed:
            score += w
            factors.append({
                "factor": "type_check_failure",
                "value": True,
                "weight": w,
                "penalty": w,
                "detail": "Type check did not pass",
            })

        # ── Security findings ─────────────────────────────────
        for severity, count in security_findings.items():
            if count <= 0:
                continue
            key = f"security_{severity.lower()}"
            w = self.weights.get(key, 5)
            penalty = count * w
            score += penalty
            factors.append({
                "factor": f"security_{severity}",
                "value": count,
                "weight": w,
                "penalty": penalty,
                "detail": f"{count} {severity} security finding(s)",
            })

        # ── Low agent confidence ──────────────────────────────
        w = self.weights.get("low_confidence", 15)
        if agent_confidence < 0.5:
            score += w
            factors.append({
                "factor": "low_confidence",
                "value": agent_confidence,
                "weight": w,
                "penalty": w,
                "detail": f"Agent confidence is {agent_confidence:.2f} (< 0.5 threshold)",
            })

        # ── Large patch ───────────────────────────────────────
        w = self.weights.get("large_patch", 10)
        if patch_lines > 200:
            score += w
            factors.append({
                "factor": "large_patch",
                "value": patch_lines,
                "weight": w,
                "penalty": w,
                "detail": f"Patch size is {patch_lines} lines (> 200 threshold)",
            })

        # ── Cap score at 100 ──────────────────────────────────
        score = min(score, 100.0)

        # ── Determine risk level ──────────────────────────────
        low_threshold = self.thresholds.get("low", 20)
        medium_threshold = self.thresholds.get("medium", 50)

        if score <= low_threshold:
            risk_level = "low"
        elif score <= medium_threshold:
            risk_level = "medium"
        else:
            risk_level = "high"

        # ── Build explanation ─────────────────────────────────
        explanation_lines = [
            f"Risk Score: {score:.1f}/100 → Level: {risk_level.upper()}",
            "",
            "Contributing Factors:",
        ]
        if not factors:
            explanation_lines.append("  • No risk factors detected — minimal change")
        for f in factors:
            explanation_lines.append(
                f"  • {f['factor']}: +{f['penalty']:.0f} — {f['detail']}"
            )

        explanation = "\n".join(explanation_lines)

        # ── Gate recommendation ───────────────────────────────
        gate_rec = self.policy.evaluate_gate_decision(
            risk_level=risk_level,
            all_validations_pass=(test_passed and lint_passed and type_check_passed),
            security_block=self.policy.should_block_security(
                max_severity=self._max_severity(security_findings),
                finding_counts=security_findings,
            ),
            test_failure=not test_passed,
        )

        return RiskAssessment(
            risk_score=score,
            risk_level=risk_level,
            contributing_factors=factors,
            explanation=explanation,
            gate_recommendation=gate_rec,
        )

    def _max_severity(self, findings: dict[str, int]) -> str:
        """Get the maximum severity from findings."""
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        for sev in severity_order:
            if findings.get(sev, 0) > 0:
                return sev
        return "INFO"
