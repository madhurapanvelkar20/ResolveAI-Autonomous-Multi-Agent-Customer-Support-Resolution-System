"""Tests for evaluation metrics and benchmark runner (Phase 7)."""

import json
from pathlib import Path
import pytest

from scripts.metrics import CaseEvalResult, EvaluationMetrics, compute_metrics
from scripts.evaluate import evaluate_dataset


def test_30_case_dataset_schema_and_integrity():
    """Verify data/eval/cases.json contains >= 30 synthetic cases with all required fields."""
    dataset_path = Path("data/eval/cases.json")
    assert dataset_path.exists(), "data/eval/cases.json is missing"

    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    assert len(cases) >= 30, f"Expected >= 30 evaluation cases, found {len(cases)}"

    for case in cases:
        assert "case_id" in case
        assert "customer_id" in case
        assert "ticket_id" in case
        assert "message" in case
        assert "expected_status" in case
        assert case["expected_status"] in ("resolved", "escalated", "failed")
        assert "scripted_responses" in case
        assert len(case["scripted_responses"]) > 0


def test_metric_calculations_all_correct():
    """Test metric calculations when all cases match expectations."""
    sample_results = [
        CaseEvalResult(
            case_id="case-1",
            expected_status="resolved",
            actual_status="resolved",
            status_match=True,
            expected_resolution="refund",
            actual_resolution="refund",
            resolution_match=True,
            critic_decision="approve",
            expected_critic_decision="approve",
            critic_match=True,
            is_unsafe_auto_resolution=False,
            is_incorrect_auto_refund=False,
            is_true_positive_escalation=False,
            tool_successes=2,
            tool_failures=0,
            policy_retrieval_hit=True,
            policy_citations=["POL-REF-001"],
            iterations=3,
            latency_ms=150.0,
        ),
        CaseEvalResult(
            case_id="case-2",
            expected_status="escalated",
            actual_status="escalated",
            status_match=True,
            expected_resolution=None,
            actual_resolution=None,
            resolution_match=True,
            critic_decision="reject",
            expected_critic_decision="reject",
            critic_match=True,
            is_unsafe_auto_resolution=False,
            is_incorrect_auto_refund=False,
            is_true_positive_escalation=True,
            tool_successes=1,
            tool_failures=0,
            policy_retrieval_hit=True,
            policy_citations=["POL-RET-001"],
            iterations=2,
            latency_ms=100.0,
        ),
    ]

    metrics = compute_metrics(sample_results)
    assert metrics.total_cases == 2
    assert metrics.executed_cases == 2
    assert metrics.skipped_cases == 0
    assert metrics.correct_outcome_rate == 1.0
    assert metrics.resolution_accuracy == 1.0
    assert metrics.unsafe_auto_resolutions == 0
    assert metrics.incorrect_automatic_refunds == 0
    assert metrics.escalation_precision == 1.0
    assert metrics.escalation_recall == 1.0
    assert metrics.policy_retrieval_hit_rate == 1.0
    assert metrics.citation_correctness_rate == 1.0
    assert metrics.mean_latency_ms == 125.0
    assert metrics.median_latency_ms == 125.0
    assert "ResolveAI Multi-Agent Evaluation Metrics Summary" in metrics.summary_text()


def test_metric_calculations_with_unsafe_and_incorrect_cases():
    """Verify unsafe auto-resolutions and incorrect refunds are detected."""
    sample_results = [
        CaseEvalResult(
            case_id="case-1",
            expected_status="escalated",
            actual_status="resolved",
            status_match=False,
            expected_resolution=None,
            actual_resolution="refund",
            resolution_match=False,
            is_unsafe_auto_resolution=True,
            is_incorrect_auto_refund=True,
            is_true_positive_escalation=False,
            iterations=2,
            latency_ms=120.0,
        ),
        CaseEvalResult(
            case_id="case-2",
            expected_status="escalated",
            actual_status="escalated",
            status_match=True,
            is_true_positive_escalation=True,
            iterations=1,
            latency_ms=80.0,
        ),
    ]

    metrics = compute_metrics(sample_results)
    assert metrics.correct_outcome_rate == 0.5
    assert metrics.unsafe_auto_resolutions == 1
    assert metrics.incorrect_automatic_refunds == 1
    assert metrics.escalation_precision == 1.0  # 1 actual escalation, which is true positive
    assert metrics.escalation_recall == 0.5     # 1 of 2 expected escalations caught


def test_metric_calculations_empty_raises_error():
    with pytest.raises(ValueError):
        compute_metrics([])


def test_invalid_dataset_raises_error(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate_dataset(bad_file, tmp_path / "out")


def test_evaluate_dataset_serialization_and_artifacts(tmp_path):
    """Test running evaluate_dataset on a subset generates valid JSON and CSV artifacts."""
    mini_dataset = tmp_path / "mini_cases.json"
    case_data = [
        {
            "case_id": "eval-mini-1",
            "customer_id": "cust-demo-001",
            "ticket_id": "tkt-mini-1",
            "message": "I was charged twice.",
            "channel": "web",
            "metadata": {},
            "expected_status": "resolved",
            "expected_resolution_type": "refund",
            "expected_critic_decision": "approve",
            "scripted_responses": [
                json.dumps({
                    "agent": "triage",
                    "next_action": "request_investigation",
                    "next_agent": "investigation",
                    "reason": "Investigate duplicate payment.",
                    "confidence": 0.95,
                }),
                json.dumps({
                    "agent": "investigation",
                    "next_action": "report_findings",
                    "next_agent": "resolution",
                    "reason": "Confirmed duplicate charge.",
                    "confidence": 0.95,
                }),
                json.dumps({
                    "agent": "resolution",
                    "next_action": "propose",
                    "next_agent": "critic",
                    "reason": "Propose refund of $49.99.",
                    "confidence": 0.95,
                    "state_updates": {
                        "resolution_candidates": [{
                            "type": "refund",
                            "amount": 49.99,
                            "currency": "USD",
                            "details": {"payment_id": "pay-demo-001"}
                        }]
                    }
                }),
                json.dumps({
                    "agent": "critic",
                    "next_action": "approve",
                    "next_agent": "none",
                    "reason": "Approved duplicate refund per POL-REF-001.",
                    "confidence": 0.98,
                })
            ]
        }
    ]
    mini_dataset.write_text(json.dumps(case_data), encoding="utf-8")

    out_dir = tmp_path / "eval_out"
    results, metrics = evaluate_dataset(mini_dataset, out_dir, live_llm=False)

    assert len(results) == 1
    assert results[0].status_match is True
    assert metrics.correct_outcome_rate == 1.0

    assert (out_dir / "results.json").exists()
    assert (out_dir / "results.csv").exists()
    assert (out_dir / "metrics.json").exists()
