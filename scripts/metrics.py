"""Evaluation metrics calculation for ResolveAI multi-agent support workflows."""

import statistics
from typing import Any
from pydantic import BaseModel, Field


class CaseEvalResult(BaseModel):
    """Execution outcome of a single evaluation case."""

    case_id: str
    expected_status: str
    actual_status: str
    status_match: bool
    expected_resolution: str | None = None
    actual_resolution: str | None = None
    resolution_match: bool = True
    critic_decision: str | None = None
    expected_critic_decision: str | None = None
    critic_match: bool = True
    is_unsafe_auto_resolution: bool = False
    is_incorrect_auto_refund: bool = False
    is_true_positive_escalation: bool = False
    tools_used: list[str] = Field(default_factory=list)
    tool_successes: int = 0
    tool_failures: int = 0
    policy_retrieval_hit: bool = False
    policy_citations: list[str] = Field(default_factory=list)
    citations_valid: bool = True
    iterations: int = 0
    latency_ms: float = 0.0
    trace_id: str | None = None
    error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None


class EvaluationMetrics(BaseModel):
    """Aggregate benchmark metrics with clear explanations of denominators."""

    total_cases: int
    executed_cases: int
    skipped_cases: int
    correct_outcome_rate: float
    correct_outcomes: int
    resolution_accuracy: float
    correct_resolutions: int
    expected_resolved_total: int
    unsafe_auto_resolutions: int
    incorrect_automatic_refunds: int
    escalation_precision: float
    true_positive_escalations: int
    actual_escalations_total: int
    escalation_recall: float
    expected_escalations_total: int
    policy_retrieval_hit_rate: float
    policy_retrieval_hits: int
    citation_correctness_rate: float
    valid_citations_count: int
    total_citations_count: int
    tool_success_count: int
    tool_failure_count: int
    mean_latency_ms: float
    median_latency_ms: float
    mean_iterations: float
    iteration_distribution: dict[int, int]
    critic_approval_count: int
    critic_rejection_count: int
    critic_request_evidence_count: int
    critic_audit_accuracy: float
    failures_count: int
    provider_cost: str = "0.00 USD (deterministic scripted evaluation, 0 cloud tokens billed)"

    def summary_text(self) -> str:
        """Render a readable human explanation of metrics and denominators."""
        return (
            "======================================================================\n"
            "               ResolveAI Multi-Agent Evaluation Metrics Summary        \n"
            "======================================================================\n"
            f"Total Evaluated Cases:         {self.executed_cases} / {self.total_cases} (Skipped: {self.skipped_cases})\n"
            f"Correct Final Outcome Rate:    {self.correct_outcome_rate:.2%} ({self.correct_outcomes}/{self.executed_cases} cases matched expected status)\n"
            f"Resolution Accuracy:           {self.resolution_accuracy:.2%} ({self.correct_resolutions}/{self.expected_resolved_total} expected resolved cases matched)\n"
            f"Unsafe Auto-Resolutions:       {self.unsafe_auto_resolutions} (Cases resolved automatically that should have been escalated/denied)\n"
            f"Incorrect Auto-Refunds:        {self.incorrect_automatic_refunds} (Unauthorized or ineligible refunds issued)\n"
            f"Escalation Precision:          {self.escalation_precision:.2%} ({self.true_positive_escalations}/{self.actual_escalations_total} actual escalations were true positive)\n"
            f"Escalation Recall:             {self.escalation_recall:.2%} ({self.true_positive_escalations}/{self.expected_escalations_total} required escalations successfully triggered)\n"
            f"Policy Retrieval Hit Rate:     {self.policy_retrieval_hit_rate:.2%} ({self.policy_retrieval_hits}/{self.executed_cases} cases verified policy documentation)\n"
            f"Citation Correctness:          {self.citation_correctness_rate:.2%} ({self.valid_citations_count}/{max(1, self.total_citations_count)} citations matched standard POL-* identifiers)\n"
            f"Critic Approvals:              {self.critic_approval_count}\n"
            f"Critic Rejections / Audits:    {self.critic_rejection_count} rejections, {self.critic_request_evidence_count} evidence requests\n"
            f"Tool Execution Activity:       {self.tool_success_count} succeeded, {self.tool_failure_count} handled failures\n"
            f"Workflow Latency:              Mean {self.mean_latency_ms:.1f} ms | Median {self.median_latency_ms:.1f} ms\n"
            f"Mean Iterations:               {self.mean_iterations:.1f} agent steps per case\n"
            f"Workflow Failures:             {self.failures_count}\n"
            f"Estimated Cloud Cost:          {self.provider_cost}\n"
            "======================================================================\n"
        )


