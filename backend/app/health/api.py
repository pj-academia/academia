from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.health.checks import DependencyCheck, run_checks

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "down"]


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckStatus]


@router.get("/health", response_model=HealthReport)
async def health(request: Request, response: Response) -> HealthReport:
    checks: list[DependencyCheck] = request.app.state.health_checks
    timeout: float = request.app.state.settings.health_check_timeout_seconds

    results = await run_checks(checks, timeout)
    all_healthy = all(results.values())
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthReport(
        status="ok" if all_healthy else "degraded",
        checks={name: "ok" if healthy else "down" for name, healthy in results.items()},
    )
