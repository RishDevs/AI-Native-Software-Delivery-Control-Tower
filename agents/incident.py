"""Incident Agent — summarizes canary anomalies and recommends actions."""

from __future__ import annotations

import logging
from typing import Any

from schemas.incident import IncidentInput, IncidentOutput, MetricSummary

logger = logging.getLogger(__name__)


class IncidentAgent:
    """Rule-based agent that processes canary anomalies and produces incident reports.

    For MVP, this is primarily rule-based for reliability.
    Can be enhanced with LLM-generated postmortems post-MVP.
    """

    def analyze(self, input_data: IncidentInput) -> IncidentOutput:
        """Analyze canary metrics and produce incident report."""
        baseline = input_data.baseline_metrics
        canary = input_data.canary_metrics
        breaches = input_data.threshold_breaches

        metrics_summary: list[MetricSummary] = []
        anomaly_detected = len(breaches) > 0
        probable_causes: list[str] = []

        # Build metric summaries
        for metric_name in set(list(baseline.keys()) + list(canary.keys())):
            b_val = baseline.get(metric_name, 0)
            c_val = canary.get(metric_name, 0)

            delta = 0.0
            if b_val > 0:
                delta = ((c_val - b_val) / b_val) * 100

            breach_info = next(
                (b for b in breaches if b.get("metric") == metric_name), None
            )

            metrics_summary.append(MetricSummary(
                name=metric_name,
                baseline_value=b_val,
                canary_value=c_val,
                threshold=breach_info.get("threshold", 0) if breach_info else 0,
                breached=breach_info is not None,
                breach_count=breach_info.get("count", 0) if breach_info else 0,
                delta_percent=round(delta, 2),
            ))

        # Determine probable causes from breach patterns
        if anomaly_detected:
            for breach in breaches:
                metric = breach.get("metric", "unknown")
                if "error_rate" in metric:
                    probable_causes.append(
                        "Elevated error rate — possible code regression or unhandled exception"
                    )
                elif "latency" in metric:
                    probable_causes.append(
                        "Increased latency — possible performance regression or resource contention"
                    )
                elif "5xx" in metric:
                    probable_causes.append(
                        "HTTP 5xx spike — possible server-side error in new code path"
                    )

            if not probable_causes:
                probable_causes.append(
                    "Metric degradation detected — root cause requires further investigation"
                )

        # Determine action
        if anomaly_detected:
            action = "rollback"
            rollback = True
        else:
            action = "monitor"
            rollback = False

        # Build incident summary
        summary_lines = []
        if anomaly_detected:
            summary_lines.append("🚨 CANARY ANOMALY DETECTED")
            summary_lines.append(f"Deployment: {input_data.deployment_id}")
            summary_lines.append(f"Breached metrics: {len(breaches)}")
            for breach in breaches:
                summary_lines.append(
                    f"  - {breach.get('metric', '?')}: "
                    f"{breach.get('count', 0)} consecutive breaches"
                )
            summary_lines.append(f"Action: {action.upper()}")
        else:
            summary_lines.append("✅ Canary deployment healthy")
            summary_lines.append("No threshold breaches detected")

        # Build postmortem draft
        postmortem = ""
        if anomaly_detected:
            postmortem = self._draft_postmortem(
                input_data, metrics_summary, probable_causes
            )

        logger.info(
            f"Incident analysis: anomaly={anomaly_detected}, action={action}"
        )

        return IncidentOutput(
            anomaly_detected=anomaly_detected,
            metrics_summary=metrics_summary,
            probable_causes=probable_causes,
            action_recommendation=action,
            rollback_triggered=rollback,
            incident_summary="\n".join(summary_lines),
            postmortem_draft=postmortem,
            confidence=0.85 if anomaly_detected else 0.95,
        )

    def _draft_postmortem(
        self,
        input_data: IncidentInput,
        metrics: list[MetricSummary],
        causes: list[str],
    ) -> str:
        """Draft a postmortem for the incident."""
        lines = [
            "# Incident Postmortem Draft",
            "",
            "## Summary",
            f"Canary deployment {input_data.deployment_id} was rolled back "
            "due to metric threshold breaches.",
            "",
            "## Timeline",
            "- Canary deployed",
            "- Metric degradation detected",
            "- Automatic rollback triggered",
            "",
            "## Metrics",
        ]

        for m in metrics:
            if m.breached:
                lines.append(
                    f"- **{m.name}**: baseline={m.baseline_value:.4f}, "
                    f"canary={m.canary_value:.4f} "
                    f"(Δ {m.delta_percent:+.1f}%) ⚠️ BREACHED"
                )

        lines.extend([
            "",
            "## Probable Causes",
        ])
        for cause in causes:
            lines.append(f"- {cause}")

        lines.extend([
            "",
            "## Patch Summary",
            input_data.patch_summary or "No patch summary available",
            "",
            "## Action Items",
            "- [ ] Investigate root cause",
            "- [ ] Fix regression",
            "- [ ] Add regression test",
            "- [ ] Re-deploy with fix",
            "",
            "## Lessons Learned",
            "- Canary monitoring detected the regression before full rollout",
            "- Automatic rollback prevented user impact",
        ])

        return "\n".join(lines)
