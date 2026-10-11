
"""Shared Pydantic contracts for ResolveAI."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AgentName = Literal["triage", "investigation", "resolution", "critic"]
NextAgent = Literal["triage", "investigation", "resolution", "critic", "none"]
RiskLevel = Literal["low", "medium", "high"]
Channel = Literal["web", "email", "chat"]

ActionName = Literal[
    "call_tool", "request_investigation", "ask_customer",
    "human_escalation", "report_findings", "request_replan",
    "propose", "request_evidence", "approve", "reject",
]

MessageType = Literal[
    "request_investigation", "evidence_report", "proposal", "critique",
    "revision_request", "replan", "escalation", "clarification_request",
]

EvidenceStatus = Literal[
    "supports", "contradicts", "missing", "tool_failure", "policy"
]
CaseStatus = Literal["open", "resolved", "escalated", "failed"]
CriticDecision = Literal["approve", "reject", "request_evidence"]

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

ACTION_AGENTS = {
    "call_tool": "same",
    "request_investigation": "investigation",
    "ask_customer": "none",
    "human_escalation": "none",
    "report_findings": "resolution",
    "request_replan": "triage",
    "propose": "critic",
    "request_evidence": "investigation",
    "approve": "none",
    "reject": "resolution",
}

AGENT_ACTIONS = {
    "triage": {
        "call_tool", "request_investigation",
        "ask_customer", "human_escalation",
    },
    "investigation": {
        "call_tool", "report_findings",
        "request_replan", "human_escalation",
    },
    "resolution": {
        "call_tool", "propose", "request_evidence",
        "human_escalation",
    },
    "critic": {
        "call_tool", "approve", "reject",
        "request_evidence", "human_escalation",
    },
}


class ContractModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class TicketIn(ContractModel):
    ticket_id: str
    customer_id: str
    message: str = Field(min_length=1, max_length=2000)
    channel: Channel
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ticket_id", "customer_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError(
                "Identifier must contain 1-64 letters, digits, '_' or '-'"
            )
        return value

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Message must be a string")
        value = value.replace("\x00", "").strip()
        if not value:
            raise ValueError("Message cannot be blank")
        if len(value) > 2000:
            raise ValueError("Message cannot exceed 2000 characters")
        return value


class ToolCall(ContractModel):
    name: str = Field(min_length=1, max_length=100)
    args: dict[str, Any] = Field(default_factory=dict)


class AgentDecision(ContractModel):
    agent: AgentName
    next_action: ActionName
    next_agent: NextAgent
    tool_call: ToolCall | None = None
    reason: str = Field(min_length=3, max_length=500)
    confidence: float = Field(ge=0, le=1)
    risk: RiskLevel | None = None
    state_updates: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_contract(self):
        action = self.next_action

        if action not in AGENT_ACTIONS[self.agent]:
            raise ValueError(
                f"Agent '{self.agent}' cannot perform action '{action}'"
            )

        if action == "call_tool" and self.tool_call is None:
            raise ValueError("call_tool requires tool_call")

        if action != "call_tool" and self.tool_call is not None:
            raise ValueError("tool_call is only allowed with call_tool")

        expected = ACTION_AGENTS[action]
        if expected == "same":
            expected = self.agent

        if self.next_agent != expected:
            raise ValueError(
                f"Action '{action}' must target '{expected}', "
                f"not '{self.next_agent}'"
            )

        if action == "human_escalation" and self.risk is None:
            raise ValueError("human_escalation requires risk")

        return self


class CriticFeedback(ContractModel):
    decision: CriticDecision
    reason: str = Field(min_length=3, max_length=500)
    missing_evidence: list[str] = Field(default_factory=list)
    policy_citations: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_non_approval_feedback(self):
        if (
            self.decision != "approve"
            and not self.missing_evidence
            and not self.recommended_next_action
        ):
            raise ValueError(
                "Non-approve feedback requires missing_evidence "
                "or recommended_next_action"
            )
        return self


class CaseMessage(ContractModel):
    sender: AgentName
    recipient: NextAgent
    message_type: MessageType
    content: str = Field(min_length=1, max_length=2000)
    iteration: int = Field(ge=0)


class Evidence(ContractModel):
    source: str = Field(min_length=1, max_length=200)
    status: EvidenceStatus
    summary: str = Field(min_length=1, max_length=1000)
    details: dict[str, Any] = Field(default_factory=dict)
    citation: str | None = None


class Resolution(ContractModel):
    type: str = Field(min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    action_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CaseState(ContractModel):
    case_id: str = Field(min_length=1, max_length=64)
    ticket: TicketIn
    status: CaseStatus = "open"
    current_hypothesis: str | None = None
    plan: list[str] = Field(default_factory=list)
    messages: list[CaseMessage] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    agent_decisions: list[AgentDecision] = Field(default_factory=list)
    critic_feedback: list[CriticFeedback] = Field(default_factory=list)
    resolution_candidates: list[Resolution] = Field(default_factory=list)
    selected_resolution: Resolution | None = None
    iteration: int = Field(default=0, ge=0)
    confidence: float = Field(default=0, ge=0, le=1)
    escalation_reason: str | None = None


class CaseResult(ContractModel):
    case_id: str
    status: Literal["resolved", "escalated", "failed"]
    customer_response: str = Field(min_length=1)
    resolution: Resolution | None = None
    confidence: float = Field(ge=0, le=1)
    agents_involved: list[AgentName]
    tools_used: list[str]
    iterations: int = Field(ge=0)
    critic_decision: CriticDecision | None = None
    escalation_reason: str | None = None
    trace_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result_invariants(self):
        if self.status == "resolved":
            if self.resolution is None:
                raise ValueError("Resolved cases require a resolution")
            if self.critic_decision != "approve":
                raise ValueError("Resolved cases require Critic approval")

        if self.status == "escalated" and not self.escalation_reason:
            raise ValueError("Escalated cases require escalation_reason")

        return self
