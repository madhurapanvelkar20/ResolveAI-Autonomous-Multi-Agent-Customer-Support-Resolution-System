"""LangGraph orchestration for ResolveAI's four-agent workflow."""

import time
from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from resolveai.config import Settings, get_settings
from resolveai.llm import (
    InvalidAgentOutput,
    LLMError,
    StructuredLLM,
)
from resolveai.llm_factory import build_llm
from resolveai.policies import PolicyVectorStore, retrieve_policies
from resolveai.schemas import (
    ACTION_AGENTS,
    AgentDecision,
    CaseResult,
    CaseState,
    CriticFeedback,
    Evidence,
    TicketIn,
)
from resolveai.state import CaseStateStore, StatePermissionError
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
        "You are ResolveAI's Triage Agent. Classify the customer's issue, "
        "identify missing information, evaluate initial risk, and formulate "
        "an investigation plan. Use read-only tools if needed. Do not invent "
        "facts, perform resolution write actions, or issue refunds. "
        "If more customer info is required, use ask_customer (next_agent='none'). "
        "If investigation is needed, use request_investigation (next_agent='investigation'). "
        "If severe risk or threats are detected, use human_escalation (next_agent='none')."
    ),
    "investigation": (
        "You are ResolveAI's Investigation Agent. Gather factual evidence using "
        "authorized read tools (lookup_customer, lookup_ticket, lookup_order, "
        "lookup_payment, search_tickets) and search the policy knowledge base via "
        "search_knowledge_base. Distinguish confirmed system facts, customer claims, "
        "and unknowns. Do not invent facts or propose financial refunds directly. "
        "When facts and policy evidence are collected, report findings to resolution "
        "using report_findings (next_agent='resolution'). If replanning is needed, "
        "use request_replan (next_agent='triage'). If fraud is detected, use human_escalation."
    ),
    "resolution": (
        "You are ResolveAI's Resolution Agent. Propose policy-compliant resolutions "
        "supported by verified case facts, policy citations, and configured limits. "
        "Autonomous refunds may not exceed $100.00 USD. You cannot perform write "
        "actions directly; formulate resolution candidates in state_updates and "
        "submit them for Critic review using propose (next_agent='critic'). If key "
        "facts are missing, request evidence using request_evidence (next_agent='investigation'). "
        "If claims violate policy, exceed limits, or cannot be resolved, use human_escalation."
    ),
    "critic": (
        "You are ResolveAI's Critic Agent. Conduct an independent, adversarial audit "
        "of the proposed resolution against case facts, policy evidence, and safety limits. "
        "Check financial limits ($100 max auto-refund), required evidence (photos for damage), "
        "and fraud flags. Approve ONLY when evidence is complete and strictly adheres to policy. "
        "If evidence is insufficient or policy is violated, reject (next_agent='resolution') "
        "or request_evidence (next_agent='investigation'). Never approve an unsupported resolution."
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
    """Run triage, investigation, resolution, and critic with bounded LangGraph routing."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: Any = None,
        tracer: Any = None,
        policy_dir: str = "docs/policies",
        vector_store: Any = None,
        time_provider: Callable[[], float] = time.perf_counter,
    ):
        self.settings = settings or get_settings()
        self.llm = llm or build_llm(self.settings)
        self.structured_llm = StructuredLLM(self.llm)
        self.tracer = tracer
        self.policy_dir = policy_dir
        self.vector_store = vector_store
        self.time_provider = time_provider
        self._start_time: float = self.time_provider()
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

    def _check_safety_limits(self, state: CaseState) -> str | None:
        """Check iterations, tool calls, and wall-clock safety limits."""
        if state.iteration >= self.settings.max_iterations:
            return f"Maximum workflow iterations reached ({self.settings.max_iterations})"

        if len(state.tools_used) >= self.settings.max_tool_calls:
            return f"Maximum tool calls reached ({self.settings.max_tool_calls})"

        elapsed = self.time_provider() - self._start_time
        if elapsed >= self.settings.max_case_wall_time_seconds:
            return (
                f"Maximum case wall-clock duration reached "
                f"({self.settings.max_case_wall_time_seconds}s)"
            )

        return None

    def _retrieve_policy_context(self, query: str) -> str:
        """Retrieve relevant policy chunks for agent prompt context."""
        if self.vector_store is not None:
            try:
                results = self.vector_store.query(
                    query=query,
                    top_k=self.settings.rag_top_k,
                    relevance_threshold=self.settings.rag_relevance_threshold,
                )
                if results:
                    return "\n\n".join(
                        f"[{r.citation}] {r.text}" for r in results
                    )
            except Exception as exc:
                return f"Vector policy retrieval unavailable: {exc}"

        try:
            matches = retrieve_policies(
                query=query,
                policy_dir=self.policy_dir,
                top_k=self.settings.rag_top_k,
            )
            if matches:
                return "\n\n".join(
                    f"[{m.citation or m.source}] {m.text}" for m in matches
                )
        except (OSError, ValueError) as exc:
            return f"Policy retrieval unavailable: {exc}"

        return "No matching policy paragraphs found."

    def _run_agent(self, context: WorkflowContext) -> dict[str, Any]:
        state = CaseState.model_validate(context["case_state"])

        limit_violation = self._check_safety_limits(state)
        if limit_violation is not None:
            state.status = "escalated"
            state.escalation_reason = limit_violation
            self._log(
                state,
                "safety_limit",
                reason_summary=state.escalation_reason,
                extra={"limit_type": "safety_boundary"},
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
        policy_text = self._retrieve_policy_context(policy_query)

        prompt = (
            f"Ticket:\n{state.ticket.model_dump_json()}\n\n"
            f"Current case state:\n{state.model_dump_json()}\n\n"
            f"Retrieved policy evidence (reference only):\n{policy_text}\n\n"
            f"Current agent: {agent}\n"
            "Return exactly one JSON object matching the AgentDecision schema. "
            "Use only allowed actions for your agent. For call_tool, specify "
            "the registered tool name and valid arguments. State updates must "
            "contain only fields this agent is authorized to write."
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
                f"Agent {agent} could not produce a valid decision: {exc}"
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

        # Validate state write permissions
        try:
            store = CaseStateStore(state)
            store.write(agent, decision.state_updates)
            state = store.state
        except (ValueError, PermissionError, StatePermissionError) as exc:
            state.status = "escalated"
            state.escalation_reason = f"Agent attempted an invalid state update: {exc}"
            self._log(
                state,
                "safety_limit",
                agent=agent,
                reason_summary=str(exc)[:250],
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        # Process next action outcomes
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

        if decision.next_action == "ask_customer":
            state.status = "escalated"
            state.escalation_reason = (
                f"Additional customer information required: {decision.reason}"
            )
            self._log(
                state,
                "escalation",
                agent=agent,
                reason_summary=state.escalation_reason,
            )
            return {"case_state": _dump_state(state), "result": {"done": True}}

        if agent == "critic":
            feedback = CriticFeedback(
                decision=decision.next_action,
                reason=decision.reason,
                missing_evidence=[],
                policy_citations=[],
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
                    # Enforce max refund amount safety threshold
                    res = state.selected_resolution
                    if res.amount is not None and float(res.amount) > self.settings.max_refund_amount:
                        state.status = "escalated"
                        state.escalation_reason = (
                            f"Proposed refund of ${res.amount} exceeds maximum allowed limit "
                            f"(${self.settings.max_refund_amount})"
                        )
                        self._log(
                            state,
                            "safety_limit",
                            agent=agent,
                            reason_summary=state.escalation_reason,
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
                    "agent": agent,
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

        is_done = state.status in {"resolved", "escalated", "failed"} or decision.next_agent == "none"
        return {
            "case_state": _dump_state(state),
            "result": {"done": is_done},
        }

    def _execute_tool(self, data: dict[str, Any]) -> dict[str, Any]:
        state = CaseState.model_validate(data["case_state"])
        result = data.get("result", {})

        name = result.get("tool_name")
        args = result.get("tool_args", {})
        calling_agent = result.get("agent")

        self._log(
            state,
            "tool_call",
            agent=calling_agent,
            tool=name,
            input_refs=[str(args)[:200]],
        )

        if not name:
            tool_result = {
                "ok": False,
                "error": "Missing tool name",
            }
        else:
            try:
                if calling_agent is not None:
                    tool_result = execute_tool(name, args, agent=calling_agent)
                else:
                    tool_result = execute_tool(name, args)
            except TypeError:
                tool_result = execute_tool(name, args)

        state.tools_used.append(name or "unknown_tool")

        is_ok = tool_result.get("ok", False)
        event_name = "tool_result" if is_ok else "tool_failure"
        self._log(
            state,
            event_name,
            agent=calling_agent,
            tool=name,
            tool_result_summary=str(tool_result)[:300],
        )

        state.evidence.append(
            Evidence(
                source=f"tool:{name or 'unknown_tool'}",
                status="supports" if is_ok else "tool_failure",
                summary=str(tool_result)[:1000],
                details=tool_result,
            )
        )

        limit_violation = self._check_safety_limits(state)
        is_done = False
        if limit_violation is not None:
            state.status = "escalated"
            state.escalation_reason = limit_violation
            self._log(
                state,
                "safety_limit",
                reason_summary=state.escalation_reason,
                extra={"limit_type": "safety_boundary"},
            )
            is_done = True

        data["case_state"] = state.model_dump(mode="json")
        data["result"] = {
            "done": is_done,
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
        result = context.get("result", {})
        if result.get("done"):
            return "finish"
        return "run_agent"

    def _next_agent(self, state: CaseState) -> str | None:
        """Derive next agent strictly from validated decision.next_agent field."""
        if state.status in {"resolved", "escalated", "failed"}:
            return None
        if not state.agent_decisions:
            return "triage"

        previous = state.agent_decisions[-1]
        next_agent_target = previous.next_agent

        # Validate that the requested next agent is permitted for the action
        expected_target = ACTION_AGENTS.get(previous.next_action)
        if expected_target == "same":
            expected_target = previous.agent

        if next_agent_target != expected_target:
            state.status = "escalated"
            state.escalation_reason = (
                f"Invalid routing: agent '{previous.agent}' requested '{next_agent_target}' "
                f"for action '{previous.next_action}' (expected '{expected_target}')"
            )
            self._log(
                state,
                "safety_limit",
                reason_summary=state.escalation_reason,
            )
            return None

        if next_agent_target == "none":
            return None

        if next_agent_target in {"triage", "investigation", "resolution", "critic"}:
            return next_agent_target

        state.status = "escalated"
        state.escalation_reason = (
            f"Unknown routing target: '{next_agent_target}'"
        )
        return None

    def _finish(self, context: WorkflowContext) -> dict[str, Any]:
        state = CaseState.model_validate(context["case_state"])
        trace_id = getattr(self.tracer, "trace_id", "trace-unavailable")

        if state.status == "resolved":
            response = "Your case has been resolved based on the approved resolution."
        elif state.status == "escalated":
            response = (
                f"Your case has been escalated for human review: {state.escalation_reason or 'Needs review'}. "
                "A support specialist will follow up with you."
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
        """Run one ticket through the compiled LangGraph workflow."""
        self._start_time = self.time_provider()
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