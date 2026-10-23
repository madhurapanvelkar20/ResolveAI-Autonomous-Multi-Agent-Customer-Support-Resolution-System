"""Safe, opt-in delivery of approved case events to n8n."""

import logging
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field, ValidationError

from resolveai.config import Settings
from resolveai.schemas import CaseResult, ContractModel, WorkflowIntegrationStatus

logger = logging.getLogger(__name__)

ALLOWED_RESOLUTION_TYPES = frozenset(
    {"refund", "replacement", "return", "explanation", "escalation"}
)
LOCAL_WEBHOOK_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "n8n", "host.docker.internal"}
)


class ResolutionEvent(ContractModel):
    event_type: Literal["case.resolution_ready"]
    event_idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^resolveai-case-[A-Za-z0-9_-]{1,80}$"
    )
    case_id: str = Field(min_length=1, max_length=80)
    resolution_type: Literal[
        "refund", "replacement", "return", "explanation", "escalation"
    ]


class ResolutionEventResponse(ContractModel):
    status: Literal["accepted", "completed"]
    event_idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^resolveai-case-[A-Za-z0-9_-]{1,80}$"
    )
    demo_result: Literal["simulated_notification"] | None = None


def _valid_webhook_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        return bool(
            parsed.scheme in {"http", "https"}
            and hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and (parsed.port is None or 1 <= parsed.port <= 65535)
            and (
                parsed.scheme == "https"
                or hostname.lower() in LOCAL_WEBHOOK_HOSTS
            )
        )
    except ValueError:
        return False


def _eligible(case_id: str, result: CaseResult) -> bool:
    return bool(
        result.status == "resolved"
        and result.critic_decision == "approve"
        and result.resolution is not None
        and result.resolution.type.lower() in ALLOWED_RESOLUTION_TYPES
        and len(case_id) <= 80
    )


def dispatch_resolution_event(
    settings: Settings,
    case_id: str,
    result: CaseResult,
    *,
    mock_mode: bool,
) -> WorkflowIntegrationStatus:
    """Send only an approved, minimal event; never execute the resolution itself."""
    if mock_mode:
        return "mock_skipped"
    if not _eligible(case_id, result):
        return "ineligible"
    if not settings.n8n_enabled:
        return "not_configured"

    url = settings.n8n_webhook_url.strip()
    raw_token = settings.n8n_webhook_token.get_secret_value().strip()
    token = raw_token.strip("'\"")
    while token.lower().startswith("bearer ") or token.lower() == "bearer":
        if token.lower() == "bearer":
            token = ""
            break
        token = token[7:].strip().strip("'\"")
    if not url or not token or not _valid_webhook_url(url):
        logger.warning("n8n workflow integration has incomplete or invalid configuration")
        return "failed"

    resolution = result.resolution
    if resolution is None:
        return "ineligible"

    idempotency_key = f"resolveai-case-{case_id}"
    try:
        event = ResolutionEvent(
            event_type="case.resolution_ready",
            event_idempotency_key=idempotency_key,
            case_id=case_id,
            resolution_type=resolution.type.lower(),
        )
    except ValidationError:
        return "ineligible"

    try:
        with httpx.Client(
            timeout=settings.n8n_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = client.post(
                url,
                json=event.model_dump(mode="json"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": idempotency_key,
                },
            )
    except httpx.TimeoutException:
        logger.warning("n8n workflow integration timed out")
        return "timed_out"
    except httpx.InvalidURL:
        logger.warning("n8n workflow integration URL is invalid")
        return "failed"
    except httpx.RequestError:
        logger.warning("n8n workflow integration connection failed")
        return "failed"

    if not response.is_success:
        logger.warning("n8n workflow integration returned HTTP %d", response.status_code)
        return "failed"

    try:
        body = ResolutionEventResponse.model_validate(response.json())
    except (ValueError, ValidationError):
        logger.warning("n8n workflow integration returned an invalid response")
        return "failed"

    if body.event_idempotency_key != idempotency_key:
        logger.warning("n8n workflow integration response did not match the event")
        return "failed"
    if body.status == "completed":
        if body.demo_result != "simulated_notification":
            logger.warning("n8n workflow did not confirm its safe demonstration result")
            return "failed"
        return "completed"
    return "accepted"
