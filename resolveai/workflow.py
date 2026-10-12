"""LangGraph orchestration for ResolveAI's four-agent workflow."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from resolveai.config import Settings, get_settings
from resolveai.llm import (
    InvalidAgentOutput,
    LLMError,
    StructuredLLM,
)
from resolveai.llm_factory import build_llm
from resolveai.policies import retrieve_policies
from resolveai.schemas import (
    AgentDecision,
    CaseResult,
    CaseState,
    CriticFeedback,
    Evidence,
    TicketIn,
)
from resolveai.state import CaseStateStore
from resolveai.tools import execute_tool
from resolveai.tracing import TraceLogger


class WorkflowInput(TypedDict):
    ticket: dict[str, Any]


class WorkflowContext(TypedDict, total=False):
    case_state: dict[str, Any]
    result: dict[str, Any]
    error: str


AGENT_PROMPTS = {
    "triage": (
        "Classify the customer's issue, identify missing information, "
        "and plan investigation. Do not invent evidence."
    ),
    "investigation": (
        "Investigate using authorized tools. Base conclusions on tool "
        "results and policy evidence. Do not invent facts."
    ),
    "resolution": (
        "Propose a policy-compliant resolution based on verified evidence. "
        "Never claim a refund or other action succeeded without tool evidence."
    ),
    "critic": (
        "Independently evaluate the proposed resolution against evidence "
        "and policy. Approve only when adequately supported. Otherwise reject "
        "or request evidence."
    ),
}


def _dump_state(state: CaseState) -> dict[str, Any]:
    return state.model_dump(mode="json")


def _build_result(
    state: CaseState,
    status: str,
    response: str,
    trace_id: str,
    critic_decision: str | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=state.case_id,
        status=status,
        customer_response=response,
        resolution=state.selected_resolution,
        confidence=state.confidence,
        agents_involved=list(
            dict.fromkeys(decision.agent for decision in state.agent_decisions)
        ),
        tools_used=state.tools_used,
        iterations=state.iteration,
        critic_decision=critic_decision,
        escalation_reason=state.escalation_reason,
        trace_id=trace_id,
    )


class ResolveAIWorkflow:
    """Run triage, investigation, resolution, and critic with bounded routing."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: Any = None,
        tracer: Any = None,
        policy_dir: str = "docs/policies",
    ):
        self.settings = settings or get_settings()
        self.llm = llm or build_llm(self.settings)
        self.structured_llm = StructuredLLM(self.llm)
        self.tracer = tracer
        self.policy_dir = policy_dir
        self._last_critic_decision: str | None = None

        graph = StateGraph(WorkflowContext)
        graph.add_node("run_agent", self._run_agent)
        graph.add_node("execute_tool", self._execute_tool)
        graph.add_node("finish", self._finish)
        graph.set_entry_point("run_agent")
        graph.add_conditional_edges(
            "run_agent",
            self._route,
            {
                "run_agent": "run_agent",
                "execute_tool": "execute_tool",
                "finish": "finish",
            },
        )
        graph.add_conditional_edges(
            "execute_tool",
            self._after_tool,
            {"run_agent": "run_agent", "finish": "finish"},
        )
        graph.add_edge("finish", END)
        self.graph = graph.compile()

    def _log(self, state: CaseState, event: str, **kwargs: Any) -> None:
        if self.tracer is not None:
            self.tracer.log(
                case_id=state.case_id,
                iteration=state.iteration,
                event=event,
                **kwargs,
            )

    def _run_agent(self, context: WorkflowContext) -> dict[str, Any]:
        state = CaseState.model_validate(context["case_state"])
        if state.iteration >= self.settings.max_iterations:
            state.status = "escalated"
            state.escalation_reason = "Maximum workflow iterations reached"
            self._log(
                state,
                "safety_limit",
                reason_summary=state.escalation_reason,
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        agent = self._next_agent(state)
        if agent is None:
            return {"case_state": _dump_state(state), "result": {"done": True}}

        state.iteration += 1
        policy_query = (
            state.ticket.message
            + " "
            + " ".join(state.plan)
            + " "
            + (state.current_hypothesis or "")
        )
        try:
            matches = retrieve_policies(
                policy_query, self.policy_dir, top_k=3
            )
            policy_text = "\n\n".join(
                f"[{match.source}] {match.text}" for match in matches
            ) or "No matching policy paragraphs found."
        except (OSError, ValueError) as exc:
            policy_text = f"Policy retrieval unavailable: {exc}"

        prompt = (
            f"Ticket:\n{state.ticket.model_dump_json()}\n\n"
            f"Current case state:\n{state.model_dump_json()}\n\n"
            f"Retrieved policies:\n{policy_text}\n\n"
            f"Current agent: {agent}\n"
            "Return one JSON object matching the AgentDecision schema. "
            "Use only allowed actions for your agent. For call_tool, provide "
            "the registered tool name and arguments. State updates must only "
            "contain fields this agent is permitted to write."
        )
        try:
            decision = self.structured_llm.decide(
                agent,
                AGENT_PROMPTS[agent],
                prompt,
                AgentDecision,
                tracer=self.tracer,
            )
        except (LLMError, ValidationError, ValueError) as exc:
            state.status = "escalated"
            state.escalation_reason = (
                f"Agent {agent} could not produce a valid decision"
            )
            self._log(
                state,
                "llm_failure",
                agent=agent,
                reason_summary=str(exc)[:250],
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        state.agent_decisions.append(decision)
        self._log(
            state,
            "agent_decision",
            agent=agent,
            decision=decision.next_action,
            reason_summary=decision.reason,
            confidence=decision.confidence,
        )

        try:
            store = CaseStateStore(state)
            store.write(agent, decision.state_updates)
            state = store.state
        except (ValueError, PermissionError) as exc:
            state.status = "escalated"
            state.escalation_reason = "Agent attempted an invalid state update"
            self._log(
                state,
                "safety_limit",
                agent=agent,
                reason_summary=str(exc)[:250],
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        # Apply authorized updates through the store's validated state.

        if decision.next_action == "human_escalation":
            state.status = "escalated"
            state.escalation_reason = decision.reason
            self._log(
                state,
                "escalation",
                agent=agent,
                reason_summary=decision.reason,
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        if agent == "critic":
            feedback = CriticFeedback(
                decision=decision.next_action,
                reason=decision.reason,
                missing_evidence=[],
                recommended_next_action=(
                    None if decision.next_action == "approve"
                    else decision.reason
                ),
                confidence=decision.confidence,
            )
            state.critic_feedback.append(feedback)
            self._last_critic_decision = decision.next_action

            if decision.next_action == "approve":
                if state.selected_resolution is None:
                    state.status = "failed"
                    self._log(
                        state,
                        "safety_limit",
                        agent=agent,
                        reason_summary="Critic approved without a selected resolution",
                    )
                else:
                    state.status = "resolved"
            elif decision.next_action == "reject":
                state.selected_resolution = None
                state.status = "open"
            else:
                state.status = "open"

        if decision.next_action == "call_tool":
            context["case_state"] = _dump_state(state)
            return {
                "case_state": _dump_state(state),
                "result": {
                    "done": False,
                    "tool_name": decision.tool_call.name,
                    "tool_args": decision.tool_call.args,
                },
            }

        if decision.next_action == "propose":
            if not state.resolution_candidates:
                state.status = "failed"
            else:
                state.selected_resolution = state.resolution_candidates[-1]
                state.status = "open"

        return {
            "case_state": _dump_state(state),
            "result": {"done": state.status in {"resolved", "escalated", "failed"}},
        }

    def _execute_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        state = CaseState.model_validate(data["case_state"])
        result = data.get("result", {})

        name = result.get("tool_name")
        args = result.get("tool_args", {})

        if not name:
            tool_result = {
                "ok": False,
                "error": "Missing tool name",
            }
        else:
            tool_result = execute_tool(name, args)

        state.tools_used.append(name or "unknown_tool")

        state.evidence.append(
            Evidence(
                source=f"tool:{name or 'unknown_tool'}",
                status="supports" if tool_result.get("ok") else "tool_failure",
                summary=str(tool_result)[:1000],
                details=tool_result,
            )
        )

        data["case_state"] = state.model_dump(mode="json")
        data["result"] = {
            **result,
            "last_tool_result": tool_result,
        }

        return data

    def _route(self, context: WorkflowContext) -> str:
        result = context.get("result", {})
        if result.get("done"):
            return "finish"
        if result.get("tool_name"):
            return "execute_tool"
        return "run_agent"

    def _after_tool(self, context: WorkflowContext) -> str:
        state = CaseState.model_validate(context["case_state"])
        if len(state.tools_used) >= self.settings.max_tool_calls:
            state.status = "escalated"
            state.escalation_reason = "Maximum tool calls reached"
            context["case_state"] = _dump_state(state)
            self._log(
                state,
                "safety_limit",
                reason_summary=state.escalation_reason,
            )
            return "finish"
        return "run_agent"

    def _next_agent(self, state: CaseState) -> str | None:
        if state.status in {"resolved", "escalated", "failed"}:
            return None
        if not state.agent_decisions:
            return "triage"

        previous = state.agent_decisions[-1]
        action = previous.next_action
        if action == "request_investigation":
            return "investigation"
        if action == "report_findings":
            return "resolution"
        if action == "request_replan":
            return "triage"
        if action in {"propose", "request_evidence"}:
            return "critic" if action == "propose" else "investigation"
        if action in {"approve", "reject"}:
            return "resolution" if action == "reject" else None
        if action == "ask_customer":
            state.status = "escalated"
            state.escalation_reason = "Additional customer information is required"
            return None
        if action == "human_escalation":
            return None
        if action == "call_tool":
            return previous.agent
        return "triage"

    def _finish(self, context: WorkflowContext) -> dict[str, Any]:
        state = CaseState.model_validate(context["case_state"])
        trace_id = getattr(self.tracer, "trace_id", "trace-unavailable")

        if state.status == "resolved":
            response = "Your case has been resolved based on the approved resolution."
        elif state.status == "escalated":
            response = (
                "Your case has been escalated for human review. "
                "We will follow up when more information is available."
            )
        else:
            state.status = "failed"
            response = (
                "We could not safely complete your case automatically. "
                "Please contact support for further assistance."
            )

        result = _build_result(
            state,
            state.status,
            response,
            trace_id,
            self._last_critic_decision,
        )
        self._log(state, "final", decision=state.status, message=response)
        return {
            "case_state": _dump_state(state),
            "result": result.model_dump(mode="json"),
        }

    def run(self, ticket: TicketIn | dict[str, Any]) -> CaseResult:
        """Run one ticket through the compiled workflow."""
        ticket = ticket if isinstance(ticket, TicketIn) else TicketIn.model_validate(ticket)
        case_id = f"case-{ticket.ticket_id}"
        initial = CaseState(case_id=case_id, ticket=ticket)
        if self.tracer is None:
            self.tracer = TraceLogger(self.settings.trace_dir)

        self._log(initial, "case_start", message="Case workflow started")
        output = self.graph.invoke({
            "ticket": ticket.model_dump(mode="json"),
            "case_state": _dump_state(initial),
            "result": {"done": False},
        })
        return CaseResult.model_validate(output["result"])