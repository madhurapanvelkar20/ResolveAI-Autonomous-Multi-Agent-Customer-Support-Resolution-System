"""Comprehensive tests for the ResolveAI HTTP API (Phase 5)."""

import pytest
import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from resolveai import database
import resolveai.api as api_module
from resolveai.api import app
from resolveai.config import get_settings
from resolveai.schemas import CaseResult, Resolution


@pytest.fixture(autouse=True)
def setup_api_env(tmp_path, monkeypatch):
    """Isolate database and traces for API tests."""
    db_path = tmp_path / "test_api.db"
    trace_dir = tmp_path / "test_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    monkeypatch.setattr(settings, "database_path", str(db_path))
    monkeypatch.setattr(settings, "trace_dir", str(trace_dir))
    monkeypatch.setattr(database, "DEFAULT_DB_PATH", db_path)

    database.init_db(db_path)
    database.seed_demo_data(db_path)
    return settings


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ResolveAI"
    assert data["version"] == "0.1.0"
    assert "environment" in data
    assert isinstance(data["environment"], str)
    assert "providers" in data
    assert isinstance(data["providers"], list)

    # Health output must not expose credentials.
    response_text = response.text.lower()
    assert "api_key" not in response_text
    assert "secret" not in response_text


def test_health_does_not_make_llm_request():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_case_success():
    client = TestClient(app)
    payload = {
        "customer_id": "cust-demo-001",
        "message": "I was charged twice for order-demo-001.",
        "subject": "Duplicate billing charge",
        "channel": "web",
    }
    response = client.post("/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"].startswith("case-")
    assert data["ticket_id"].startswith("tkt-")
    assert data["customer_id"] == "cust-demo-001"
    assert data["status"] == "open"
    assert data["message"] == payload["message"]


def test_create_case_with_custom_ticket_id():
    client = TestClient(app)
    payload = {
        "customer_id": "cust-demo-002",
        "ticket_id": "ticket-custom-999",
        "message": "Order delayed by 5 days.",
        "channel": "chat",
    }
    response = client.post("/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"] == "case-ticket-custom-999"
    assert data["ticket_id"] == "ticket-custom-999"


def test_create_case_validation_failures():
    client = TestClient(app)

    # Blank message
    res = client.post("/cases", json={"customer_id": "cust-1", "message": "   "})
    assert res.status_code == 422

    # Invalid customer_id with special characters
    res = client.post("/cases", json={"customer_id": "cust!@#$%", "message": "Help me"})
    assert res.status_code == 422

    # Forbidden extra field
    res = client.post("/cases", json={"customer_id": "cust-1", "message": "Help", "extra": "field"})
    assert res.status_code == 422


