"""ResolveAI HTTP API with LangGraph multi-agent orchestration."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from resolveai import database
from resolveai.config import get_settings
from resolveai.llm import ScriptedLLM
from resolveai.scenarios import ALL_SCENARIOS, run_scenario
from resolveai.schemas import Channel, ID_PATTERN, TicketIn
from resolveai.tools import execute_tool
from resolveai.tracing import TraceLogger, load_trace
from resolveai.workflow import ResolveAIWorkflow

settings = get_settings()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application: FastAPI):
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_tables(db_path: Path | str) -> None:
    """Ensure database tables including cases table are initialized."""
    database.init_db(db_path)
    with database.connect_db(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                trace_id TEXT,
                result_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            );
            """
        )


class CaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    message: str = Field(min_length=1, max_length=2000)
    subject: str = Field(default="Customer Inquiry", min_length=1, max_length=200)
    channel: Channel = "web"
    ticket_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError(
                "customer_id must contain 1-64 alphanumeric characters, hyphens or underscores"
            )
        return value

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, value: str | None) -> str | None:
        if value is not None and not ID_PATTERN.fullmatch(value):
            raise ValueError(
                "ticket_id must contain 1-64 alphanumeric characters, hyphens or underscores"
            )
        return value

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        cleaned = value.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class CaseRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mock: bool = False
    scenario: str | None = None


class ToolExecuteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1, max_length=100)
    args: dict[str, Any] = Field(default_factory=dict)
    agent: str | None = None


@app.get("/health")
def health():
    """Return application health without making an LLM request."""
    current_settings = get_settings()
    configured_providers = []

    for provider in current_settings.llm_provider_order:
        model = getattr(current_settings, f"{provider}_model", "")

        if not model.strip():
            continue

        if provider == "ollama":
            configured_providers.append(provider)
            continue

        api_key = getattr(
            current_settings, f"{provider}_api_key"
        ).get_secret_value()

        if api_key.strip():
            configured_providers.append(provider)

    return {
        "status": "ok",
        "app": current_settings.app_name,
        "version": current_settings.app_version,
        "environment": current_settings.environment,
        "providers": configured_providers,
    }


