from prometheus_client import CollectorRegistry, Counter, Histogram


class HttpMetrics:
    """HTTP metrics bound to an explicit registry so each app instance (and test) is isolated."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self.registry = registry
        self.requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests.",
            ["method", "route", "status"],
            registry=registry,
        )
        self.request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ["method", "route"],
            registry=registry,
        )

    def observe(self, method: str, route: str, status: int, duration_seconds: float) -> None:
        self.requests_total.labels(method=method, route=route, status=str(status)).inc()
        self.request_duration_seconds.labels(method=method, route=route).observe(duration_seconds)
