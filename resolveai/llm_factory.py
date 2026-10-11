
"""Build configured LLM clients from application settings."""

from resolveai.config import Settings, get_settings
from resolveai.llm import FallbackLLM, OpenAICompatLLM


def build_llm(settings: Settings | None = None) -> FallbackLLM:
    """Create clients for providers that have the required configuration."""
    settings = settings or get_settings()
    clients = {}

    provider_settings = {
        "groq": (
            settings.groq_base_url,
            settings.groq_model,
            settings.groq_api_key.get_secret_value(),
        ),
        "gemini": (
            settings.gemini_base_url,
            settings.gemini_model,
            settings.gemini_api_key.get_secret_value(),
        ),
        "ollama": (
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_api_key.get_secret_value(),
        ),
    }

    for provider in settings.llm_provider_order:
        base_url, model, api_key = provider_settings[provider]

        if not model.strip():
            continue
        if provider != "ollama" and not api_key.strip():
            continue

        clients[provider] = OpenAICompatLLM(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    return FallbackLLM(settings, clients)
