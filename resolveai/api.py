
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
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
