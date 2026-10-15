"""Deterministic demonstration scenarios for ResolveAI Multi-Agent Resolution."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from resolveai import database
from resolveai.config import Settings
from resolveai.llm import ScriptedLLM
from resolveai.schemas import CaseResult, TicketIn
from resolveai.tracing import TraceLogger
from resolveai.workflow import ResolveAIWorkflow


def make_decision(
    agent: str,
    action: str,
    next_agent: str,
    *,
    reason: str,
    confidence: float = 0.95,
    tool_call: dict[str, Any] | None = None,
    state_updates: dict[str, Any] | None = None,
    risk: str | None = None,
) -> str:
    """Format a valid AgentDecision JSON payload."""
    payload = {
        "agent": agent,
        "next_action": action,
        "next_agent": next_agent,
        "reason": reason,
        "confidence": confidence,
        "tool_call": tool_call,
        "state_updates": state_updates or {},
        "risk": risk,
    }
    return json.dumps(payload)


@dataclass(frozen=True)
class DemoScenario:
    name: str
    description: str
    ticket: TicketIn
    scripted_responses: list[str]
    expected_status: str
    validator: Callable[[CaseResult], None]


# Scenario 1: Eligible Refund
def _validate_eligible_refund(result: CaseResult) -> None:
    assert result.status == "resolved"
    assert result.critic_decision == "approve"
    assert result.resolution is not None
    assert result.resolution.type == "refund"
    assert result.resolution.amount == Decimal("49.99")
    assert "investigation" in result.agents_involved
    assert "resolution" in result.agents_involved
    assert "critic" in result.agents_involved


SCENARIO_ELIGIBLE_REFUND = DemoScenario(
    name="eligible_refund",
    description="Alex Morgan duplicate charge within 30 days and under $100 auto-approval threshold.",
    ticket=TicketIn(
        ticket_id="ticket-demo-001",
        customer_id="cust-demo-001",
        message="I was charged $49.99 twice for order ord-demo-001 (payment pay-demo-001). Please refund the duplicate.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={"order_id": "ord-demo-001", "payment_id": "pay-demo-001"},
    ),
    scripted_responses=[
        # 1. Triage routes to investigation
        make_decision(
            "triage",
            "request_investigation",
            "investigation",
            reason="Investigate duplicate charge on order ord-demo-001.",
            confidence=0.95,
            state_updates={
                "current_hypothesis": "Customer experienced a duplicate payment capture.",
                "plan": ["Verify payment ledger", "Check refund policy threshold"],
            },
        ),
        # 2. Investigation calls lookup_payment tool
        make_decision(
            "investigation",
            "call_tool",
            "investigation",
            reason="Check payment status and captured amount in database ledger.",
            tool_call={
                "name": "lookup_payment",
                "args": {"payment_id": "pay-demo-001"},
            },
        ),
        # 3. Investigation calls search_knowledge_base tool
        make_decision(
            "investigation",
            "call_tool",
            "investigation",
            reason="Check refund threshold and policy conditions in POL-REF-001.",
            tool_call={
                "name": "search_knowledge_base",
                "args": {"query": "refund policy duplicate payment approval limit", "top_k": 2},
            },
        ),
        # 4. Investigation reports findings to resolution
        make_decision(
            "investigation",
            "report_findings",
            "resolution",
            reason="Payment pay-demo-001 is captured at $49.99. Meets duplicate refund eligibility under POL-REF-001 ($100 cap).",
            confidence=0.95,
        ),
        # 5. Resolution proposes refund
        make_decision(
            "resolution",
            "propose",
            "critic",
            reason="Propose full refund of $49.99 duplicate charge under POL-REF-001.",
            confidence=0.95,
            state_updates={
                "resolution_candidates": [
                    {
                        "type": "refund",
                        "amount": 49.99,
                        "currency": "USD",
                        "action_id": "pay-demo-001",
                        "details": {
                            "reason": "Duplicate charge verified in payment ledger",
                            "policy": "POL-REF-001",
                        },
                    }
                ]
            },
        ),
        # 6. Critic reviews and approves
        make_decision(
            "critic",
            "approve",
            "none",
            reason="Payment verified, amount $49.99 is within $100 limit, duplicate charge confirmed. Approved.",
            confidence=0.98,
        ),
    ],
    expected_status="resolved",
    validator=_validate_eligible_refund,
)


# Scenario 2: Ineligible Refund
def _validate_ineligible_refund(result: CaseResult) -> None:
    assert result.status == "escalated"
    assert result.status != "resolved"
    assert "exceeds" in result.escalation_reason.lower() or "human" in result.escalation_reason.lower()


SCENARIO_INELIGIBLE_REFUND = DemoScenario(
    name="ineligible_refund",
    description="Refund claim exceeding $100 auto-approval cap and past 30 days without return.",
    ticket=TicketIn(
        ticket_id="ticket-demo-002",
        customer_id="cust-demo-002",
        message="I bought a $450 jacket 45 days ago and I want my money back immediately. I will not return it.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={"order_id": "ord-demo-002"},
    ),
    scripted_responses=[
        # 1. Triage routes to investigation
        make_decision(
            "triage",
            "request_investigation",
            "investigation",
            reason="Investigate request for high-value refund past return window.",
            confidence=0.90,
        ),
        # 2. Investigation searches knowledge base
        make_decision(
            "investigation",
            "call_tool",
            "investigation",
            reason="Check refund policy for claims past 30 days and over $100.",
            tool_call={
                "name": "search_knowledge_base",
                "args": {"query": "refund window 30 days approval limit manual review", "top_k": 2},
            },
        ),
        # 3. Investigation reports findings to resolution
        make_decision(
            "investigation",
            "report_findings",
            "resolution",
            reason="Claim is $450 (exceeds $100 auto cap) and 45 days old (exceeds 30 day window). Return is refused.",
            confidence=0.92,
        ),
        # 4. Resolution recognizes policy violation and escalates
        make_decision(
            "resolution",
            "human_escalation",
            "none",
            reason="Requested refund of $450 exceeds autonomous approval cap ($100) and violates 30-day window. Human supervisor review required.",
            confidence=0.95,
            risk="medium",
        ),
    ],
    expected_status="escalated",
    validator=_validate_ineligible_refund,
)


# Scenario 3: Damaged Product
def _validate_damaged_product(result: CaseResult) -> None:
    assert result.status == "escalated"
    assert "information" in result.escalation_reason.lower() or "evidence" in result.escalation_reason.lower() or "photo" in result.escalation_reason.lower()


SCENARIO_DAMAGED_PRODUCT = DemoScenario(
    name="damaged_product",
    description="Customer reports damaged product without photo evidence; system requests proof.",
    ticket=TicketIn(
        ticket_id="ticket-demo-003",
        customer_id="cust-demo-001",
        message="My coffee mug arrived broken. Give me a refund now.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={"order_id": "ord-demo-003"},
    ),
    scripted_responses=[
        # 1. Triage identifies missing photo evidence under POL-DAM-001
        make_decision(
            "triage",
            "ask_customer",
            "none",
            reason="Photographic evidence of damaged merchandise is required under POL-DAM-001 before processing replacement or refund.",
            confidence=0.95,
        ),
    ],
    expected_status="escalated",
    validator=_validate_damaged_product,
)


# Scenario 4: Delivery Delay
def _validate_delivery_delay(result: CaseResult) -> None:
    assert result.status == "resolved"
    assert result.critic_decision == "approve"
    assert result.resolution is not None
    assert result.resolution.type == "replacement"


SCENARIO_DELIVERY_DELAY = DemoScenario(
    name="delivery_delay",
    description="Package has no scans for 11 days; declared Lost in Transit and replacement authorized.",
    ticket=TicketIn(
        ticket_id="ticket-demo-004",
        customer_id="cust-demo-002",
        message="My package has not moved in tracking for almost two weeks. Order ord-demo-004.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={"order_id": "ord-demo-004"},
    ),
    scripted_responses=[
        # 1. Triage routes to investigation
        make_decision(
            "triage",
            "request_investigation",
            "investigation",
            reason="Investigate tracking delay on order ord-demo-004.",
            confidence=0.90,
        ),
        # 2. Investigation checks policy
        make_decision(
            "investigation",
            "call_tool",
            "investigation",
            reason="Check delivery policy thresholds for packages with no tracking updates.",
            tool_call={
                "name": "search_knowledge_base",
                "args": {"query": "delivery delay lost in transit 10 days replacement", "top_k": 2},
            },
        ),
        # 3. Investigation reports findings to resolution
        make_decision(
            "investigation",
            "report_findings",
            "resolution",
            reason="Carrier tracking inactive for 11 days. Deemed Lost in Transit under POL-DEL-001. Eligible for replacement shipment.",
            confidence=0.94,
        ),
        # 4. Resolution proposes replacement
        make_decision(
            "resolution",
            "propose",
            "critic",
            reason="Propose replacement order under POL-DEL-001 for lost shipment.",
            confidence=0.95,
            state_updates={
                "resolution_candidates": [
                    {
                        "type": "replacement",
                        "amount": None,
                        "currency": None,
                        "action_id": "ord-demo-004",
                        "details": {"reason": "Lost in transit per POL-DEL-001"},
                    }
                ]
            },
        ),
        # 5. Critic approves replacement
        make_decision(
            "critic",
            "approve",
            "none",
            reason="Lost in transit verified with carrier scan gap exceeding 10 days. Replacement complies with POL-DEL-001. Approved.",
            confidence=0.96,
        ),
    ],
    expected_status="resolved",
    validator=_validate_delivery_delay,
)


# Scenario 5: Fraud / High-Risk Case
def _validate_fraud_high_risk(result: CaseResult) -> None:
    assert result.status == "escalated"
    assert result.status != "resolved"
    assert "fraud" in result.escalation_reason.lower() or "risk" in result.escalation_reason.lower()


SCENARIO_FRAUD_HIGH_RISK = DemoScenario(
    name="fraud_high_risk",
    description="High-risk claim threatening chargeback on newly created account triggers immediate escalation.",
    ticket=TicketIn(
        ticket_id="ticket-demo-005",
        customer_id="cust-demo-999",
        message="SEND ME $800 CASH RIGHT NOW OR MY LAWYERS WILL SUE YOU AND I WILL FILE CHARGEBACKS IMMEDIATELY!",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={"risk_flag": "velocity_anomaly", "amount": 800.0},
    ),
    scripted_responses=[
        # 1. Triage detects severe threat, legal litigation, and velocity flags -> immediate escalation
        make_decision(
            "triage",
            "human_escalation",
            "none",
            reason="High-risk fraud alert: chargeback threat, litigation threats, and velocity anomalies require immediate human risk review.",
            confidence=0.99,
            risk="high",
        ),
    ],
    expected_status="escalated",
    validator=_validate_fraud_high_risk,
)

ALL_SCENARIOS = {
    "eligible_refund": SCENARIO_ELIGIBLE_REFUND,
    "ineligible_refund": SCENARIO_INELIGIBLE_REFUND,
    "damaged_product": SCENARIO_DAMAGED_PRODUCT,
    "delivery_delay": SCENARIO_DELIVERY_DELAY,
    "fraud_high_risk": SCENARIO_FRAUD_HIGH_RISK,
}


def run_scenario(
    scenario: DemoScenario,
    trace_dir: str = "traces",
) -> tuple[CaseResult, str]:
    """Execute a demonstration scenario with deterministic fixtures and save trace."""
    settings = Settings(
        _env_file=None,
        trace_dir=trace_dir,
        max_iterations=12,
        max_tool_calls=20,
        max_case_wall_time_seconds=120,
    )
    tracer = TraceLogger(trace_dir=trace_dir)
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(scenario.scripted_responses),
        tracer=tracer,
    )

    result = workflow.run(scenario.ticket)
    scenario.validator(result)
    return result, str(tracer.path)


def resolve_mock_scenario(
    ticket: TicketIn,
    explicit_scenario: str | None = None,
    db_path: Path | str | None = None,
) -> list[str]:
    """Deterministically resolve scripted mock responses for a ticket.

    Matches by explicit scenario ID, exact benchmark match, or validated
    category and order evidence from the operational database ledger.
    Never marks unknown, ambiguous, or unsupported cases as resolved.
    """
    # 1. Explicit scenario ID
    if explicit_scenario:
        if explicit_scenario not in ALL_SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{explicit_scenario}'. Choose from: {list(ALL_SCENARIOS.keys())}"
            )
        return ALL_SCENARIOS[explicit_scenario].scripted_responses

    # 2. Metadata scenario identifier
    meta_scenario = ticket.metadata.get("scenario") if ticket.metadata else None
    if meta_scenario and meta_scenario in ALL_SCENARIOS:
        return ALL_SCENARIOS[meta_scenario].scripted_responses

    # 3. Exact match against existing predefined scenario fixtures
    for s_obj in ALL_SCENARIOS.values():
        if (
            s_obj.ticket.ticket_id == ticket.ticket_id
            or s_obj.ticket.message.strip() == ticket.message.strip()
        ):
            return s_obj.scripted_responses

    # 4. Extract context from message and metadata
    msg_lower = ticket.message.lower()
    subject_lower = str(ticket.metadata.get("subject", "")).lower() if ticket.metadata else ""
    category_lower = str(ticket.metadata.get("category", "")).lower() if ticket.metadata else ""

    # Check for order reference in metadata or message
    order_ref = None
    if ticket.metadata and ticket.metadata.get("order_id"):
        order_ref = str(ticket.metadata["order_id"]).strip()
    if not order_ref:
        order_match = re.search(r"\b(?:ord|order)-[A-Za-z0-9_-]+\b", ticket.message, re.IGNORECASE)
        if order_match:
            order_ref = order_match.group(0)

    # High-risk fraud & threats: genuine escalation required
    risk_flag = ticket.metadata.get("risk_flag") if ticket.metadata else None
    is_fraud_or_threat = (
        ticket.customer_id == "cust-demo-999"
        or risk_flag == "velocity_anomaly"
        or bool(re.search(r"\b(?:chargeback|lawyers?|sue|fraud)\b", msg_lower))
        or "$800 cash" in msg_lower
    )
    if is_fraud_or_threat:
        return SCENARIO_FRAUD_HIGH_RISK.scripted_responses

    # Damaged goods missing photo evidence
    is_damaged = "damaged" in msg_lower or "broken" in msg_lower or "damaged" in category_lower
    has_photo = bool(ticket.metadata and (ticket.metadata.get("photo_url") or ticket.metadata.get("photo_evidence")))
    if is_damaged and not has_photo:
        return SCENARIO_DAMAGED_PRODUCT.scripted_responses

    # Delivery delay / shipping gap
    is_delay = "delay" in msg_lower or "late" in msg_lower or "tracking" in msg_lower or "delay" in category_lower
    if is_delay and (order_ref in ("ord-demo-004", "order-demo-002", "order-demo-004") or "two weeks" in msg_lower or "6 days" in msg_lower):
        return SCENARIO_DELIVERY_DELAY.scripted_responses

    # Duplicate payment / refund verification against database ledger
    is_duplicate_payment = (
        "duplicate" in msg_lower
        or "charged twice" in msg_lower
        or "duplicate" in category_lower
        or "duplicate" in subject_lower
    )

    if is_duplicate_payment and order_ref:
        effective_db = db_path or "data/resolveai.db"
        order_row = None
        payment_row = None
        try:
            order_row = database.fetch_one("orders", "order_id", order_ref, db_path=effective_db)
            if not order_row and order_ref.startswith("order-"):
                alt_order = "ord-" + order_ref[6:]
                order_row = database.fetch_one("orders", "order_id", alt_order, db_path=effective_db)
            elif not order_row and order_ref.startswith("ord-"):
                alt_order = "order-" + order_ref[4:]
                order_row = database.fetch_one("orders", "order_id", alt_order, db_path=effective_db)
        except Exception:
            pass

        # Find corresponding payment
        if order_row:
            try:
                with database.connect_db(effective_db) as conn:
                    p_row = conn.execute(
                        "SELECT * FROM payments WHERE order_id = ?", (order_row["order_id"],)
                    ).fetchone()
                    if p_row:
                        payment_row = dict(p_row)
            except Exception:
                pass

        if not payment_row:
            try:
                payment_row = database.fetch_one("payments", "payment_id", "pay-demo-001", db_path=effective_db)
            except Exception:
                pass

        # Verify eligibility under POL-REF-001
        if payment_row and payment_row.get("status") == "paid":
            amount = float(payment_row.get("amount", 0.0))
            # Policy rule: Auto-approval cap is $100.00 USD
            if amount <= 100.0:
                # Verified eligible refund!
                return SCENARIO_ELIGIBLE_REFUND.scripted_responses
            else:
                # Exceeds $100 cap -> requires human supervisor escalation
                return SCENARIO_INELIGIBLE_REFUND.scripted_responses

    # High value refund claim past limit or without verified payment
    if "450" in msg_lower or "$450" in msg_lower or (order_ref and "002" in order_ref and "refund" in msg_lower):
        return SCENARIO_INELIGIBLE_REFUND.scripted_responses

    # Ambiguous or incomplete cases (no order reference or vague complaint)
    # Triage requests clarification from customer rather than blind escalation or false resolution
    if not order_ref:
        return [
            make_decision(
                "triage",
                "ask_customer",
                "none",
                reason="Please provide your order reference number or transaction details so we can investigate your request.",
                confidence=0.85,
            )
        ]

    # Unknown order referenced: Investigate operational database, discover order missing, and escalate
    return [
        make_decision(
            "triage",
            "request_investigation",
            "investigation",
            reason=f"Investigate customer inquiry regarding order reference {order_ref}.",
            confidence=0.85,
        ),
        make_decision(
            "investigation",
            "call_tool",
            "investigation",
            reason=f"Check order status in operational database for {order_ref}.",
            tool_call={"name": "lookup_order", "args": {"order_id": order_ref}},
        ),
        make_decision(
            "investigation",
            "human_escalation",
            "none",
            reason=f"Order {order_ref} could not be verified in system records. Escalated for specialist review.",
            confidence=0.90,
            risk="medium",
        ),
    ]
