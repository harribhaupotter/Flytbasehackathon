import time
from fastapi import APIRouter, Request
from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Liveness probe.
    Extremely lightweight, zero dependency checks, no auth required.
    """
    start_time = getattr(request.app.state, "start_time", None)
    uptime_s = round(time.time() - start_time, 2) if start_time else 0.0

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        uptime_s=uptime_s,
    )
