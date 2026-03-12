"""Traces router — trace-to-diagram mapping and observability config."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["Client: Observability"])


@router.get("/config")
async def get_observability_config(request: Request):
    """Return observability URLs for frontend deep-links."""
    settings = request.app.state.settings
    return {
        "tracing_enabled": settings.tracing_enabled,
        "grafana_base_url": settings.grafana_base_url,
        "langfuse_enabled": settings.langfuse_enabled,
        "langfuse_base_url": settings.langfuse_base_url,
    }


@router.get("/{trace_id}/diagram")
async def get_trace_diagram(trace_id: str, request: Request):
    """Return diagram data for a given trace ID.

    Looks up the trace_id in the registry to find the associated
    task or flow, then returns the event data needed for rendering.
    """
    from src.shared.tracing.context import trace_registry

    mapping = trace_registry.get(trace_id)
    if not mapping:
        return {"error": "trace not found", "trace_id": trace_id}

    entity_type, entity_id = mapping
    cost_tracker = request.app.state.cost_tracker
    report = cost_tracker.get_report(entity_id)

    return {
        "trace_id": trace_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "cost_report": report.model_dump(mode="json") if report else None,
    }
