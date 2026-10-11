"""Tests for the ResolveAI HTTP API."""

from fastapi.testclient import TestClient

from resolveai.api import app


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