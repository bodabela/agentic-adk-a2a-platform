"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    tags=["Client: Health"],
    summary="Service health check",
    description="Returns the current health status of the Agent Platform service. "
    "Use this endpoint for liveness probes and uptime monitoring.",
    response_description="Health status object with service name.",
)
async def health_check():
    return {"status": "ok", "service": "agent-platform"}
