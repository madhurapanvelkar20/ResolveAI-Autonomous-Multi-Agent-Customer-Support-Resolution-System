
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
