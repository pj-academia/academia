"""Composition root: the only place that decides which adapter implements each port."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.health.checks import ChromaCheck, DependencyCheck, PostgresCheck
from app.shared.config import Settings


@dataclass(frozen=True)
class Container:
    health_checks: list[DependencyCheck]


@asynccontextmanager
async def build_container(settings: Settings) -> AsyncIterator[Container]:
    engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
    http_client = httpx.AsyncClient(timeout=settings.health_check_timeout_seconds)
    try:
        yield Container(
            health_checks=[
                PostgresCheck(engine),
                ChromaCheck(http_client, settings.chroma_url),
            ]
        )
    finally:
        await http_client.aclose()
        await engine.dispose()
