from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from starlette.responses import Response

from app.bootstrap import Container, build_container
from app.health.api import router as health_router
from app.shared.config import Settings, get_settings
from app.shared.logging import configure_logging
from app.shared.metrics import HttpMetrics
from app.shared.observability import REQUEST_ID_HEADER, ObservabilityMiddleware

ContainerFactory = Callable[[Settings], AbstractAsyncContextManager[Container]]


def create_app(
    settings: Settings | None = None,
    container_factory: ContainerFactory = build_container,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    metrics = HttpMetrics(CollectorRegistry())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with container_factory(settings) as container:
            app.state.health_checks = container.health_checks
            structlog.get_logger("app").info("startup_complete", app_name=settings.app_name)
            yield

    app = FastAPI(title="Academia IA API RECORDED", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(ObservabilityMiddleware, metrics=metrics)
    # Added last so it wraps everything, including error responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
