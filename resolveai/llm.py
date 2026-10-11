
"""Provider-agnostic LLM clients and structured output handling."""

import json
import re
import time
from collections import deque
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from resolveai.config import Settings


class LLMError(RuntimeError):
    """Raised when an LLM provider request fails."""


class InvalidAgentOutput(LLMError):
    """Raised when the model cannot produce valid structured output."""


class OpenAICompatLLM:
    """Minimal chat-completions client for compatible providers."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 30,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise LLMError(f"LLM transport failure: {exc}") from exc
                self.sleep(min(2**attempt, 8))
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else 2**attempt
                    except ValueError:
                        delay = 2**attempt
                    self.sleep(max(0, min(delay, 60)))
                    continue

            return response

        raise LLMError(f"LLM request failed: {last_error}")

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        """Return the first assistant message, retrying transient failures."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = self._post(payload)

        # Some OpenAI-compatible endpoints do not support JSON mode.
        if json_mode and response.status_code == 400:
            payload.pop("response_format", None)
            response = self._post(payload)

        if response.is_error:
            body = response.text[:300]
            raise LLMError(
                f"Provider returned HTTP {response.status_code}: {body}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Provider returned an invalid chat response") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("Provider returned empty assistant content")

        return content.strip()


class FallbackLLM:
    """Try configured providers in order, skipping unavailable cloud keys."""

    def __init__(self, settings: Settings, clients: dict[str, Any]):
        self.settings = settings
        self.clients = clients

    
    def _configured(self, provider: str) -> bool:
        model = getattr(self.settings, f"{provider}_model", "")
        if not model.strip():
            return False

        if provider == "ollama":
            return True

        key = getattr(self.settings, f"{provider}_api_key")
        return bool(key.get_secret_value().strip())


    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        failures = []

        for provider in self.settings.llm_provider_order:
            client = self.clients.get(provider)

            if client is None or not self._configured(provider):
                continue

            try:
                return client.complete(messages, json_mode=json_mode)
            except LLMError as exc:
                failures.append(f"{provider}: {exc}")

        detail = "; ".join(failures) or "No configured provider is available"
        raise LLMError(f"All LLM providers failed. {detail}")


T = TypeVar("T", bound=BaseModel)


class StructuredLLM:
    """Request, parse, validate, and retry structured agent output."""

    def __init__(self, client: Any, max_validation_retries: int = 2):
        self.client = client
        self.max_validation_retries = max_validation_retries

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        fenced = re.search(
            r"```(?:json)?\s*(.*?)```",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced:
            cleaned = fenced.group(1).strip()

        # Permit short explanatory text surrounding a JSON object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object found")

        value = json.loads(cleaned[start:end + 1])
        if not isinstance(value, dict):
            raise ValueError("Expected one JSON object")
        return value

    def decide(
        self,
        agent: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
        tracer: Any = None,
    ) -> T:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None

        for attempt in range(self.max_validation_retries + 1):
            try:
                raw = self.client.complete(messages, json_mode=True)
                parsed = self._extract_json(raw)
                return schema.model_validate(parsed)
            except (ValueError, ValidationError) as exc:
                last_error = exc
                if tracer is not None:
                    tracer.log(
                        case_id="unknown",
                        iteration=attempt,
                        event="validation_error",
                        agent=agent,
                        reason_summary=str(exc)[:300],
                    )
                if attempt >= self.max_validation_retries:
                    break

                messages.append({
                    "role": "assistant",
                    "content": raw if "raw" in locals() else "",
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was invalid. Return exactly "
                        "one JSON object matching this schema. Correct these "
                        f"errors: {str(exc)[:1000]}"
                    ),
                })

        raise InvalidAgentOutput(
            f"{agent} did not produce valid structured output: {last_error}"
        )


class ScriptedLLM:
    """Deterministic offline client for tests."""

    def __init__(self, responses: list[str | Exception]):
        self.responses = deque(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        self.calls.append({
            "messages": messages,
            "json_mode": json_mode,
        })

        if not self.responses:
            raise LLMError("ScriptedLLM has no responses remaining")

        response = self.responses.popleft()
        if isinstance(response, Exception):
            if isinstance(response, LLMError):
                raise response
            raise LLMError(str(response)) from response

        return response