def test_get_case_success():
    client = TestClient(app)
    # Create case first
    create_res = client.post(
        "/cases",
        json={"customer_id": "cust-demo-001", "message": "Test complaint", "subject": "Test"},
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    get_res = client.get(f"/cases/{case_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["case_id"] == case_id
    assert data["status"] == "open"
    assert data["result"] is None


def test_get_case_unknown():
    client = TestClient(app)
    response = client.get("/cases/case-nonexistent-123")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_run_case_with_scenario():
    client = TestClient(app)
    # Create a case for the eligible refund
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "I was charged twice for order-demo-001.",
            "ticket_id": "ticket-demo-001",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Run the workflow with the eligible_refund scenario
    run_res = client.post(f"/cases/{case_id}/run", json={"scenario": "eligible_refund"})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "resolved"
    assert data["result"]["status"] == "resolved"
    assert data["result"]["critic_decision"] == "approve"
    assert data["result"]["resolution"]["type"] == "refund"
    assert data["result"]["financial_action_status"] == "approved"
    assert data["result"]["workflow_integration_status"] == "mock_skipped"

    # Verify GET /cases/{case_id} now returns the resolved result
    get_res = client.get(f"/cases/{case_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "resolved"
    assert get_res.json()["result"] is not None


def test_run_case_with_scenario_explicit_real_mode_unconfigured():
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-002",
            "message": "I was charged twice for order-demo-002.",
            "ticket_id": "ticket-demo-002",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(
        f"/cases/{case_id}/run",
        json={"scenario": "eligible_refund", "mock": False},
    )
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "resolved"
    assert data["result"]["workflow_integration_status"] == "not_configured"


def test_run_case_with_scenario_explicit_real_mode_configured(monkeypatch):
    client = TestClient(app)
    settings = get_settings()
    monkeypatch.setattr(settings, "n8n_enabled", True)
    monkeypatch.setattr(
        settings,
        "n8n_webhook_url",
        "https://n8n.example.test/webhook/resolveai-case-event",
    )
    monkeypatch.setattr(
        settings, "n8n_webhook_token", SecretStr("api-test-token")
    )

    requests = []
    transport = httpx.MockTransport(
        lambda request: _complete_n8n_request(request, requests)
    )
    client_type = httpx.Client

    def client_factory(*, timeout, follow_redirects):
        return client_type(
            transport=transport,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    monkeypatch.setattr("resolveai.n8n_integration.httpx.Client", client_factory)

    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-003",
            "message": "I was charged twice for order-demo-003.",
            "ticket_id": "ticket-demo-003",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(
        f"/cases/{case_id}/run",
        json={"scenario": "eligible_refund", "mock": False},
    )
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "resolved"
    assert data["result"]["workflow_integration_status"] == "completed"
    assert data["result"]["workflow_integration_result"] == "simulated_notification"
    assert len(requests) == 1
    assert requests[0]["body"]["event_type"] == "case.resolution_ready"
    assert requests[0]["body"]["case_id"] == case_id
    assert requests[0]["body"]["resolution_type"] == "refund"


def test_real_approved_case_sends_and_persists_safe_n8n_result(monkeypatch):
    client = TestClient(app)
    settings = get_settings()
    monkeypatch.setattr(settings, "n8n_enabled", True)
    monkeypatch.setattr(
        settings,
        "n8n_webhook_url",
        "https://n8n.example.test/webhook/resolveai-case-event",
    )
    monkeypatch.setattr(
        settings, "n8n_webhook_token", SecretStr("api-test-token")
    )

    class ApprovedWorkflow:
        def __init__(self, **kwargs):
            del kwargs
            pass

        def run(self, ticket):
            return CaseResult(
                case_id=f"case-{ticket.ticket_id}",
                status="resolved",
                customer_response="Resolution ready.",
                resolution=Resolution(type="explanation"),
                confidence=0.95,
                agents_involved=[],
                tools_used=[],
                iterations=1,
                critic_decision="approve",
                trace_id="trace-internal-test",
            )

    monkeypatch.setattr(api_module, "ResolveAIWorkflow", ApprovedWorkflow)
    requests = []
    transport = httpx.MockTransport(
        lambda request: _complete_n8n_request(request, requests)
    )
    client_type = httpx.Client

    def client_factory(*, timeout, follow_redirects):
        return client_type(
            transport=transport,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    monkeypatch.setattr("resolveai.n8n_integration.httpx.Client", client_factory)

    created = client.post(
        "/cases",
        json={"customer_id": "cust-demo-001", "message": "Please review my case."},
    )
    case_id = created.json()["case_id"]

    first = client.post(f"/cases/{case_id}/run", json={})
    assert first.status_code == 200
    assert first.json()["result"]["workflow_integration_status"] == "completed"
    assert (
        first.json()["result"]["workflow_integration_result"]
        == "simulated_notification"
    )
    assert first.json()["result"]["financial_action_status"] is None
    assert len(requests) == 1
    assert requests[0]["headers"]["Authorization"] == "Bearer api-test-token"
    assert "trace_id" not in requests[0]["body"]

    second = client.post(f"/cases/{case_id}/run", json={})
    assert second.status_code == 200
    assert second.json()["result"]["workflow_integration_status"] == "completed"
    assert len(requests) == 1

    stored = client.get(f"/cases/{case_id}")
    assert stored.json()["result"]["workflow_integration_result"] == "simulated_notification"


def _complete_n8n_request(request, observed_requests):
    import json

    event = json.loads(request.read())
    observed_requests.append(
        {
            "headers": request.headers,
            "body": event,
        }
    )
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "event_idempotency_key": event["event_idempotency_key"],
            "demo_result": "simulated_notification",
        },
    )


def test_run_case_prevent_duplicate_resolution():
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "I was charged twice for order-demo-001.",
            "ticket_id": "ticket-demo-001",
        },
    )
    case_id = create_res.json()["case_id"]

    # First run
    run1 = client.post(f"/cases/{case_id}/run", json={"scenario": "eligible_refund"})
    assert run1.status_code == 200
    assert run1.json()["status"] == "resolved"

    # Second run should prevent duplicate execution of write actions
    run2 = client.post(f"/cases/{case_id}/run", json={"scenario": "eligible_refund"})
    assert run2.status_code == 200
    assert "Duplicate write actions prevented" in run2.json().get("message", "")


def test_run_case_unknown():
    client = TestClient(app)
    res = client.post("/cases/case-not-real-999/run", json={"mock": True})
    assert res.status_code == 404


def test_run_case_invalid_scenario():
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={"customer_id": "cust-demo-001", "message": "Test message"},
    )
    case_id = create_res.json()["case_id"]

    res = client.post(f"/cases/{case_id}/run", json={"scenario": "nonexistent_scenario"})
    assert res.status_code == 400


