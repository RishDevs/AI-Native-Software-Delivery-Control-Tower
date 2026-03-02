"""Release Agent — determines deployment gate strategy (rule-based)."""

from __future__ import annotations

import logging
from typing import Any

from schemas.release import ReleaseInput, ReleaseOutput, CanaryConfig
from schemas.common import GateDecision

logger = logging.getLogger(__name__)


class ReleaseAgent:
    """Rule-based agent that recommends deployment gating.

    For MVP, this is entirely deterministic for reliability.
    """

    def evaluate(self, input_data: ReleaseInput) -> ReleaseOutput:
        """Evaluate deployment readiness and recommend gate strategy."""
        reasons: list[str] = []
        required_approvals: list[str] = []

        # ── Security check ────────────────────────────────────
        if input_data.security_block:
            decision = GateDecision.BLOCK
            reasons.append(
                f"Security block: {input_data.security_max_severity} severity finding(s)"
            )
            logger.info(f"Gate decision: BLOCK (security)")
            return ReleaseOutput(
                gate_decision=decision,
                decision_reasons=reasons,
                summary=f"Blocked due to {input_data.security_max_severity} security findings",
                confidence=1.0,
            )

        # ── Validation check ──────────────────────────────────
        if not input_data.validation_passed:
            if input_data.risk_level == "high":
                decision = GateDecision.BLOCK
                reasons.append("Validation failed + high risk level")
            else:
                decision = GateDecision.HUMAN_REVIEW
                reasons.append("Validation has failures — requires human review")
                required_approvals.append("validation_override")

            logger.info(f"Gate decision: {decision.value} (validation)")
            return ReleaseOutput(
                gate_decision=decision,
                decision_reasons=reasons,
                required_approvals=required_approvals,
                summary=f"{decision.value}: validation issues detected",
                confidence=0.9,
            )

        # ── Risk-based decision ───────────────────────────────
        risk_level = input_data.risk_level
        risk_score = input_data.risk_score

        if risk_level == "low" and input_data.validation_passed:
            decision = GateDecision.APPROVE
            reasons.append(f"Low risk ({risk_score:.0f}) + all validations passed")
            canary_config = None

        elif risk_level == "medium":
            decision = GateDecision.CANARY
            reasons.append(f"Medium risk ({risk_score:.0f}) — canary deployment recommended")
            canary_config = CanaryConfig(
                duration_seconds=60,
                check_interval_seconds=10,
                traffic_split_percent=10,
                metrics_to_monitor=["error_rate", "p95_latency_ms", "http_5xx_ratio"],
            )

        elif risk_level == "high":
            decision = GateDecision.HUMAN_REVIEW
            reasons.append(f"High risk ({risk_score:.0f}) — human approval required")
            required_approvals.append("senior_engineer")
            canary_config = None

        else:
            # Default: block
            decision = GateDecision.BLOCK
            reasons.append("Uncertain risk assessment — defaulting to block")
            canary_config = None

        # ── Reviewer alignment ────────────────────────────────
        if input_data.reviewer_recommendation == "reject":
            decision = GateDecision.BLOCK
            reasons.append("Reviewer recommended rejection")
        elif input_data.reviewer_recommendation == "revise" and decision == GateDecision.APPROVE:
            decision = GateDecision.HUMAN_REVIEW
            reasons.append("Reviewer recommended revisions — escalating to human review")

        logger.info(f"Gate decision: {decision.value} (risk={risk_level})")

        return ReleaseOutput(
            gate_decision=decision,
            decision_reasons=reasons,
            canary_config=canary_config if decision == GateDecision.CANARY else None,
            required_approvals=required_approvals,
            summary=f"{decision.value}: {'; '.join(reasons)}",
            confidence=0.95,
        )
