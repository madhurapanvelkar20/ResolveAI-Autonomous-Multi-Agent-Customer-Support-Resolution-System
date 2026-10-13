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


def test_scenario_ineligible_refund(tmp_path):
    result, trace_path = run_scenario(SCENARIO_INELIGIBLE_REFUND, trace_dir=str(tmp_path))
    assert result.status == "escalated"
    assert result.status != "resolved"
    assert result.resolution is None
    assert "exceeds" in result.escalation_reason.lower() or "human" in result.escalation_reason.lower()


def test_scenario_damaged_product_missing_evidence(tmp_path):
    result, trace_path = run_scenario(SCENARIO_DAMAGED_PRODUCT, trace_dir=str(tmp_path))
    assert result.status == "escalated"
    assert result.resolution is None
    assert "information" in result.escalation_reason.lower() or "photo" in result.escalation_reason.lower()


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
