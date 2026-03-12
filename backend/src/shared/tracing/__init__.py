"""Tracing & observability — OpenTelemetry instrumentation for the agent platform."""

from src.shared.tracing.provider import init_tracing, get_tracer, shutdown_tracing
from src.shared.tracing.context import (
    start_task_span,
    start_flow_span,
    start_state_span,
    get_current_trace_ids,
    inject_trace_to_event,
)
from src.shared.tracing.callbacks import make_adk_callbacks

__all__ = [
    "init_tracing",
    "get_tracer",
    "shutdown_tracing",
    "start_task_span",
    "start_flow_span",
    "start_state_span",
    "get_current_trace_ids",
    "inject_trace_to_event",
    "make_adk_callbacks",
]
