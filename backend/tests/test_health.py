from tests.conftest import FakeCheck


def test_health_is_ok_when_every_dependency_is_healthy(make_client):
    client = make_client(FakeCheck("postgres", True), FakeCheck("chroma", True))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "chroma": "ok"}}


def test_health_is_degraded_when_a_dependency_is_down(make_client):
    client = make_client(FakeCheck("postgres", True), FakeCheck("chroma", False))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": {"postgres": "ok", "chroma": "down"}}
