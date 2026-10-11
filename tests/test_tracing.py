
import json

import pytest

from resolveai.tracing import TraceLogger, load_trace, render_text


def test_trace_round_trip(tmp_path):
    logger = TraceLogger(tmp_path, trace_id="trace-test")

    logger.log(
        case_id="case-001",
        iteration=0,
        event="case_start",
        message="Case received",
    )
    logger.log(
        case_id="case-001",
        iteration=1,
        event="agent_decision",
        agent="triage",
        decision="request_investigation",
        reason_summary="Payment outcome needs investigation.",
        confidence=0.8,
    )

    events = load_trace(logger.path)

    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].seq == 2
    assert events[1].agent == "triage"
    assert events[1].confidence == 0.8


def test_trace_summary_is_trimmed(tmp_path):
    logger = TraceLogger(tmp_path)

    logger.log(
        case_id="case-001",
        iteration=0,
        event="tool_result",
        tool="get_payment",
        tool_result_summary="x" * 500,
    )

    event = load_trace(logger.path)[0]
    assert len(event.tool_result_summary) == 300


def test_unknown_event_is_rejected(tmp_path):
    logger = TraceLogger(tmp_path)

    with pytest.raises(ValueError):
        logger.log(
            case_id="case-001",
            iteration=0,
            event="invented_event",
        )


def test_trace_file_contains_valid_jsonl(tmp_path):
    logger = TraceLogger(tmp_path)
    logger.log(
        case_id="case-001",
        iteration=0,
        event="case_start",
    )

    lines = logger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "case_start"


def test_render_text():
    logger_event = {
        "trace_id": "t1",
        "seq": 1,
        "ts": "2026-10-11T10:00:00Z",
        "case_id": "case-001",
        "iteration": 0,
        "event": "case_start",
        "message": "Case received",
    }

    from resolveai.tracing import TraceEvent

    text = render_text([TraceEvent.model_validate(logger_event)])
    assert "case_start" in text
    assert "case-001" in text
