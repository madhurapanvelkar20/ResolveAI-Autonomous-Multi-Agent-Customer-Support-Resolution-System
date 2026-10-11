"""ResolveAI HTTP API."""

from fastapi import FastAPI

from resolveai.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.get("/health")
def health():
    """Return application health without making an LLM request."""
    configured_providers = []

    for provider in settings.llm_provider_order:
        model = getattr(settings, f"{provider}_model", "")

        if not model.strip():
            continue

        if provider == "ollama":
            configured_providers.append(provider)
            continue

        api_key = getattr(
            settings, f"{provider}_api_key"
        ).get_secret_value()

        if api_key.strip():
            configured_providers.append(provider)

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "providers": configured_providers,
    }