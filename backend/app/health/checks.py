import asyncio
from typing import Protocol

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)


class DependencyCheck(Protocol):
    """A downstream dependency whose availability is reported by /health."""

    name: str

    async def is_healthy(self) -> bool: ...


class PostgresCheck:
    name = "postgres"

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def is_healthy(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as error:
            logger.warning("dependency_unhealthy", dependency=self.name, error=str(error))
            return False
        return True


class ChromaCheck:
    name = "chroma"

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._heartbeat_url = f"{base_url.rstrip('/')}/api/v2/heartbeat"

    async def is_healthy(self) -> bool:
        try:
            response = await self._client.get(self._heartbeat_url)
        except httpx.HTTPError as error:
            logger.warning("dependency_unhealthy", dependency=self.name, error=str(error))
            return False
        return response.is_success


async def run_checks(checks: list[DependencyCheck], timeout_seconds: float) -> dict[str, bool]:
    """Run every check concurrently; a check that exceeds the timeout counts as unhealthy."""

    async def guarded(check: DependencyCheck) -> bool:
        try:
            return await asyncio.wait_for(check.is_healthy(), timeout=timeout_seconds)
        except TimeoutError:
            logger.warning("dependency_timeout", dependency=check.name)
            return False

    results = await asyncio.gather(*(guarded(check) for check in checks))
    return {check.name: result for check, result in zip(checks, results, strict=True)}
