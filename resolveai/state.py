
"""Controlled case-state access and write permissions."""

from copy import deepcopy
from typing import Any

from resolveai.schemas import (
    AgentName,
    CaseState,
    CriticFeedback,
    Resolution,
)


WRITE_PERMISSIONS: dict[str, set[str]] = {
    "triage": {
        "current_hypothesis", "plan", "confidence", "escalation_reason"
    },
    "investigation": {
        "current_hypothesis", "confidence", "escalation_reason"
    },
    "resolution": {
        "resolution_candidates", "selected_resolution",
        "confidence", "escalation_reason"
    },
    "critic": {
        "critic_feedback", "confidence", "escalation_reason"
    },
}

AGENT_VIEW_FIELDS: dict[str, set[str]] = {
    "triage": {
        "case_id", "ticket", "status", "current_hypothesis", "plan",
        "messages", "evidence", "tools_used", "agent_decisions",
        "critic_feedback", "resolution_candidates", "selected_resolution",
        "iteration", "confidence", "escalation_reason",
    },
    "investigation": {
        "case_id", "ticket", "status", "current_hypothesis", "plan",
        "messages", "evidence", "tools_used", "critic_feedback",
        "resolution_candidates", "selected_resolution", "iteration",
        "confidence", "escalation_reason",
    },
    "resolution": {
        "case_id", "ticket", "status", "current_hypothesis", "plan",
        "messages", "evidence", "tools_used", "critic_feedback",
        "resolution_candidates", "selected_resolution", "iteration",
        "confidence", "escalation_reason",
    },
    "critic": {
        "case_id", "ticket", "status", "current_hypothesis", "plan",
        "messages", "evidence", "tools_used", "resolution_candidates",
        "selected_resolution", "iteration", "confidence",
        "escalation_reason",
    },
}


class StatePermissionError(PermissionError):
    """Raised when an agent attempts an unauthorized state write."""


class CaseStateStore:
    """Owns a case state and validates agent write requests."""

    def __init__(self, state: CaseState):
        self._state = state.model_copy(deep=True)

    @property
    def state(self) -> CaseState:
        return self._state.model_copy(deep=True)

    def view_for(self, agent: AgentName) -> dict[str, Any]:
        allowed = AGENT_VIEW_FIELDS[agent]
        state_data = self._state.model_dump(mode="python")
        return deepcopy({
            key: value for key, value in state_data.items()
            if key in allowed
        })

    def write(self, agent: AgentName, updates: dict[str, Any]) -> None:
        """Validate the complete update before committing any changes."""
        if not updates:
            return

        forbidden = set(updates) - WRITE_PERMISSIONS[agent]
        if forbidden:
            raise StatePermissionError(
                f"{agent} cannot write fields: {sorted(forbidden)}"
            )

        candidate = self._state.model_dump(mode="python")

        for field, value in updates.items():
            if field == "resolution_candidates":
                if not isinstance(value, list) or not all(
                    isinstance(item, Resolution) for item in value
                ):
                    raise ValueError(
                        "resolution_candidates must contain Resolution objects"
                    )
                candidate[field] = candidate[field] + deepcopy(value)

            elif field == "critic_feedback":
                if not isinstance(value, list) or not all(
                    isinstance(item, CriticFeedback) for item in value
                ):
                    raise ValueError(
                        "critic_feedback must contain CriticFeedback objects"
                    )
                candidate[field] = candidate[field] + deepcopy(value)

            else:
                candidate[field] = value

        validated = CaseState.model_validate(candidate)
        self._state = validated
