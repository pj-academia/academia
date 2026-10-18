from tests.conftest import FakeCheck


def test_generates_a_request_id_when_the_client_sends_none(make_client):
    client = make_client(FakeCheck("postgres", True))

    response = client.get("/health")

    assert len(response.headers["X-Request-ID"]) == 32


def test_propagates_the_client_request_id(make_client):
    client = make_client(FakeCheck("postgres", True))

    response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"


def test_metrics_count_requests_by_route_template(make_client):
    client = make_client(FakeCheck("postgres", True))
    client.get("/health")

    body = client.get("/metrics").text

    assert 'http_requests_total{method="GET",route="/health",status="200"} 1.0' in body
    assert "http_request_duration_seconds_bucket" in body


def test_metrics_endpoint_does_not_measure_itself(make_client):
    client = make_client(FakeCheck("postgres", True))
    client.get("/metrics")

    body = client.get("/metrics").text

    assert 'route="/metrics"' not in body
