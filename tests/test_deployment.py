"""Deployment configuration validation tests (Phase 8)."""

from pathlib import Path
import re


def test_dockerfile_backend_configuration():
    path = Path("Dockerfile")
    assert path.exists()
    content = path.read_text(encoding="utf-8")

    assert "FROM python:" in content
    assert "WORKDIR /app" in content
    assert "EXPOSE 8000" in content
    assert "HEALTHCHECK" in content
    assert "uvicorn" in content


def test_dockerfile_frontend_configuration():
    path = Path("frontend/Dockerfile")
    assert path.exists()
    content = path.read_text(encoding="utf-8")

    assert "FROM node:" in content
    assert "FROM nginx:" in content
    assert "npm run build" in content
    assert "EXPOSE 80" in content
    assert "HEALTHCHECK" in content


def test_docker_compose_production_structure():
    path = Path("docker-compose.yml")
    assert path.exists()
    content = path.read_text(encoding="utf-8")

    # Services
    assert "api:" in content
    assert "frontend:" in content
    assert "n8n:" in content

    # Volumes and networking
    assert "resolveai_data:" in content
    assert "resolveai_traces:" in content
    assert "n8n_data:" in content

    # Healthcheck and service dependency
    assert "healthcheck:" in content
    assert "service_healthy" in content

    # No hardcoded secrets in compose
    forbidden_secrets = ["sk-", "gsk_", "password123", "secret_key"]
    for s in forbidden_secrets:
        assert s not in content


def test_docker_compose_dev_structure():
    path = Path("docker-compose.dev.yml")
    assert path.exists()
    content = path.read_text(encoding="utf-8")

    assert "api:" in content
    assert "frontend:" in content
    assert "--reload" in content


def test_dockerignore_excludes_sensitive_and_ephemeral_files():
    path = Path(".dockerignore")
    assert path.exists()
    content = path.read_text(encoding="utf-8")

    assert ".env" in content
    assert ".venv" in content
    assert "data/*.db" in content
    assert "data/chroma" in content
    assert "traces/*.jsonl" in content
    assert "node_modules" in content
