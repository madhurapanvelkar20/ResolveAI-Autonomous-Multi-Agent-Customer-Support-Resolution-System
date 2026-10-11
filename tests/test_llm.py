
import json

import httpx
import pytest
from pydantic import BaseModel, Field

from resolveai.config import Settings
from resolveai.llm import (
    FallbackLLM,
    InvalidAgentOutput,
    LLMError,
    OpenAICompatLLM,
    ScriptedLLM,
    StructuredLLM,
)


def response(content="hello", status=200, headers=None):
    return httpx.Response(
        status,
        headers=headers,
        json={
            "choices": [{"message": {"content": content}}],
        },
    )


def test_openai_compatible_client_success():
    transport = httpx.MockTransport(
        lambda request: response("Hello from model")
    )
    client = OpenAICompatLLM(
        base_url="http://test/v1",
        model="test-model",
        transport=transport,
    )
    try:
        assert client.complete([{"role": "user", "content": "Hi"}]) == (
            "Hello from model"
        )
    finally:
        client.close()


def test_retries_rate_limit():
    calls = {"count": 0}
    delays = []

    def handler(request):
        calls["count"] += 1
        if calls["count"] == 1:
            return response(status=429, headers={"Retry-After": "1"})
        return response("recovered")

    client = OpenAICompatLLM(
        base_url="http://test/v1",
        model="test-model",
        max_retries=1,
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    )
    try:
        result = client.complete([{"role": "user", "content": "Hi"}])
        assert result == "recovered"
        assert calls["count"] == 2
        assert delays == [1.0]
    finally:
        client.close()


def test_json_mode_falls_back_after_http_400():
    formats = []

    def handler(request):
        body = json.loads(request.content)
        formats.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unsupported"})
        return response('{"ok": true}')

    client = OpenAICompatLLM(
        base_url="http://test/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.complete(
            [{"role": "user", "content": "Return JSON"}],
            json_mode=True,
        ) == '{"ok": true}'
        assert formats == [True, False]
    finally:
        client.close()


def test_provider_http_failure_raises():
    client = OpenAICompatLLM(
        base_url="http://test/v1",
        model="test-model",
        max_retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, text="unauthorized")
        ),
    )
    try:
        with pytest.raises(LLMError, match="401"):
            client.complete([{"role": "user", "content": "Hi"}])
    finally:
        client.close()


def test_fallback_skips_cloud_provider_without_key():
    settings = Settings(
        llm_provider_order=["groq", "ollama"],
        groq_api_key="",
        groq_model="",
        ollama_model="local-model",
    )

    class Client:
        def __init__(self, result):
            self.result = result
            self.called = False

        def complete(self, messages, *, json_mode=False):
            self.called = True
            return self.result

    groq = Client("should not run")
    ollama = Client("local response")

    fallback = FallbackLLM(
        settings,
        {"groq": groq, "ollama": ollama},
    )

    assert fallback.complete([{"role": "user", "content": "Hi"}]) == (
        "local response"
    )
    assert not groq.called
    assert ollama.called


class Decision(BaseModel):
    ok: bool
    reason: str = Field(min_length=3)


def test_structured_llm_parses_fenced_json():
    client = ScriptedLLM([
        'Here is the result:\n```json\n{"ok": true, "reason": "Looks good"}\n```'
    ])
    result = StructuredLLM(client).decide(
        "triage", "Be precise", "Check this", Decision
    )
    assert result.ok is True


def test_structured_llm_retries_invalid_output():
    client = ScriptedLLM([
        '{"ok": "not-a-boolean", "reason": "Bad"}',
        '{"ok": true, "reason": "Valid response"}',
    ])
    result = StructuredLLM(client).decide(
        "triage", "Be precise", "Check this", Decision
    )
    assert result.ok is True
    assert len(client.calls) == 2


def test_structured_llm_raises_after_retries():
    client = ScriptedLLM(["not JSON", "still not JSON"])
    with pytest.raises(InvalidAgentOutput):
        StructuredLLM(client, max_validation_retries=1).decide(
            "triage", "Be precise", "Check this", Decision
        )


def test_scripted_llm_exhaustion():
    client = ScriptedLLM([])
    with pytest.raises(LLMError, match="no responses"):
        client.complete([{"role": "user", "content": "Hi"}])
from resolveai.llm_factory import build_llm


def test_malformed_provider_response_raises_llm_error():
    client = OpenAICompatLLM(
        base_url="http://test/v1",
        model="test-model",
        max_retries=0,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"unexpected": "body"})
        ),
    )

    try:
        with pytest.raises(LLMError, match="invalid chat response"):
            client.complete([{"role": "user", "content": "Hi"}])
    finally:
        client.close()


def test_fallback_uses_next_provider_after_failure():
    settings = Settings(
        llm_provider_order=["groq", "ollama"],
        groq_api_key="test-key",
        groq_model="groq-test",
        ollama_model="ollama-test",
    )

    class Client:
        def __init__(self, error=None, result="ok"):
            self.error = error
            self.result = result
            self.called = False

        def complete(self, messages, *, json_mode=False):
            self.called = True
            if self.error:
                raise self.error
            return self.result

    groq = Client(error=LLMError("temporary failure"))
    ollama = Client(result="fallback response")

    fallback = FallbackLLM(settings, {"groq": groq, "ollama": ollama})

    assert fallback.complete([{"role": "user", "content": "Hi"}]) == (
        "fallback response"
    )
    assert groq.called
    assert ollama.called


def test_fallback_raises_when_all_providers_fail():
    settings = Settings(
        llm_provider_order=["ollama"],
        ollama_model="local-test",
    )

    class Client:
        def complete(self, messages, *, json_mode=False):
            raise LLMError("provider unavailable")

    fallback = FallbackLLM(settings, {"ollama": Client()})

    with pytest.raises(LLMError, match="All LLM providers failed"):
        fallback.complete([{"role": "user", "content": "Hi"}])


def test_factory_selects_only_configured_providers():
    settings = Settings(
        llm_provider_order=["groq", "gemini", "ollama"],
        groq_api_key="test-groq-key",
        groq_model="groq-test-model",
        gemini_api_key="",
        gemini_model="gemini-test-model",
        ollama_model="",
    )

    client = build_llm(settings)

    try:
        assert list(client.clients) == ["groq"]
        assert client.clients["groq"].model == "groq-test-model"
    finally:
        for provider_client in client.clients.values():
            provider_client.close()


def test_structured_llm_propagates_provider_failure():
    client = ScriptedLLM([LLMError("provider unavailable")])

    with pytest.raises(LLMError, match="provider unavailable"):
        StructuredLLM(client).decide(
            "triage",
            "Return a valid decision",
            "Check this ticket",
            Decision,
        )