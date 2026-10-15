import json
from decimal import Decimal

from resolveai.scenarios import (
    SCENARIO_DAMAGED_PRODUCT,
    SCENARIO_DELIVERY_DELAY,
    SCENARIO_ELIGIBLE_REFUND,
    SCENARIO_FRAUD_HIGH_RISK,
    SCENARIO_INELIGIBLE_REFUND,
    run_scenario,
)


def test_scenario_eligible_refund(tmp_path):
    result, trace_path = run_scenario(SCENARIO_ELIGIBLE_REFUND, trace_dir=str(tmp_path))
    assert result.status == "resolved"
    assert result.critic_decision == "approve"
    assert result.resolution is not None
    assert result.resolution.type == "refund"
    assert result.resolution.amount == Decimal("49.99")
    assert "investigation" in result.agents_involved
    assert "resolution" in result.agents_involved
    assert "critic" in result.agents_involved
    assert result.financial_action_status == "approved"
    timeline = {event.stage: event for event in result.customer_timeline}
    assert timeline["case_received"].outcome == "received"
    assert timeline["payment_verification"].outcome in {
        "verified", "not_found", "unable_to_verify"
    }
    assert timeline["policy_review"].outcome in {
        "guidance_found", "guidance_not_found", "unavailable"
    }
    if timeline["payment_verification"].outcome == "verified":
        assert "payment record was verified" in result.customer_summary
    else:
        assert "payment record was verified" not in result.customer_summary
    assert timeline["safety_check"].outcome == "passed"
    assert timeline["resolution_decision"].outcome == "approved"
    assert timeline["next_steps"].outcome == "resolved"
    customer_content = json.dumps({
        "summary": result.customer_summary,
        "timeline": [event.model_dump() for event in result.customer_timeline],
    })
    assert "pay-demo-001" not in customer_content
    assert "POL-REF-001" not in customer_content
    assert "lookup_payment" not in customer_content


def test_scenario_ineligible_refund(tmp_path):
    result, trace_path = run_scenario(SCENARIO_INELIGIBLE_REFUND, trace_dir=str(tmp_path))
    assert result.status == "escalated"
    assert result.status != "resolved"
    assert result.resolution is None
    assert "exceeds" in result.escalation_reason.lower() or "human" in result.escalation_reason.lower()
    assert "automatic approval limit" in result.customer_summary.lower()


def test_scenario_damaged_product_missing_evidence(tmp_path):
    result, trace_path = run_scenario(SCENARIO_DAMAGED_PRODUCT, trace_dir=str(tmp_path))
    assert result.status == "escalated"
    assert result.resolution is None
    assert "information" in result.escalation_reason.lower() or "photo" in result.escalation_reason.lower()
    timeline = {event.stage: event for event in result.customer_timeline}
    assert timeline["evidence_check"].outcome == "needs_information"
    assert timeline["next_steps"].outcome == "waiting_for_information"
    assert "more information is needed" in result.customer_summary.lower()


def test_scenario_delivery_delay_lost_in_transit(tmp_path):
    result, trace_path = run_scenario(SCENARIO_DELIVERY_DELAY, trace_dir=str(tmp_path))
    assert result.status == "resolved"
    assert result.critic_decision == "approve"
    assert result.resolution is not None
    assert result.resolution.type == "replacement"


def test_scenario_fraud_or_high_risk_triggers_escalation(tmp_path):
    result, trace_path = run_scenario(SCENARIO_FRAUD_HIGH_RISK, trace_dir=str(tmp_path))
    assert result.status == "escalated"
    assert result.status != "resolved"
    assert "fraud" in result.escalation_reason.lower() or "risk" in result.escalation_reason.lower()
    timeline = {event.stage: event for event in result.customer_timeline}
    assert timeline["safety_check"].outcome == "needs_review"
    assert timeline["resolution_decision"].outcome == "needs_review"
    assert "additional risk checks" in result.customer_summary.lower()
    assert "chargeback" not in result.customer_summary.lower()
