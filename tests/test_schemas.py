
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from resolveai.schemas import (
    AgentDecision,
    CaseResult,
    CriticFeedback,
    Resolution,
    TicketIn,
)


def make_ticket(**overrides):
    data = {
        "ticket_id": "ticket-001",
        "customer_id": "customer-001",
        "message": "My payment was deducted but no order was created.",
        "channel": "web",
        "timestamp": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return data


def test_ticket_sanitizes_message():
    ticket = TicketIn(**make_ticket(message="  Hello\x00 world  "))
    assert ticket.message == "Hello world"


@pytest.mark.parametrize("field", ["ticket_id", "customer_id"])
def test_ticket_rejects_invalid_identifier(field):
    with pytest.raises(ValidationError):
        TicketIn(**make_ticket(**{field: "bad identifier!"}))


@pytest.mark.parametrize("message", ["", "   ", "\x00 \x00"])
def test_ticket_rejects_blank_message(message):
    with pytest.raises(ValidationError):
        TicketIn(**make_ticket(message=message))


def test_ticket_rejects_oversized_message():
    with pytest.raises(ValidationError):
        TicketIn(**make_ticket(message="x" * 2001))


def test_valid_triage_decision():
    decision = AgentDecision(
        agent="triage",
        next_action="request_investigation",
        next_agent="investigation",
        reason="The payment outcome must be verified first.",
        confidence=0.8,
    )
    assert decision.next_agent == "investigation"


def test_call_tool_requires_tool_call():
    with pytest.raises(ValidationError):
        AgentDecision(
            agent="investigation",
            next_action="call_tool",
            next_agent="investigation",
            reason="Check the payment record before proceeding.",
            confidence=0.7,
        )


def test_wrong_action_target_is_rejected():
    with pytest.raises(ValidationError):
        AgentDecision(
            agent="triage",
            next_action="request_investigation",
            next_agent="resolution",
            reason="The payment outcome must be verified first.",
            confidence=0.8,
        )


def test_agent_cannot_use_another_agents_action():
    with pytest.raises(ValidationError):
        AgentDecision(
            agent="triage",
            next_action="approve",
            next_agent="none",
            reason="Triage is not authorized to approve resolutions.",
            confidence=0.9,
        )


def test_escalation_requires_risk():
    with pytest.raises(ValidationError):
        AgentDecision(
            agent="triage",
            next_action="human_escalation",
            next_agent="none",
            reason="Human review is required for this authorization.",
            confidence=0.5,
        )


def test_non_approval_requires_actionable_feedback():
    with pytest.raises(ValidationError):
        CriticFeedback(
            decision="reject",
            reason="The proposal lacks sufficient supporting evidence.",
            confidence=0.9,
        )


def test_resolved_case_requires_critic_approval():
    with pytest.raises(ValidationError):
        CaseResult(
            case_id="case-001",
            status="resolved",
            customer_response="Your case has been resolved.",
            resolution=Resolution(type="refund"),
            confidence=0.9,
            agents_involved=["triage", "resolution"],
            tools_used=[],
            iterations=2,
            critic_decision="reject",
            trace_id="trace-001",
        )


def test_escalated_case_requires_reason():
    with pytest.raises(ValidationError):
        CaseResult(
            case_id="case-001",
            status="escalated",
            customer_response="A support specialist will review your case.",
            confidence=0.7,
            agents_involved=["triage"],
            tools_used=[],
            iterations=1,
            trace_id="trace-001",
        )
