
from datetime import datetime, timezone

import pytest

from resolveai.schemas import CaseState, CriticFeedback, Resolution, TicketIn
from resolveai.state import CaseStateStore, StatePermissionError


def make_state():
    ticket = TicketIn(
        ticket_id="ticket-001",
        customer_id="customer-001",
        message="My payment was deducted but no order was created.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
    )
    return CaseState(case_id="case-001", ticket=ticket)


def test_triage_can_write_plan():
    store = CaseStateStore(make_state())
    store.write("triage", {"plan": ["Check payment", "Check order"]})
    assert store.state.plan == ["Check payment", "Check order"]


def test_agent_cannot_write_unauthorized_field():
    store = CaseStateStore(make_state())
    before = store.state.model_dump()

    with pytest.raises(StatePermissionError):
        store.write("triage", {"selected_resolution": {"type": "refund"}})

    assert store.state.model_dump() == before


def test_failed_multi_field_write_changes_nothing():
    store = CaseStateStore(make_state())
    before = store.state.model_dump()

    with pytest.raises(StatePermissionError):
        store.write(
            "triage",
            {
                "plan": ["Investigate"],
                "selected_resolution": {"type": "refund"},
            },
        )

    assert store.state.model_dump() == before


def test_only_critic_can_append_feedback():
    store = CaseStateStore(make_state())
    feedback = CriticFeedback(
        decision="reject",
        reason="The proposed resolution lacks sufficient evidence.",
        missing_evidence=["Payment confirmation"],
        confidence=0.9,
    )

    with pytest.raises(StatePermissionError):
        store.write("resolution", {"critic_feedback": [feedback]})

    store.write("critic", {"critic_feedback": [feedback]})
    assert len(store.state.critic_feedback) == 1


def test_resolution_candidates_are_append_only():
    store = CaseStateStore(make_state())

    store.write("resolution", {
        "resolution_candidates": [Resolution(type="replacement")]
    })
    store.write("resolution", {
        "resolution_candidates": [Resolution(type="refund")]
    })

    assert [r.type for r in store.state.resolution_candidates] == [
        "replacement", "refund"
    ]


def test_agent_view_is_a_copy():
    store = CaseStateStore(make_state())
    view = store.view_for("triage")
    view["plan"].append("External mutation")

    assert store.state.plan == []


def test_agent_view_omits_runtime_managed_fields():
    store = CaseStateStore(make_state())
    view = store.view_for("resolution")

    assert "ticket" in view
    assert "agent_decisions" not in view