def compute_metrics(results: list[CaseEvalResult]) -> EvaluationMetrics:
    """Compute benchmark metrics from evaluation outcomes."""
    total = len(results)
    if total == 0:
        raise ValueError("Cannot compute metrics on empty results list")

    executed = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    exec_count = len(executed)

    if exec_count == 0:
        return EvaluationMetrics(
            total_cases=total,
            executed_cases=0,
            skipped_cases=len(skipped),
            correct_outcome_rate=0.0,
            correct_outcomes=0,
            resolution_accuracy=0.0,
            correct_resolutions=0,
            expected_resolved_total=0,
            unsafe_auto_resolutions=0,
            incorrect_automatic_refunds=0,
            escalation_precision=0.0,
            true_positive_escalations=0,
            actual_escalations_total=0,
            escalation_recall=0.0,
            expected_escalations_total=0,
            policy_retrieval_hit_rate=0.0,
            policy_retrieval_hits=0,
            citation_correctness_rate=0.0,
            valid_citations_count=0,
            total_citations_count=0,
            tool_success_count=0,
            tool_failure_count=0,
            mean_latency_ms=0.0,
            median_latency_ms=0.0,
            mean_iterations=0.0,
            iteration_distribution={},
            critic_approval_count=0,
            critic_rejection_count=0,
            critic_request_evidence_count=0,
            critic_audit_accuracy=0.0,
            failures_count=0,
        )

    correct_outcomes = sum(1 for r in executed if r.status_match)
    correct_outcome_rate = correct_outcomes / exec_count

    expected_resolved = [r for r in executed if r.expected_status == "resolved"]
    expected_resolved_total = len(expected_resolved)
    correct_resolutions = sum(
        1 for r in expected_resolved if r.status_match and r.resolution_match
    )
    resolution_accuracy = (
        correct_resolutions / expected_resolved_total if expected_resolved_total > 0 else 1.0
    )

    unsafe_auto_resolutions = sum(1 for r in executed if r.is_unsafe_auto_resolution)
    incorrect_auto_refunds = sum(1 for r in executed if r.is_incorrect_auto_refund)

    actual_escalations = [r for r in executed if r.actual_status == "escalated"]
    actual_escalations_total = len(actual_escalations)
    expected_escalations = [r for r in executed if r.expected_status == "escalated"]
    expected_escalations_total = len(expected_escalations)

    true_pos_escalations = sum(1 for r in executed if r.is_true_positive_escalation)
    escalation_precision = (
        true_pos_escalations / actual_escalations_total
        if actual_escalations_total > 0
        else (1.0 if expected_escalations_total == 0 else 0.0)
    )
    escalation_recall = (
        true_pos_escalations / expected_escalations_total
        if expected_escalations_total > 0
        else 1.0
    )

    policy_hits = sum(1 for r in executed if r.policy_retrieval_hit)
    policy_hit_rate = policy_hits / exec_count

    total_citations = sum(len(r.policy_citations) for r in executed)
    valid_citations = sum(
        sum(1 for c in r.policy_citations if "POL-" in c) for r in executed
    )
    citation_correctness_rate = (
        valid_citations / total_citations if total_citations > 0 else 1.0
    )

    tool_successes = sum(r.tool_successes for r in executed)
    tool_failures = sum(r.tool_failures for r in executed)

    latencies = [r.latency_ms for r in executed]
    mean_latency = statistics.mean(latencies) if latencies else 0.0
    median_latency = statistics.median(latencies) if latencies else 0.0

    iterations = [r.iterations for r in executed]
    mean_iterations = statistics.mean(iterations) if iterations else 0.0
    iter_dist: dict[int, int] = {}
    for it in iterations:
        iter_dist[it] = iter_dist.get(it, 0) + 1

    critic_approvals = sum(
        1 for r in executed if r.critic_decision == "approve"
    )
    critic_rejections = sum(
        1 for r in executed if r.critic_decision == "reject"
    )
    critic_req_evidence = sum(
        1 for r in executed if r.critic_decision == "request_evidence"
    )
    critic_matches = sum(1 for r in executed if r.critic_match)
    critic_audit_accuracy = critic_matches / exec_count

    failures = sum(1 for r in executed if r.actual_status == "failed")

    return EvaluationMetrics(
        total_cases=total,
        executed_cases=exec_count,
        skipped_cases=len(skipped),
        correct_outcome_rate=round(correct_outcome_rate, 4),
        correct_outcomes=correct_outcomes,
        resolution_accuracy=round(resolution_accuracy, 4),
        correct_resolutions=correct_resolutions,
        expected_resolved_total=expected_resolved_total,
        unsafe_auto_resolutions=unsafe_auto_resolutions,
        incorrect_automatic_refunds=incorrect_auto_refunds,
        escalation_precision=round(escalation_precision, 4),
        true_positive_escalations=true_pos_escalations,
        actual_escalations_total=actual_escalations_total,
        escalation_recall=round(escalation_recall, 4),
        expected_escalations_total=expected_escalations_total,
        policy_retrieval_hit_rate=round(policy_hit_rate, 4),
        policy_retrieval_hits=policy_hits,
        citation_correctness_rate=round(citation_correctness_rate, 4),
        valid_citations_count=valid_citations,
        total_citations_count=total_citations,
        tool_success_count=tool_successes,
        tool_failure_count=tool_failures,
        mean_latency_ms=round(mean_latency, 2),
        median_latency_ms=round(median_latency, 2),
        mean_iterations=round(mean_iterations, 2),
        iteration_distribution=dict(sorted(iter_dist.items())),
        critic_approval_count=critic_approvals,
        critic_rejection_count=critic_rejections,
        critic_request_evidence_count=critic_req_evidence,
        critic_audit_accuracy=round(critic_audit_accuracy, 4),
        failures_count=failures,
    )
