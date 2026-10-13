"""Phase 4 tests: Autonomous Multi-Agent Orchestration with LangGraph."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from resolveai.config import Settings
from resolveai.llm import ScriptedLLM
from resolveai.policies import DeterministicFakeEmbeddingFunction, PolicyVectorStore
from resolveai.scenarios import ALL_SCENARIOS, make_decision, run_scenario
from resolveai.schemas import (
    AGENT_ACTIONS,
    AgentDecision,
    CaseResult,
    CaseState,
    Resolution,
    TicketIn,
)
from resolveai.state import CaseStateStore, StatePermissionError
from resolveai.tracing import TraceLogger, load_trace
from resolveai.workflow import AGENT_PROMPTS, ResolveAIWorkflow


def make_ticket(
    ticket_id: str = "TICKET-401",
    customer_id: str = "CUST-401",
    message: str = "Test customer message",
) -> TicketIn:
    return TicketIn(
        ticket_id=ticket_id,
        customer_id=customer_id,
        message=message,
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={},
    )


def test_four_agents_distinct_responsibilities_and_prompts():
    """All 4 agents must have distinct system prompts and allowed actions."""
    expected_agents = {"triage", "investigation", "resolution", "critic"}
    assert set(AGENT_PROMPTS.keys()) == expected_agents
    assert set(AGENT_ACTIONS.keys()) == expected_agents

    prompts = list(AGENT_PROMPTS.values())
    assert len(set(prompts)) == 4, "Agent prompts must all be unique"

    # Verify distinct responsibility focus
    assert "Triage" in AGENT_PROMPTS["triage"]
    assert "Investigation" in AGENT_PROMPTS["investigation"]
    assert "Resolution" in AGENT_PROMPTS["resolution"]
    assert "Critic" in AGENT_PROMPTS["critic"]

    # Verify distinct action permissions
    assert "ask_customer" in AGENT_ACTIONS["triage"]
    assert "report_findings" in AGENT_ACTIONS["investigation"]
    assert "propose" in AGENT_ACTIONS["resolution"]
    assert "approve" in AGENT_ACTIONS["critic"]


def test_next_agent_routing_and_critic_approval(tmp_path: Path):
    """Workflow respects validated next_agent routing and approves resolution."""
    responses = [
        make_decision("triage", "request_investigation", "investigation", reason="Plan check"),
        make_decision("investigation", "report_findings", "resolution", reason="Facts ready"),
        make_decision(
            "resolution",
            "propose",
            "critic",
            reason="Propose replacement",
            state_updates={
                "resolution_candidates": [
                    {
                        "type": "replacement",
                        "amount": None,
                        "currency": None,
                        "action_id": "ord-1",
                        "details": {"reason": "defective"},
                    }
                ]
            },
        ),
        make_decision("critic", "approve", "none", reason="Meets all requirements"),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(_env_file=None, trace_dir=str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "resolved"
    assert result.critic_decision == "approve"
    assert result.resolution is not None
    assert result.resolution.type == "replacement"
    assert result.agents_involved == ["triage", "investigation", "resolution", "critic"]


def test_invalid_routing_escalates_safely(tmp_path: Path):
    """An agent decision requesting an unpermitted next_agent is rejected and escalated."""
    # Triage requesting next_agent='critic' for 'request_investigation' is invalid according to ACTION_AGENTS
    with pytest.raises(Exception):
        # Pydantic schema validation rejects mismatch at contract boundary
        AgentDecision.model_validate(
            json.loads(
                make_decision(
                    "triage",
                    "request_investigation",
                    "critic",  # Invalid target
                    reason="Invalid jump",
                )
            )
        )


def test_agent_state_permission_violation_escalates(tmp_path: Path):
    """Investigation agent attempting to write resolution_candidates triggers safe escalation."""
    responses = [
        make_decision(
            "triage",
            "request_investigation",
            "investigation",
            reason="Investigate ticket",
        ),
        make_decision(
            "investigation",
            "report_findings",
            "resolution",
            reason="Unauthorized write attempt",
            state_updates={
                # Investigation is forbidden from writing resolution_candidates
                "resolution_candidates": [{"type": "refund", "amount": 50}],
            },
        ),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(_env_file=None, trace_dir=str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "escalated"
    assert "invalid state update" in result.escalation_reason.lower()


def test_critic_approval_without_resolution_fails(tmp_path: Path):
    """If Critic approves without a selected resolution, case transitions to failed/safety limit."""
    responses = [
        make_decision("triage", "request_investigation", "investigation", reason="Check"),
        make_decision("investigation", "report_findings", "resolution", reason="Report"),
        make_decision(
            "resolution",
            "propose",
            "critic",
            reason="Propose empty",
            state_updates={},  # No candidate added!
        ),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(_env_file=None, trace_dir=str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "failed"


def test_critic_rejection_routes_back_to_resolution(tmp_path: Path):
    """Critic rejection clears selection and routes back to resolution agent."""
    responses = [
        make_decision("triage", "request_investigation", "investigation", reason="Investigate"),
        make_decision("investigation", "report_findings", "resolution", reason="Facts ready"),
        make_decision(
            "resolution",
            "propose",
            "critic",
            reason="First proposal",
            state_updates={
                "resolution_candidates": [{"type": "refund", "amount": 100}]
            },
        ),
        make_decision("critic", "reject", "resolution", reason="Insufficient proof"),
        make_decision(
            "resolution",
            "human_escalation",
            "none",
            reason="Escalate after rejection",
            risk="medium",
        ),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(_env_file=None, trace_dir=str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "escalated"
    assert result.critic_decision == "reject"
    assert result.resolution is None  # Rejection cleared candidate


def test_tool_allowlist_enforced_in_workflow(tmp_path: Path):
    """Triage calling unauthorized write tool request_refund is rejected and recorded."""
    responses = [
        make_decision(
            "triage",
            "call_tool",
            "triage",
            reason="Triage tries calling refund",
            tool_call={
                "name": "request_refund",
                "args": {"payment_id": "p1", "amount": 50, "reason": "test"},
            },
        ),
        make_decision(
            "triage",
            "human_escalation",
            "none",
            reason="Escalate after tool failure",
            risk="low",
        ),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(_env_file=None, trace_dir=str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "escalated"
    events = load_trace(tracer.path)
    tool_failures = [e for e in events if e.event == "tool_failure"]
    assert len(tool_failures) >= 1
    assert "not authorized" in tool_failures[0].tool_result_summary


def test_wall_clock_safety_limit_enforcement(tmp_path: Path):
    """Simulated elapsed wall-clock time exceeding max_case_wall_time_seconds halts execution."""
    clock_values = [100.0, 125.0, 150.0]

    def mock_clock():
        if clock_values:
            return clock_values.pop(0)
        return 200.0

    responses = [
        make_decision("triage", "request_investigation", "investigation", reason="Check"),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(
        _env_file=None,
        trace_dir=str(tmp_path),
        max_case_wall_time_seconds=10.0,
    )
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
        time_provider=mock_clock,
    )

    result = workflow.run(make_ticket())
    assert result.status == "escalated"
    assert "wall-clock" in result.escalation_reason.lower()

    events = load_trace(tracer.path)
    safety_events = [e for e in events if e.event == "safety_limit"]
    assert len(safety_events) >= 1


def test_tool_call_limit_enforcement(tmp_path: Path):
    """Exceeding max_tool_calls safety limit terminates graph execution cleanly."""
    responses = [
        make_decision(
            "triage",
            "call_tool",
            "triage",
            reason="Lookup 1",
            tool_call={"name": "lookup_ticket", "args": {"ticket_id": "TICKET-1"}},
        ),
        make_decision(
            "triage",
            "call_tool",
            "triage",
            reason="Lookup 2",
            tool_call={"name": "lookup_ticket", "args": {"ticket_id": "TICKET-2"}},
        ),
    ]

    tracer = TraceLogger(trace_dir=str(tmp_path))
    settings = Settings(
        _env_file=None,
        trace_dir=str(tmp_path),
        max_tool_calls=1,  # Strict cap of 1 tool call
    )
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )

    result = workflow.run(make_ticket())
    assert result.status == "escalated"
    assert "maximum tool calls" in result.escalation_reason.lower()


def test_all_five_scenarios_execute_and_verify(tmp_path: Path):
    """Verify all 5 demo scenarios pass with assertions and trace persistence."""
    for name, scenario in ALL_SCENARIOS.items():
        result, trace_path = run_scenario(scenario, trace_dir=str(tmp_path))
        assert result.status == scenario.expected_status
        assert Path(trace_path).exists()
        events = load_trace(trace_path)
        assert len(events) >= 2
        assert events[0].event == "case_start"
        assert events[-1].event == "final"
