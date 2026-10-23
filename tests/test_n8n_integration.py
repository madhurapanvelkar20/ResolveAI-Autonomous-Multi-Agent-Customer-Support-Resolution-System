"""Safe n8n resolution-event delivery tests using mocked HTTP transport."""

import httpx
import pytest
from pydantic import SecretStr

from resolveai.config import Settings
from resolveai.n8n_integration import dispatch_resolution_event
from resolveai.schemas import CaseResult, Resolution


def _settings(
    *,
    enabled: bool = True,
    url: str = "https://n8n.example.test/webhook/resolveai-case-event",
    token: str = "unit-test-token",
) -> Settings:
    return Settings(
        _env_file=None,
        n8n_enabled=enabled,
        n8n_webhook_url=url,
        n8n_webhook_token=SecretStr(token),
    )


def _approved_result(
    *,
    resolution_type: str = "explanation",
    status: str = "resolved",
    critic_decision: str = "approve",
) -> CaseResult:
    return CaseResult(
        case_id="case-test-1",
        status=status,
        customer_response="Resolution ready.",
        resolution=Resolution(type=resolution_type),
        confidence=0.95,
        agents_involved=[],
        tools_used=[],
        iterations=1,
        critic_decision=critic_decision,
        escalation_reason="Needs a support specialist." if status == "escalated" else None,
        trace_id="trace-test-internal",
    )


def _install_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    client_type = httpx.Client

    def client_factory(*, timeout, follow_redirects):
        return client_type(
            transport=transport,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    monkeypatch.setattr("resolveai.n8n_integration.httpx.Client", client_factory)


def _unexpected_http_client(**kwargs):
    del kwargs
    pytest.fail("This path must not create an HTTP client")


def test_mock_mode_does_not_make_external_http_call(monkeypatch):
    monkeypatch.setattr(
        "resolveai.n8n_integration.httpx.Client", _unexpected_http_client
    )

    status = dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=True,
    )

    assert status == "mock_skipped"


def test_approved_result_sends_minimal_authenticated_idempotent_event(monkeypatch):
    observed = {}

    def handler(request):
        observed["headers"] = request.headers
        observed["body"] = request.read()
        event_key = request.headers["Idempotency-Key"]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "event_idempotency_key": event_key,
                "demo_result": "simulated_notification",
            },
        )

    _install_transport(monkeypatch, handler)

    status = dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(resolution_type="refund"),
        mock_mode=False,
    )

    assert status == "completed"
    assert observed["headers"]["Authorization"] == "Bearer unit-test-token"
    assert observed["headers"]["Idempotency-Key"] == "resolveai-case-case-test-1"
    assert httpx.URL("https://n8n.example.test").host in observed["headers"]["host"]
    assert observed["body"] == (
        b'{"event_type":"case.resolution_ready",'
        b'"event_idempotency_key":"resolveai-case-case-test-1",'
        b'"case_id":"case-test-1","resolution_type":"refund"}'
    )
    assert b"payment_id" not in observed["body"]
    assert b"trace" not in observed["body"]
    assert b"amount" not in observed["body"]


@pytest.mark.parametrize(
    "result",
    [
        _approved_result(status="escalated", critic_decision="request_evidence"),
        _approved_result(critic_decision="approve", resolution_type="unknown-action"),
    ],
)
def test_ineligible_or_unsupported_results_are_blocked(result, monkeypatch):
    monkeypatch.setattr(
        "resolveai.n8n_integration.httpx.Client", _unexpected_http_client
    )

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        result,
        mock_mode=False,
    ) == "ineligible"


def test_disabled_integration_reports_not_configured_without_http(monkeypatch):
    monkeypatch.setattr(
        "resolveai.n8n_integration.httpx.Client", _unexpected_http_client
    )

    assert dispatch_resolution_event(
        _settings(enabled=False),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "not_configured"


@pytest.mark.parametrize(
    "settings",
    [
        _settings(url="", token=""),
        _settings(url="http://public.example.test/webhook/resolveai-case-event"),
    ],
)
def test_missing_or_unsafe_configuration_fails_before_network(settings, monkeypatch):
    monkeypatch.setattr(
        "resolveai.n8n_integration.httpx.Client", _unexpected_http_client
    )

    assert dispatch_resolution_event(
        settings,
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "failed"


def test_accepted_response_is_not_reported_as_completed(monkeypatch):
    def handler(request):
        assert request.method == "POST"
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "event_idempotency_key": "resolveai-case-case-test-1",
            },
        )

    _install_transport(monkeypatch, handler)

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "accepted"


@pytest.mark.parametrize(
    "response",
    [
        {"status": "completed"},
        {
            "status": "completed",
            "event_idempotency_key": "resolveai-case-other",
            "demo_result": "simulated_notification",
        },
        {
            "status": "completed",
            "event_idempotency_key": "resolveai-case-case-test-1",
            "demo_result": "execute arbitrary command",
        },
    ],
)
def test_invalid_webhook_responses_are_failed(response, monkeypatch):
    def handler(request):
        assert request.method == "POST"
        return httpx.Response(200, json=response)

    _install_transport(
        monkeypatch,
        handler,
    )

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "failed"


def test_http_error_is_reported_as_failed(monkeypatch):
    def handler(request):
        assert request.method == "POST"
        return httpx.Response(503, json={"error": "not available"})

    _install_transport(
        monkeypatch,
        handler,
    )

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "failed"


def test_connection_error_is_reported_as_failed(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install_transport(monkeypatch, handler)

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "failed"


def test_timeout_is_reported_without_claiming_completion(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("request timed out", request=request)

    _install_transport(monkeypatch, handler)

    assert dispatch_resolution_event(
        _settings(),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "timed_out"


@pytest.mark.parametrize(
    "token_input",
    [
        "unit-test-token",
        "Bearer unit-test-token",
        "bearer unit-test-token",
        "Bearer  unit-test-token",
        'Bearer "unit-test-token"',
    ],
)
def test_authorization_header_handles_bearer_prefix_without_duplication(token_input, monkeypatch):
    observed = {}

    def handler(request):
        observed["headers"] = request.headers
        event_key = request.headers["Idempotency-Key"]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "event_idempotency_key": event_key,
                "demo_result": "simulated_notification",
            },
        )

    _install_transport(monkeypatch, handler)

    status = dispatch_resolution_event(
        _settings(token=token_input),
        "case-test-1",
        _approved_result(resolution_type="refund"),
        mock_mode=False,
    )

    assert status == "completed"
    assert observed["headers"]["Authorization"] == "Bearer unit-test-token"


def test_empty_token_after_bearer_prefix_fails_safely(monkeypatch):
    monkeypatch.setattr(
        "resolveai.n8n_integration.httpx.Client", _unexpected_http_client
    )

    assert dispatch_resolution_event(
        _settings(token="Bearer "),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "failed"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:5678/webhook/resolveai-case-event",
        "http://127.0.0.1:5678/webhook/resolveai-case-event",
        "http://n8n:5678/webhook/resolveai-case-event",
        "http://host.docker.internal:5678/webhook/resolveai-case-event",
        "https://n8n.example.test/webhook/resolveai-case-event",
    ],
)
def test_valid_webhook_hosts_accepted_for_delivery(url, monkeypatch):
    def handler(request):
        event_key = request.headers["Idempotency-Key"]
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "event_idempotency_key": event_key,
                "demo_result": "simulated_notification",
            },
        )

    _install_transport(monkeypatch, handler)

    assert dispatch_resolution_event(
        _settings(url=url),
        "case-test-1",
        _approved_result(),
        mock_mode=False,
    ) == "completed"