@app.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreateIn):
    """Validate customer complaint, persist ticket and case, and return case ID."""
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)

    ticket_id = payload.ticket_id or f"tkt-{uuid4().hex[:8]}"
    case_id = f"case-{ticket_id}"

    with database.connect_db(current_settings.database_path) as connection:
        # Ensure customer exists to satisfy foreign key constraint
        connection.execute(
            """
            INSERT OR IGNORE INTO customers (customer_id, name, email)
            VALUES (?, ?, ?)
            """,
            (
                payload.customer_id,
                f"Customer {payload.customer_id}",
                f"{payload.customer_id}@example.test",
            ),
        )

        # Check if ticket already exists
        existing_ticket = connection.execute(
            "SELECT ticket_id FROM tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()

        if existing_ticket is None:
            connection.execute(
                """
                INSERT INTO tickets
                    (ticket_id, customer_id, subject, message, status, channel)
                VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (
                    ticket_id,
                    payload.customer_id,
                    payload.subject,
                    payload.message,
                    payload.channel,
                ),
            )

        # Insert or update cases table
        connection.execute(
            """
            INSERT OR REPLACE INTO cases
                (case_id, ticket_id, customer_id, status, updated_at)
            VALUES (?, ?, ?, 'open', CURRENT_TIMESTAMP)
            """,
            (case_id, ticket_id, payload.customer_id),
        )

        row = connection.execute(
            "SELECT * FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

    return {
        "case_id": case_id,
        "ticket_id": ticket_id,
        "customer_id": payload.customer_id,
        "status": "open",
        "channel": payload.channel,
        "subject": payload.subject,
        "message": payload.message,
        "created_at": row["created_at"] if row else datetime.now(timezone.utc).isoformat(),
    }


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    """Return safe case details, status, and resolution result."""
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)

    with database.connect_db(current_settings.database_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM cases
            WHERE case_id = ? OR ticket_id = ?
            """,
            (case_id, case_id),
        ).fetchone()

        if row is None:
            # Check if ticket exists in tickets table
            ticket_row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?",
                (case_id,),
            ).fetchone()
            if ticket_row is not None:
                derived_case_id = f"case-{ticket_row['ticket_id']}"
                connection.execute(
                    """
                    INSERT OR IGNORE INTO cases (case_id, ticket_id, customer_id, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        derived_case_id,
                        ticket_row["ticket_id"],
                        ticket_row["customer_id"],
                        ticket_row["status"],
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM cases WHERE case_id = ?",
                    (derived_case_id,),
                ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found",
        )

    result_data = None
    if row["result_json"]:
        try:
            result_data = json.loads(row["result_json"])
        except json.JSONDecodeError:
            result_data = None

    return {
        "case_id": row["case_id"],
        "ticket_id": row["ticket_id"],
        "customer_id": row["customer_id"],
        "status": row["status"],
        "trace_id": row["trace_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "result": result_data,
    }


@app.post("/cases/{case_id}/run")
def run_case_workflow(case_id: str, payload: CaseRunIn | None = None):
    """Execute the actual LangGraph multi-agent workflow for a case."""
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)

    with database.connect_db(current_settings.database_path) as connection:
        case_row = connection.execute(
            "SELECT * FROM cases WHERE case_id = ? OR ticket_id = ?",
            (case_id, case_id),
        ).fetchone()

        if case_row is None:
            ticket_row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?",
                (case_id,),
            ).fetchone()
            if ticket_row is not None:
                derived_case_id = f"case-{ticket_row['ticket_id']}"
                connection.execute(
                    """
                    INSERT OR IGNORE INTO cases (case_id, ticket_id, customer_id, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        derived_case_id,
                        ticket_row["ticket_id"],
                        ticket_row["customer_id"],
                        ticket_row["status"],
                    ),
                )
                case_row = connection.execute(
                    "SELECT * FROM cases WHERE case_id = ?",
                    (derived_case_id,),
                ).fetchone()

    if case_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found",
        )

    # Prevent unsafe duplicate execution of write actions if already resolved
    if case_row["status"] == "resolved" and case_row["result_json"]:
        try:
            saved_result = json.loads(case_row["result_json"])
            return {
                "message": "Case already resolved. Duplicate write actions prevented.",
                "result": saved_result,
            }
        except json.JSONDecodeError:
            pass

    actual_case_id = case_row["case_id"]
    ticket_id = case_row["ticket_id"]

    ticket_record = database.fetch_one(
        "tickets", "ticket_id", ticket_id, db_path=current_settings.database_path
    )
    if not ticket_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated ticket '{ticket_id}' not found",
        )

    ticket = TicketIn(
        ticket_id=ticket_record["ticket_id"],
        customer_id=ticket_record["customer_id"],
        message=ticket_record["message"],
        channel=ticket_record["channel"],
        timestamp=ticket_record["created_at"],
        metadata={"subject": ticket_record["subject"]},
    )

    mock_mode = payload.mock if payload else False
    scenario_choice = payload.scenario if payload else None

    tracer = TraceLogger(trace_dir=current_settings.trace_dir)

    try:
        if scenario_choice:
            if scenario_choice not in ALL_SCENARIOS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown scenario '{scenario_choice}'. Choose from: {list(ALL_SCENARIOS.keys())}",
                )
            demo_sc = ALL_SCENARIOS[scenario_choice]
            workflow = ResolveAIWorkflow(
                settings=current_settings,
                llm=ScriptedLLM(demo_sc.scripted_responses),
                tracer=tracer,
            )
        elif mock_mode:
            # Deterministic mock based on matching scenario or safe fallback
            matched_responses = None
            for s_obj in ALL_SCENARIOS.values():
                if (
                    s_obj.ticket.ticket_id == ticket.ticket_id
                    or s_obj.ticket.message.strip() == ticket.message.strip()
                ):
                    matched_responses = s_obj.scripted_responses
                    break

            if matched_responses:
                workflow = ResolveAIWorkflow(
                    settings=current_settings,
                    llm=ScriptedLLM(matched_responses),
                    tracer=tracer,
                )
            else:
                default_script = [
                    json.dumps({
                        "agent": "triage",
                        "next_action": "human_escalation",
                        "next_agent": "none",
                        "reason": "Escalated to human supervisor for review (mock mode).",
                        "confidence": 0.95,
                        "risk": "medium",
                    })
                ]
                workflow = ResolveAIWorkflow(
                    settings=current_settings,
                    llm=ScriptedLLM(default_script),
                    tracer=tracer,
                )
        else:
            workflow = ResolveAIWorkflow(
                settings=current_settings,
                tracer=tracer,
            )

        result = workflow.run(ticket)

    except HTTPException:
        raise
    except Exception as exc:
        # Return structured error without exposing secrets or raw stack trace
        with database.connect_db(current_settings.database_path) as connection:
            connection.execute(
                """
                UPDATE cases
                SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE case_id = ?
                """,
                (actual_case_id,),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {type(exc).__name__}",
        )

    # Action Gate: execute authorized write action if resolved with refund
    if result.status == "resolved" and result.resolution and result.resolution.type == "refund":
        payment_id = result.resolution.details.get("payment_id") if result.resolution.details else None
        if not payment_id and result.resolution.action_id:
            payment_id = result.resolution.action_id
        if payment_id and result.resolution.amount is not None:
            try:
                database.issue_refund(
                    payment_id=payment_id,
                    amount=float(result.resolution.amount),
                    reason=f"Approved refund for case {actual_case_id}",
                    max_refund_amount=current_settings.max_refund_amount,
                    db_path=current_settings.database_path,
                )
            except Exception:
                pass  # Ignore if payment is already refunded

    # Update ticket status in database
    try:
        database.update_ticket_status(
            ticket_id=ticket.ticket_id,
            status=result.status,
            db_path=current_settings.database_path,
        )
    except Exception:
        pass

    if result.status == "escalated" and result.escalation_reason:
        try:
            database.escalate_ticket(
                ticket_id=ticket.ticket_id,
                reason=result.escalation_reason,
                db_path=current_settings.database_path,
            )
        except Exception:
            pass

    # Persist case result to database
    with database.connect_db(current_settings.database_path) as connection:
        connection.execute(
            """
            UPDATE cases
            SET status = ?, trace_id = ?, result_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE case_id = ?
            """,
            (
                result.status,
                result.trace_id,
                result.model_dump_json(),
                actual_case_id,
            ),
        )

    return {
        "case_id": actual_case_id,
        "status": result.status,
        "result": result.model_dump(mode="json"),
    }


