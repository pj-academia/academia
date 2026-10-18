import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.shared.config import Settings

pytestmark = pytest.mark.integration


def test_health_reaches_real_postgres_and_chroma():
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200, response.json()
    assert response.json()["checks"] == {"postgres": "ok", "chroma": "ok"}
