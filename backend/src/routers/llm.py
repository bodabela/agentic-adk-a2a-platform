"""LLM provider configuration API."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/providers",
    tags=["Admin: LLM"],
    summary="List LLM providers and models",
    description="Returns the configured LLM providers with their available models, pricing information, "
    "and the platform defaults. Provider availability depends on which API keys are configured in the environment.",
    response_description="Default provider/model and a list of all available providers with their models.",
)
async def list_providers(request: Request):
    llm_config = request.app.state.llm_config
    return {
        "defaults": {
            "provider": llm_config.defaults.provider,
            "model": llm_config.defaults.model,
        },
        "providers": llm_config.list_available(),
    }