@app.get("/cases/{case_id}/trace")
def get_case_trace(case_id: str):
    """Return trace events for a given case."""
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)

    with database.connect_db(current_settings.database_path) as connection:
        row = connection.execute(
            "SELECT * FROM cases WHERE case_id = ? OR ticket_id = ?",
            (case_id, case_id),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found",
        )

    trace_id = row["trace_id"]
    if not trace_id:
        return {
            "case_id": row["case_id"],
            "trace_id": None,
            "events": [],
            "event_count": 0,
        }

    trace_file = Path(current_settings.trace_dir) / f"{trace_id}.jsonl"
    if not trace_file.exists():
        return {
            "case_id": row["case_id"],
            "trace_id": trace_id,
            "events": [],
            "event_count": 0,
        }

    try:
        events = load_trace(trace_file)
        return {
            "case_id": row["case_id"],
            "trace_id": trace_id,
            "events": [event.model_dump(mode="json") for event in events],
            "event_count": len(events),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading trace: {type(exc).__name__}",
        )


@app.get("/scenarios")
def list_scenarios():
    """List available predefined demo scenarios."""
    return [
        {
            "id": key,
            "name": sc.name,
            "description": sc.description,
            "expected_status": sc.expected_status,
        }
        for key, sc in ALL_SCENARIOS.items()
    ]


@app.post("/scenarios/{scenario_name}/run")
def run_scenario_endpoint(scenario_name: str):
    """Execute a predefined demo scenario through the multi-agent workflow."""
    current_settings = get_settings()
    _ensure_tables(current_settings.database_path)

    if scenario_name not in ALL_SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_name}' not found. Available: {list(ALL_SCENARIOS.keys())}",
        )

    scenario = ALL_SCENARIOS[scenario_name]
    result, trace_path = run_scenario(scenario, trace_dir=current_settings.trace_dir)

    # Save to database
    case_id = result.case_id
    ticket = scenario.ticket

    with database.connect_db(current_settings.database_path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO customers (customer_id, name, email)
            VALUES (?, ?, ?)
            """,
            (
                ticket.customer_id,
                f"Customer {ticket.customer_id}",
                f"{ticket.customer_id}@example.test",
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO tickets
                (ticket_id, customer_id, subject, message, status, channel)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.ticket_id,
                ticket.customer_id,
                "Demo Scenario",
                ticket.message,
                result.status,
                ticket.channel,
            ),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO cases
                (case_id, ticket_id, customer_id, status, trace_id, result_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                case_id,
                ticket.ticket_id,
                ticket.customer_id,
                result.status,
                result.trace_id,
                result.model_dump_json(),
            ),
        )

    return {
        "scenario": scenario_name,
        "case_id": case_id,
        "status": result.status,
        "result": result.model_dump(mode="json"),
        "trace_path": trace_path,
    }


@app.post("/tools/execute")
def execute_tool_endpoint(payload: ToolExecuteIn):
    """Execute an authorized tool through the tool permission gateway."""
    result = execute_tool(
        name=payload.tool,
        args=payload.args,
        agent=payload.agent,
    )
    if not result.get("ok", False):
        error_msg = result.get("error", "Tool execution failed")
        if "not authorized" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg,
            )
        return {"ok": False, "error": error_msg, "details": result.get("details")}

    return {"ok": True, "data": result.get("data")}