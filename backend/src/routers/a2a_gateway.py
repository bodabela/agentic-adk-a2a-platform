"""A2A Gateway discovery and catalog endpoints."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/catalog",
    tags=["A2A: Discovery"],
    summary="List all exposed A2A endpoints",
    description=(
        "Returns every agent, root-agent and flow that has `expose: true` in "
        "its YAML definition, together with its full A2A agent card.  External "
        "systems can use this endpoint for service discovery."
    ),
    response_description="Catalog of exposed A2A endpoints with agent cards.",
)
async def get_catalog(request: Request):
    gateway = request.app.state.a2a_gateway
    return {
        "endpoints": gateway.get_catalog(),
        "platform_discovery_url": "/.well-known/agents.json",
    }