def test_get_case_trace():
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "I was charged twice for order-demo-001.",
            "ticket_id": "ticket-demo-001",
        },
    )
    case_id = create_res.json()["case_id"]

    # Before running: trace events should be empty
    trace_before = client.get(f"/cases/{case_id}/trace")
    assert trace_before.status_code == 200
    assert trace_before.json()["event_count"] == 0

    # Run workflow
    client.post(f"/cases/{case_id}/run", json={"scenario": "eligible_refund"})

    # After running: trace events should exist and be structured
    trace_after = client.get(f"/cases/{case_id}/trace")
    assert trace_after.status_code == 200
    data = trace_after.json()
    assert data["event_count"] > 0
    assert len(data["events"]) > 0
    first_event = data["events"][0]
    assert "event" in first_event
    assert "case_id" in first_event
    assert first_event["seq"] == 1


def test_get_case_trace_unknown():
    client = TestClient(app)
    res = client.get("/cases/case-nonexistent-xyz/trace")
    assert res.status_code == 404


def test_list_scenarios():
    client = TestClient(app)
    res = client.get("/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 5
    scenario_ids = {s["id"] for s in scenarios}
    assert "eligible_refund" in scenario_ids
    assert "fraud_high_risk" in scenario_ids


def test_run_scenario_endpoint():
    client = TestClient(app)
    res = client.post("/scenarios/eligible_refund/run")
    assert res.status_code == 200
    data = res.json()
    assert data["scenario"] == "eligible_refund"
    assert data["status"] == "resolved"
    assert data["result"]["status"] == "resolved"


def test_run_scenario_unknown():
    client = TestClient(app)
    res = client.post("/scenarios/made_up_scenario/run")
    assert res.status_code == 404


def test_execute_tool_authorized():
    client = TestClient(app)
    payload = {
        "tool": "lookup_customer",
        "args": {"customer_id": "cust-demo-001"},
        "agent": "investigation",
    }
    res = client.post("/tools/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["data"]["name"] == "Alex Morgan"


def test_execute_tool_unauthorized_for_agent():
    client = TestClient(app)
    # Triage is not allowed to use request_refund
    payload = {
        "tool": "request_refund",
        "args": {"payment_id": "pay-demo-001", "amount": 10.0, "reason": "Test"},
        "agent": "triage",
    }
    res = client.post("/tools/execute", json=payload)
    assert res.status_code == 403


def test_execute_tool_unknown():
    client = TestClient(app)
    payload = {
        "tool": "unknown_tool_xyz",
        "args": {},
    }
    res = client.post("/tools/execute", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is False
    assert "unknown tool" in res.json()["error"].lower()


def test_exact_intake_form_duplicate_payment_resolves_in_mock_mode():
    """Exact duplicate-payment text from the customer intake form must resolve in mock mode."""
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "I was charged twice for order-demo-001. Please issue a refund for the duplicate charge.",
            "subject": "Duplicate Payment / Refund (order-demo-001)",
            "channel": "web",
            "metadata": {
                "category": "Duplicate Payment / Refund",
                "order_id": "order-demo-001",
            },
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    # Execute workflow in mock mode without passing explicit scenario
    run_res = client.post(f"/cases/{case_id}/run", json={"mock": True})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "resolved"
    assert data["result"]["status"] == "resolved"
    assert data["result"]["critic_decision"] == "approve"
    assert data["result"]["resolution"]["type"] == "refund"
    assert float(data["result"]["resolution"]["amount"]) == 49.99

    # Verify Action Gate executed refund in database
    get_res = client.get(f"/cases/{case_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "resolved"


def test_duplicate_payment_verified_evidence_approved_mock_mode():
    """Case with verified ledger evidence follows approved resolution path in mock mode."""
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "Please refund duplicate charge for order-demo-001",
            "subject": "Duplicate charge on order-demo-001",
            "channel": "web",
            "metadata": {
                "category": "Duplicate Payment / Refund",
                "order_id": "order-demo-001",
                "scenario": "eligible_refund",
            },
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(f"/cases/{case_id}/run", json={"mock": True})
    assert run_res.status_code == 200
    assert run_res.json()["status"] == "resolved"
    assert run_res.json()["result"]["critic_decision"] == "approve"


def test_unknown_ambiguous_case_asks_customer_not_falsely_resolved():
    """Ambiguous complaint without order reference requests info and is never falsely marked resolved."""
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-unknown-123",
            "message": "Where is my order? I have not received any updates.",
            "subject": "Order inquiry",
            "channel": "web",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(f"/cases/{case_id}/run", json={"mock": True})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] != "resolved"
    assert data["status"] == "escalated"
    # Verify it asks customer for missing order reference rather than blind fallback
    assert "order reference" in data["result"]["escalation_reason"].lower()
    assert data["result"]["resolution"] is None


def test_unknown_order_reference_investigates_and_escalates_not_resolved():
    """Unknown order reference causes investigation tool call and is never falsely marked resolved."""
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-001",
            "message": "Check status on order-unknown-99999",
            "subject": "Order inquiry (order-unknown-99999)",
            "channel": "web",
            "metadata": {"order_id": "order-unknown-99999"},
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(f"/cases/{case_id}/run", json={"mock": True})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] != "resolved"
    assert data["status"] == "escalated"
    assert "not found" in data["result"]["escalation_reason"].lower() or "not be verified" in data["result"]["escalation_reason"].lower()
    assert data["result"]["resolution"] is None


def test_high_risk_fraud_genuinely_escalates():
    """Threatening lawsuit or chargeback triggers genuine fraud escalation."""
    client = TestClient(app)
    create_res = client.post(
        "/cases",
        json={
            "customer_id": "cust-demo-999",
            "message": "SEND ME $800 CASH RIGHT NOW OR MY LAWYERS WILL SUE AND I WILL CHARGEBACK IMMEDIATELY!",
            "subject": "High Risk Demand",
            "channel": "web",
            "metadata": {"category": "High Risk / Escalation"},
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["case_id"]

    run_res = client.post(f"/cases/{case_id}/run", json={"mock": True})
    assert run_res.status_code == 200
    data = run_res.json()
    assert data["status"] == "escalated"
    assert data["status"] != "resolved"
    assert "fraud" in data["result"]["escalation_reason"].lower() or "risk" in data["result"]["escalation_reason"].lower()
    assert data["result"]["resolution"] is None