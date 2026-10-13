"""Validated customer-support tools and registry."""

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from resolveai import database

_POLICY_STORE_OVERRIDE: Any = None


def set_policy_store_override(store: Any) -> None:
    """Inject a mock or custom policy store for testing."""
    global _POLICY_STORE_OVERRIDE
    _POLICY_STORE_OVERRIDE = store


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerLookup(ToolInput):
    customer_id: str = Field(min_length=1, max_length=64)


class TicketLookup(ToolInput):
    ticket_id: str = Field(min_length=1, max_length=64)


class OrderLookup(ToolInput):
    order_id: str = Field(min_length=1, max_length=64)


class PaymentLookup(ToolInput):
    payment_id: str = Field(min_length=1, max_length=64)


class TicketSearch(ToolInput):
    customer_id: str | None = Field(default=None, max_length=64)
    status: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class AddNote(ToolInput):
    ticket_id: str = Field(min_length=1, max_length=64)
    note: str = Field(min_length=1, max_length=1000)


class ChangeTicketStatus(ToolInput):
    ticket_id: str = Field(min_length=1, max_length=64)
    status: str


class RefundRequest(ToolInput):
    payment_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=1000)
    reason: str = Field(min_length=3, max_length=500)


class EscalationRequest(ToolInput):
    ticket_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


class KnowledgeBaseSearch(ToolInput):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


def _tool_result(function: Callable[..., Any], **kwargs: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": function(**kwargs)}
    except (ValueError, ValidationError) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        # Avoid exposing database paths, SQL, or internal exception details.
        return {"ok": False, "error": "Tool execution failed"}


def lookup_customer(customer_id: str) -> dict[str, Any]:
    return _tool_result(
        database.fetch_one,
        table="customers",
        key_column="customer_id",
        key_value=customer_id,
    )


def lookup_ticket(ticket_id: str) -> dict[str, Any]:
    return _tool_result(
        database.fetch_one,
        table="tickets",
        key_column="ticket_id",
        key_value=ticket_id,
    )


def lookup_order(order_id: str) -> dict[str, Any]:
    return _tool_result(
        database.fetch_one,
        table="orders",
        key_column="order_id",
        key_value=order_id,
    )


def lookup_payment(payment_id: str) -> dict[str, Any]:
    return _tool_result(
        database.fetch_one,
        table="payments",
        key_column="payment_id",
        key_value=payment_id,
    )


def search_tickets(
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    return _tool_result(
        database.list_tickets,
        customer_id=customer_id,
        status=status,
        limit=limit,
    )


def add_internal_note(ticket_id: str, note: str) -> dict[str, Any]:
    return _tool_result(database.add_ticket_note, ticket_id=ticket_id, note=note)


def set_ticket_status(ticket_id: str, status: str) -> dict[str, Any]:
    return _tool_result(
        database.update_ticket_status, ticket_id=ticket_id, status=status
    )


def request_refund(
    payment_id: str, amount: float, reason: str
) -> dict[str, Any]:
    return _tool_result(
        database.issue_refund,
        payment_id=payment_id,
        amount=amount,
        reason=reason,
    )


def escalate_to_human(ticket_id: str, reason: str) -> dict[str, Any]:
    return _tool_result(
        database.escalate_ticket, ticket_id=ticket_id, reason=reason
    )


def initialize_demo_data() -> dict[str, Any]:
    return _tool_result(database.seed_demo_data)


def search_knowledge_base(query: str, top_k: int = 3) -> dict[str, Any]:
    """Retrieve verified policy chunks from the vector knowledge base."""
    global _POLICY_STORE_OVERRIDE

    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "error": "Query must not be empty"}

    try:
        store = _POLICY_STORE_OVERRIDE
        if store is None:
            from resolveai.config import get_settings
            from resolveai.policies import PolicyVectorStore

            settings = get_settings()
            store = PolicyVectorStore(
                chroma_dir=settings.chroma_dir,
                settings=settings,
            )

        results = store.query(
            query=query,
            top_k=top_k,
        )
        return {
            "ok": True,
            "data": [
                r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for r in results
            ],
        }
    except (ValueError, ValidationError) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"Policy retrieval unavailable: {exc}"}


TOOL_REGISTRY: dict[str, tuple[type[ToolInput], Callable[..., Any]]] = {
    "lookup_customer": (CustomerLookup, lookup_customer),
    "lookup_ticket": (TicketLookup, lookup_ticket),
    "lookup_order": (OrderLookup, lookup_order),
    "lookup_payment": (PaymentLookup, lookup_payment),
    "search_tickets": (TicketSearch, search_tickets),
    "add_internal_note": (AddNote, add_internal_note),
    "set_ticket_status": (ChangeTicketStatus, set_ticket_status),
    "request_refund": (RefundRequest, request_refund),
    "escalate_to_human": (EscalationRequest, escalate_to_human),
    "initialize_demo_data": (ToolInput, initialize_demo_data),
    "search_knowledge_base": (KnowledgeBaseSearch, search_knowledge_base),
}

AGENT_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "triage": {
        "lookup_ticket",
        "lookup_customer",
        "search_tickets",
    },
    "investigation": {
        "lookup_customer",
        "lookup_ticket",
        "lookup_order",
        "lookup_payment",
        "search_tickets",
        "search_knowledge_base",
    },
    "resolution": {
        "search_knowledge_base",
    },
    "critic": {
        "search_knowledge_base",
    },
}


def execute_tool(
    name: str,
    args: dict[str, Any],
    agent: str | None = None,
) -> dict[str, Any]:
    """Validate arguments, enforce agent allowlists, and execute a tool."""
    registered = TOOL_REGISTRY.get(name)
    if registered is None:
        return {"ok": False, "error": "Unknown tool"}

    if agent is not None:
        allowed_tools = AGENT_TOOL_ALLOWLIST.get(agent, set())
        if name not in allowed_tools:
            return {
                "ok": False,
                "error": f"Agent '{agent}' is not authorized to use tool '{name}'",
            }

    input_model, function = registered
    try:
        validated = input_model.model_validate(args)
    except ValidationError as exc:
        return {
            "ok": False,
            "error": "Invalid tool arguments",
            "details": exc.errors(include_input=False),
        }

    return function(**validated.model_dump())