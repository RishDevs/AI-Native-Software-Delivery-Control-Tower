"""Deployment simulator — canary deployment with baseline/canary metrics comparison."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

logger = logging.getLogger(__name__)


class DeploymentSimulator:
    """Simulates canary deployment with metrics monitoring and rollback.

    For MVP, this generates synthetic but realistic metrics to demonstrate
    the monitoring → regression detection → rollback pipeline without
    requiring actual Docker containers.
    """

    def __init__(
        self,
        canary_duration: int = 60,
        check_interval: int = 10,
        metrics_config: list[dict] | None = None,
    ):
        self.canary_duration = canary_duration
        self.check_interval = check_interval
        self.metrics_config = metrics_config or self._default_metrics_config()

    def _default_metrics_config(self) -> list[dict]:
        return [
            {
                "name": "error_rate",
                "type": "ratio",
                "threshold_multiplier": 2.0,
                "consecutive_breaches": 3,
            },
            {
                "name": "p95_latency_ms",
                "type": "absolute",
                "threshold_percent_above": 40,
                "consecutive_breaches": 2,
            },
            {
                "name": "http_5xx_ratio",
                "type": "ratio",
                "threshold_absolute": 0.05,
                "consecutive_breaches": 3,
            },
        ]

    def generate_baseline_metrics(self) -> dict[str, float]:
        """Generate realistic baseline metrics."""
        return {
            "error_rate": round(random.uniform(0.001, 0.01), 4),
            "p95_latency_ms": round(random.uniform(50, 150), 1),
            "http_5xx_ratio": round(random.uniform(0.001, 0.005), 4),
            "request_count": round(random.uniform(900, 1100)),
            "throughput_rps": round(random.uniform(80, 120), 1),
        }

    def generate_healthy_canary_metrics(
        self, baseline: dict[str, float]
    ) -> dict[str, float]:
        """Generate canary metrics that are close to baseline (healthy deploy)."""
        return {
            "error_rate": round(baseline["error_rate"] * random.uniform(0.8, 1.3), 4),
            "p95_latency_ms": round(
                baseline["p95_latency_ms"] * random.uniform(0.9, 1.15), 1
            ),
            "http_5xx_ratio": round(
                baseline["http_5xx_ratio"] * random.uniform(0.8, 1.2), 4
            ),
            "request_count": round(baseline["request_count"] * random.uniform(0.08, 0.12)),
            "throughput_rps": round(
                baseline["throughput_rps"] * random.uniform(0.08, 0.12), 1
            ),
        }

    def generate_degraded_canary_metrics(
        self, baseline: dict[str, float]
    ) -> dict[str, float]:
        """Generate canary metrics that show regression (problematic deploy)."""
        return {
            "error_rate": round(baseline["error_rate"] * random.uniform(3.0, 8.0), 4),
            "p95_latency_ms": round(
                baseline["p95_latency_ms"] * random.uniform(1.8, 3.5), 1
            ),
            "http_5xx_ratio": round(
                baseline["http_5xx_ratio"] * random.uniform(5.0, 15.0), 4
            ),
            "request_count": round(baseline["request_count"] * random.uniform(0.06, 0.10)),
            "throughput_rps": round(
                baseline["throughput_rps"] * random.uniform(0.04, 0.08), 1
            ),
        }

    def simulate_canary(
        self,
        simulate_degradation: bool = False,
        degradation_start_window: int = 3,
    ) -> dict[str, Any]:
        """Run a full canary simulation.

        Args:
            simulate_degradation: If True, canary will start degrading
            degradation_start_window: Window index when degradation begins

        Returns:
            Simulation results including metrics, breach detection, and rollback status
        """
        baseline = self.generate_baseline_metrics()
        windows = self.canary_duration // self.check_interval
        breach_counts: dict[str, int] = {m["name"]: 0 for m in self.metrics_config}
        rollback_triggered = False
        rollback_window = -1
        all_windows: list[dict[str, Any]] = []

        logger.info(f"Starting canary simulation: {windows} windows, "
                     f"degradation={'yes' if simulate_degradation else 'no'}")

        for window in range(windows):
            # Generate metrics for this window
            if simulate_degradation and window >= degradation_start_window:
                canary = self.generate_degraded_canary_metrics(baseline)
            else:
                canary = self.generate_healthy_canary_metrics(baseline)

            # Check for threshold breaches
            breaches = self._check_thresholds(baseline, canary)

            for metric_name, breached in breaches.items():
                if breached:
                    breach_counts[metric_name] = breach_counts.get(metric_name, 0) + 1
                else:
                    breach_counts[metric_name] = 0  # Reset consecutive count

            # Check if any metric has exceeded consecutive breach threshold
            should_rollback = False
            trigger_metric = ""
            for config in self.metrics_config:
                name = config["name"]
                max_consecutive = config.get("consecutive_breaches", 3)
                if breach_counts.get(name, 0) >= max_consecutive:
                    should_rollback = True
                    trigger_metric = name
                    break

            window_data = {
                "window": window,
                "baseline_metrics": baseline,
                "canary_metrics": canary,
                "breaches": breaches,
                "breach_counts": dict(breach_counts),
                "rollback_triggered": should_rollback,
            }
            all_windows.append(window_data)

            if should_rollback:
                rollback_triggered = True
                rollback_window = window
                logger.warning(
                    f"Rollback triggered at window {window} "
                    f"due to {trigger_metric} "
                    f"({breach_counts[trigger_metric]} consecutive breaches)"
                )
                break

            logger.info(f"Window {window}: healthy (breaches: {breach_counts})")

        return {
            "baseline_metrics": baseline,
            "final_canary_metrics": all_windows[-1]["canary_metrics"] if all_windows else {},
            "total_windows": len(all_windows),
            "rollback_triggered": rollback_triggered,
            "rollback_window": rollback_window,
            "trigger_metric": trigger_metric if rollback_triggered else "",
            "breach_counts": breach_counts,
            "windows": all_windows,
            "status": "rolled_back" if rollback_triggered else "completed",
        }

    def _check_thresholds(
        self, baseline: dict[str, float], canary: dict[str, float]
    ) -> dict[str, bool]:
        """Check canary metrics against configured thresholds."""
        breaches: dict[str, bool] = {}

        for config in self.metrics_config:
            name = config["name"]
            baseline_val = baseline.get(name, 0)
            canary_val = canary.get(name, 0)

            breached = False

            if config["type"] == "ratio":
                multiplier = config.get("threshold_multiplier", 2.0)
                absolute = config.get("threshold_absolute", float("inf"))

                if baseline_val > 0 and canary_val / baseline_val > multiplier:
                    breached = True
                if canary_val > absolute:
                    breached = True

            elif config["type"] == "absolute":
                percent_above = config.get("threshold_percent_above", 40)
                if baseline_val > 0:
                    delta = ((canary_val - baseline_val) / baseline_val) * 100
                    if delta > percent_above:
                        breached = True

            breaches[name] = breached

        return breaches
