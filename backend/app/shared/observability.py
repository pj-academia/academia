import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.shared.metrics import HttpMetrics

REQUEST_ID_HEADER = "X-Request-ID"

logger = structlog.get_logger("app.request")


def _route_template(request: Request) -> str:
    # Use the route template (/items/{id}), never the raw path, to keep label cardinality bounded.
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, binds it to every log line and records HTTP metrics."""

    def __init__(self, app: ASGIApp, metrics: HttpMetrics) -> None:
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            logger.exception("request_failed", method=request.method, path=request.url.path)
            raise
        finally:
            duration = time.perf_counter() - start
            route = _route_template(request)
            if route != "/metrics":
                self.metrics.observe(request.method, route, status, duration)
                logger.info(
                    "request_completed",
                    method=request.method,
                    path=request.url.path,
                    route=route,
                    status=status,
                    duration_ms=round(duration * 1000, 2),
                )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
