
"""Thread-safe JSONL tracing for real runtime events."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


TRACE_EVENTS = {
    "case_start", "agent_decision", "llm_call", "validation_error",
    "llm_failure", "tool_call", "tool_result", "tool_failure",
    "message", "state_update", "safety_limit", "escalation", "final",
}


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    seq: int = Field(ge=1)
    ts: datetime
    case_id: str
    iteration: int = Field(ge=0)
    agent: str | None = None
    event: str
    input_refs: list[str] = Field(default_factory=list)
    tool: str | None = None
    tool_result_summary: str | None = None
    decision: str | None = None
    reason_summary: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    message: str | None = None
    state_update: dict[str, Any] | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    model: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def trim_summary(self) -> "TraceEvent":
        if self.tool_result_summary is not None:
            self.tool_result_summary = self.tool_result_summary[:300]
        return self


class TraceLogger:
    """Append actual runtime events to a JSON Lines trace file."""

    def __init__(
        self,
        trace_dir: str | Path = "traces",
        trace_id: str | None = None,
    ):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.trace_id = trace_id or str(uuid4())
        self.path = self.trace_dir / f"{self.trace_id}.jsonl"
        self._lock = threading.Lock()
        self._seq = self._last_sequence()

    def _last_sequence(self) -> int:
        if not self.path.exists():
            return 0

        last = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    last = max(last, int(record["seq"]))
        return last

    def log(
        self,
        *,
        case_id: str,
        iteration: int,
        event: str,
        agent: str | None = None,
        input_refs: list[str] | None = None,
        tool: str | None = None,
        tool_result_summary: str | None = None,
        decision: str | None = None,
        reason_summary: str | None = None,
        confidence: float | None = None,
        message: str | None = None,
        state_update: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TraceEvent:
        if event not in TRACE_EVENTS:
            raise ValueError(f"Unknown trace event: {event}")

        with self._lock:
            self._seq += 1
            record = TraceEvent(
                trace_id=self.trace_id,
                seq=self._seq,
                ts=datetime.now(timezone.utc),
                case_id=case_id,
                iteration=iteration,
                agent=agent,
                event=event,
                input_refs=input_refs or [],
                tool=tool,
                tool_result_summary=tool_result_summary,
                decision=decision,
                reason_summary=reason_summary,
                confidence=confidence,
                message=message,
                state_update=state_update,
                latency_ms=latency_ms,
                model=model,
                extra=extra or {},
            ).trim_summary()

            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(
                    record.model_dump_json() + "\n"
                )

            return record


def load_trace(path: str | Path) -> list[TraceEvent]:
    """Load and validate events from a JSONL trace."""
    events = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(TraceEvent.model_validate_json(line))
    return events


def render_text(events: list[TraceEvent]) -> str:
    """Render concise, human-readable trace summaries."""
    lines = []
    for event in events:
        actor = event.agent or "runtime"
        reason = event.reason_summary or event.message or ""
        lines.append(
            f"[{event.seq}] {event.event} | {actor} | "
            f"case={event.case_id} | iteration={event.iteration}"
            + (f" | {reason}" if reason else "")
        )
    return "\n".join(lines)
