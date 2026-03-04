"""LLM provider configuration API."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/providers")
async def list_providers(request: Request):
    """Return available LLM providers and their models."""
    llm_config = request.app.state.llm_config
    return {
        "defaults": {
            "provider": llm_config.defaults.provider,
            "model": llm_config.defaults.model,
        },
        "providers": llm_config.list_available(),
    }
