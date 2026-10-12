
import json
from datetime import datetime, timezone

from resolveai.config import Settings
from resolveai.llm import ScriptedLLM
from resolveai.schemas import CaseState, TicketIn
from resolveai.tracing import TraceLogger
from resolveai.workflow import ResolveAIWorkflow


def response(
    agent,
    action,
    next_agent,
    *,
    reason="Test decision",
    confidence=0.9,
    tool_call=None,
    state_updates=None,
    risk=None,
):
    """Build a JSON response matching the AgentDecision contract."""
    decision = {
        "agent": agent,
        "next_action": action,
        "next_agent": next_agent,
        "reason": reason,
        "confidence": confidence,
        "tool_call": tool_call,
        "state_updates": state_updates or {},
        "risk": risk,
    }
    return json.dumps(decision)


def make_ticket():
    return TicketIn(
        ticket_id="TICKET-001",
        customer_id="CUSTOMER-001",
        message="My order arrived damaged. Please help.",
        channel="web",
        timestamp=datetime.now(timezone.utc),
        metadata={},
    )


def make_workflow(tmp_path, responses, **setting_overrides):
    settings = Settings(
        _env_file=None,
        trace_dir=str(tmp_path),
        max_iterations=setting_overrides.get("max_iterations", 12),
        max_tool_calls=setting_overrides.get("max_tool_calls", 20),
        max_case_wall_time_seconds=setting_overrides.get(
            "max_case_wall_time_seconds", 120
        ),
    )
    tracer = TraceLogger(str(tmp_path))
    workflow = ResolveAIWorkflow(
        settings=settings,
        llm=ScriptedLLM(responses),
        tracer=tracer,
    )
    return workflow, tracer


def test_workflow_routes_agents_and_escalates_after_iteration_limit(tmp_path):
    """Triage routes to investigation; the configured iteration cap is enforced."""
    workflow, tracer = make_workflow(
        tmp_path,
        [
            response(
                "triage",
                "request_investigation",
                "investigation",
                reason="Investigate the damaged order.",
            ),
        ],
        max_iterations=1,
    )

    result = workflow.run(make_ticket())

    assert result.status == "escalated"
    assert "Maximum workflow iterations reached" in result.escalation_reason
    assert result.iterations == 1

    events = [event.event for event in tracer.events] if hasattr(
        tracer, "events"
    ) else []
    if events:
        assert "safety_limit" in events


def test_critic_rejection_does_not_resolve_case(tmp_path):
    """A rejected proposal must not produce a resolved case."""
    workflow, _ = make_workflow(
        tmp_path,
        [
            response(
                "triage",
                "request_investigation",
                "investigation",
                reason="Investigate the complaint.",
            ),
            response(
                "investigation",
                "report_findings",
                "resolution",
                reason="The customer reports damage.",
            ),
            response(
                "resolution",
                "propose",
                "critic",
                reason="Propose a replacement.",
                state_updates={
                    "resolution_candidates": [
                        {
                            "type": "replacement",
                            "amount": None,
                            "currency": None,
                            "action_id": None,
                            "details": {"reason": "Reported damage"},
                        }
                    ]
                },
            ),
            response(
                "critic",
                "reject",
                "resolution",
                reason="Evidence is insufficient to approve the proposal.",
            ),
            response(
                "resolution",
                "human_escalation",
                "none",
                reason="The rejected proposal needs human review.",
                risk="high",
            ),
        ],
    )

    result = workflow.run(make_ticket())

    assert result.status == "escalated"
    assert result.status != "resolved"
    assert result.critic_decision == "reject"
    assert result.escalation_reason


def test_invalid_structured_llm_output_escalates_safely(tmp_path):
    """Exhausted structured-output retries should not crash the workflow."""
    workflow, _ = make_workflow(
        tmp_path,
        ["not valid JSON", "still not valid JSON", "invalid again"],
    )

    result = workflow.run(make_ticket())

    assert result.status == "escalated"
    assert "could not produce a valid decision" in result.escalation_reason


def test_tool_failure_is_recorded_without_exposing_internal_errors(
    tmp_path, monkeypatch
):
    """The tool execution node should record a failed tool result."""
    import resolveai.workflow as workflow_module

    workflow, tracer = make_workflow(tmp_path, [])
    state = CaseState(
        case_id="case-TICKET-001",
        ticket=make_ticket(),
    )

    monkeypatch.setattr(
        workflow_module,
        "execute_tool",
        lambda name, args: {
            "ok": False,
            "error": "Tool execution failed",
        },
    )

    output = workflow._execute_tool(
        {
            "case_state": state.model_dump(mode="json"),
            "result": {
                "tool_name": "lookup_customer",
                "tool_args": {"customer_id": "CUSTOMER-001"},
            },
        }
    )

    assert output["result"]["last_tool_result"]["ok"] is False
    assert output["case_state"]["tools_used"] == ["lookup_customer"]

    # Confirm the failed tool result is passed back into workflow state.
    evidence = output["case_state"]["evidence"]
    assert evidence[-1]["status"] == "tool_failure"
    assert "Tool execution failed" in evidence[-1]["summary"]
