"""Run state machine — manages the lifecycle of a control tower run."""

from __future__ import annotations

import logging
from typing import Any

from schemas.common import RunStatus

logger = logging.getLogger(__name__)


# ── State Transition Table ────────────────────────────────────
# Defines valid transitions from each state
VALID_TRANSITIONS: dict[RunStatus, list[RunStatus]] = {
    RunStatus.PENDING: [RunStatus.PLANNING, RunStatus.FAILED],
    RunStatus.PLANNING: [RunStatus.CODING, RunStatus.FAILED, RunStatus.BLOCKED],
    RunStatus.CODING: [RunStatus.VALIDATING, RunStatus.FAILED, RunStatus.BLOCKED],
    RunStatus.VALIDATING: [RunStatus.REVIEWING, RunStatus.FAILED, RunStatus.BLOCKED],
    RunStatus.REVIEWING: [RunStatus.RISK_SCORING, RunStatus.FAILED, RunStatus.BLOCKED],
    RunStatus.RISK_SCORING: [RunStatus.GATING, RunStatus.FAILED],
    RunStatus.GATING: [
        RunStatus.DEPLOYING,
        RunStatus.AWAITING_APPROVAL,
        RunStatus.COMPLETED,
        RunStatus.BLOCKED,
        RunStatus.FAILED,
    ],
    RunStatus.AWAITING_APPROVAL: [
        RunStatus.DEPLOYING,
        RunStatus.BLOCKED,
        RunStatus.FAILED,
    ],
    RunStatus.DEPLOYING: [RunStatus.MONITORING, RunStatus.FAILED, RunStatus.COMPLETED],
    RunStatus.MONITORING: [
        RunStatus.COMPLETED,
        RunStatus.ROLLING_BACK,
        RunStatus.FAILED,
    ],
    RunStatus.ROLLING_BACK: [RunStatus.COMPLETED, RunStatus.FAILED],
    RunStatus.COMPLETED: [],
    RunStatus.FAILED: [],
    RunStatus.BLOCKED: [],
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class StateMachine:
    """Manages run lifecycle state transitions.

    All transitions are validated against the state table.
    Invalid transitions are rejected to maintain pipeline integrity.
    """

    def __init__(self, initial_state: RunStatus = RunStatus.PENDING):
        self.current_state = initial_state
        self.history: list[dict[str, Any]] = [
            {"from": None, "to": initial_state.value, "metadata": {}}
        ]

    def can_transition(self, target: RunStatus) -> bool:
        """Check if a transition to the target state is valid."""
        return target in VALID_TRANSITIONS.get(self.current_state, [])

    def transition(self, target: RunStatus, metadata: dict[str, Any] | None = None) -> RunStatus:
        """Execute a state transition.

        Raises InvalidTransitionError if the transition is not allowed.
        """
        if not self.can_transition(target):
            raise InvalidTransitionError(
                f"Cannot transition from {self.current_state.value} to {target.value}. "
                f"Valid targets: {[s.value for s in VALID_TRANSITIONS.get(self.current_state, [])]}"
            )

        previous = self.current_state
        self.current_state = target
        self.history.append({
            "from": previous.value,
            "to": target.value,
            "metadata": metadata or {},
        })

        logger.info(f"State transition: {previous.value} → {target.value}")
        return self.current_state

    def is_terminal(self) -> bool:
        """Check if the current state is terminal (no further transitions)."""
        return len(VALID_TRANSITIONS.get(self.current_state, [])) == 0

    def get_available_transitions(self) -> list[str]:
        """Get the list of valid next states."""
        return [s.value for s in VALID_TRANSITIONS.get(self.current_state, [])]

    def get_history(self) -> list[dict[str, Any]]:
        """Get full state transition history."""
        return self.history
