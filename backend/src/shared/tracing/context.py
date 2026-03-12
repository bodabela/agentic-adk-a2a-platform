"""Trace context propagation helpers.

Provides context managers for creating root and child spans,
and utilities for extracting trace IDs into event payloads.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

from opentelemetry import context as otel_context, trace

from src.shared.tracing.provider import get_tracer

# Store the current span per-task for async context propagation
_current_span_var: ContextVar[trace.Span | None] = ContextVar("_current_span", default=None)

# Registry: trace_id (hex) -> (entity_type, entity_id)
# Allows reverse lookup from trace to task/flow
trace_registry: dict[str, tuple[str, str]] = {}


@contextmanager
def start_task_span(task_id: str, description: str = "") -> Generator[trace.Span, None, None]:
    """Create a root span for a task execution."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"task:{task_id[:8]}",
        attributes={
            "task.id": task_id,
            "task.description": description[:500],
            "span.kind": "task",
        },
    ) as span:
        _current_span_var.set(span)
        # Register trace → task mapping
        trace_id = _format_trace_id(span.get_span_context().trace_id)
        trace_registry[trace_id] = ("task", task_id)
        try:
            yield span
        finally:
            _current_span_var.set(None)


@contextmanager
def start_flow_span(flow_id: str, flow_name: str = "") -> Generator[trace.Span, None, None]:
    """Create a root span for a flow execution."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"flow:{flow_name or flow_id[:8]}",
        attributes={
            "flow.id": flow_id,
            "flow.name": flow_name,
            "span.kind": "flow",
        },
    ) as span:
        _current_span_var.set(span)
        trace_id = _format_trace_id(span.get_span_context().trace_id)
        trace_registry[trace_id] = ("flow", flow_id)
        try:
            yield span
        finally:
            _current_span_var.set(None)


@contextmanager
def start_state_span(
    flow_id: str, state_name: str, node_type: str = "",
) -> Generator[trace.Span, None, None]:
    """Create a child span for a flow state node."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"state:{state_name}",
        attributes={
            "flow.id": flow_id,
            "flow.state": state_name,
            "flow.node_type": node_type,
            "span.kind": "state",
        },
    ) as span:
        yield span


def get_current_trace_ids() -> tuple[str, str]:
    """Extract (trace_id, span_id) as hex strings from the active OTel context.

    Returns ("", "") if no active span.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id and ctx.span_id:
        return (
            _format_trace_id(ctx.trace_id),
            _format_span_id(ctx.span_id),
        )
    return ("", "")


def inject_trace_to_event(data: dict[str, Any]) -> dict[str, Any]:
    """Inject trace_id and span_id into an event dict for the EventBus.

    Mutates and returns the same dict for convenience.
    """
    trace_id, span_id = get_current_trace_ids()
    if trace_id:
        data["trace_id"] = trace_id
        data["span_id"] = span_id
    return data


def _format_trace_id(trace_id: int) -> str:
    """Format a 128-bit trace ID as a 32-char hex string."""
    return format(trace_id, "032x")


def _format_span_id(span_id: int) -> str:
    """Format a 64-bit span ID as a 16-char hex string."""
    return format(span_id, "016x")
