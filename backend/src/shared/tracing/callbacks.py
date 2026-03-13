"""ADK agent callbacks for OpenTelemetry instrumentation.

These callbacks are injected into ADK Agent() constructors to create
spans for agent runs, LLM calls, and tool invocations. The span hierarchy
is automatically maintained through OTel context propagation:

    Task/Flow span > Agent span > LLM/Tool span
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace

from src.shared.tracing.provider import get_tracer

logger = logging.getLogger("tracing.callbacks")

# Per-agent span tracking via contextvars (supports async concurrency)
_agent_span_var: ContextVar[trace.Span | None] = ContextVar("_agent_span", default=None)
_agent_span_token_var: ContextVar[Any] = ContextVar("_agent_span_token", default=None)

_model_span_var: ContextVar[trace.Span | None] = ContextVar("_model_span", default=None)
_model_span_token_var: ContextVar[Any] = ContextVar("_model_span_token", default=None)
_model_start_time_var: ContextVar[float] = ContextVar("_model_start_time", default=0.0)

_tool_span_var: ContextVar[trace.Span | None] = ContextVar("_tool_span", default=None)
_tool_span_token_var: ContextVar[Any] = ContextVar("_tool_span_token", default=None)
_tool_start_time_var: ContextVar[float] = ContextVar("_tool_start_time", default=0.0)


def make_adk_callbacks() -> dict[str, Any]:
    """Return a dict of ADK callback kwargs ready for Agent() constructor.

    Usage::

        agent = Agent(
            model=model,
            name=name,
            **make_adk_callbacks(),
        )
    """
    return {
        "before_agent_callback": _before_agent,
        "after_agent_callback": _after_agent,
        "before_model_callback": _before_model,
        "after_model_callback": _after_model,
        "before_tool_callback": _before_tool,
        "after_tool_callback": _after_tool,
    }


# -- Agent callbacks --------------------------------------------------------


def _before_agent(callback_context: Any = None, *args: Any, **kwargs: Any) -> Any:
    """Start an agent span when the agent begins processing."""
    tracer = get_tracer()
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"
    logger.info("before_agent_callback fired for agent=%s", agent_name)

    span = tracer.start_span(
        f"agent:{agent_name}",
        attributes={
            "agent.name": agent_name,
            "span.kind": "agent",
        },
    )
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _agent_span_var.set(span)
    _agent_span_token_var.set(token)
    return None  # Don't override agent behavior


def _after_agent(callback_context: Any = None, *args: Any, **kwargs: Any) -> Any:
    """End the agent span."""
    span = _agent_span_var.get(None)
    token = _agent_span_token_var.get(None)
    if span:
        span.set_status(trace.StatusCode.OK)
        span.end()
        _agent_span_var.set(None)
    if token:
        trace.context_api.detach(token)
        _agent_span_token_var.set(None)
    return None


# -- Model (LLM) callbacks -------------------------------------------------


def _before_model(callback_context: Any = None, llm_request: Any = None, *args: Any, **kwargs: Any) -> Any:
    """Start an LLM span before the model call."""
    tracer = get_tracer()
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"

    # Extract model name from the request or context
    model = ""
    if hasattr(llm_request, "model"):
        model = str(llm_request.model or "")
    elif hasattr(callback_context, "state") and isinstance(callback_context.state, dict):
        model = callback_context.state.get("model", "")

    span = tracer.start_span(
        f"llm:{model or 'call'}",
        attributes={
            "llm.model": model,
            "llm.agent": agent_name,
            "span.kind": "llm",
        },
    )
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _model_span_var.set(span)
    _model_span_token_var.set(token)
    _model_start_time_var.set(time.monotonic())

    # Capture prompt for Langfuse (stored as span attribute)
    try:
        if hasattr(llm_request, "contents") and llm_request.contents:
            # Extract last user message text for prompt tracking
            for content in reversed(llm_request.contents):
                if hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            span.set_attribute("llm.prompt", part.text[:4000])
                            break
                    break
    except Exception:
        pass

    return None  # Don't override LLM behavior


def _after_model(callback_context: Any = None, llm_response: Any = None, *args: Any, **kwargs: Any) -> Any:
    """End the LLM span with usage metrics."""
    span = _model_span_var.get(None)
    token = _model_span_token_var.get(None)
    start = _model_start_time_var.get(0.0)

    if span:
        latency_ms = int((time.monotonic() - start) * 1000) if start else 0
        span.set_attribute("llm.latency_ms", latency_ms)

        # Extract token usage from response
        if hasattr(llm_response, "usage_metadata"):
            usage = llm_response.usage_metadata
            if usage:
                input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage, "candidates_token_count", 0) or 0
                span.set_attribute("llm.input_tokens", input_tokens)
                span.set_attribute("llm.output_tokens", output_tokens)
                span.set_attribute("llm.total_tokens", input_tokens + output_tokens)

        # Capture completion text for Langfuse
        try:
            if hasattr(llm_response, "content") and llm_response.content:
                parts = getattr(llm_response.content, "parts", None) or []
                for part in parts:
                    if hasattr(part, "text") and part.text:
                        span.set_attribute("llm.completion", part.text[:4000])
                        break
        except Exception:
            pass

        span.set_status(trace.StatusCode.OK)
        span.end()
        _model_span_var.set(None)
        _model_start_time_var.set(0.0)

    if token:
        trace.context_api.detach(token)
        _model_span_token_var.set(None)

    return None


# -- Tool callbacks ---------------------------------------------------------


def _before_tool(*args: Any, **kwargs: Any) -> Any:
    """Start a tool span before tool invocation.

    ADK tool callback signature: (tool=..., args=..., tool_context=...)
    """
    tracer = get_tracer()

    # ADK passes kwargs, not positional args
    tool_obj = args[0] if args else kwargs.get("tool")
    tool_context = args[2] if len(args) > 2 else kwargs.get("tool_context")

    name = ""
    if tool_obj and hasattr(tool_obj, "name"):
        name = tool_obj.name
    elif tool_obj and hasattr(tool_obj, "__name__"):
        name = tool_obj.__name__

    agent_name = ""
    if tool_context:
        agent_name = getattr(tool_context, "agent_name", "") or ""
    logger.info("before_tool_callback fired tool=%s agent=%s", name, agent_name)

    span = tracer.start_span(
        f"tool:{name or 'call'}",
        attributes={
            "tool.name": name or "unknown",
            "tool.agent": agent_name,
            "span.kind": "tool",
        },
    )
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _tool_span_var.set(span)
    _tool_span_token_var.set(token)
    _tool_start_time_var.set(time.monotonic())
    return None  # Don't override tool behavior


def _after_tool(*args: Any, **kwargs: Any) -> Any:
    """End the tool span with result metadata.

    ADK tool callback signature: (tool=..., args=..., tool_context=..., tool_response=...)
    """
    span = _tool_span_var.get(None)
    token = _tool_span_token_var.get(None)
    start = _tool_start_time_var.get(0.0)

    tool_response = args[3] if len(args) > 3 else kwargs.get("tool_response")

    if span:
        latency_ms = int((time.monotonic() - start) * 1000) if start else 0
        span.set_attribute("tool.latency_ms", latency_ms)

        if tool_response is not None:
            resp_str = str(tool_response)
            span.set_attribute("tool.response_size", len(resp_str))
            span.set_attribute("tool.response_preview", resp_str[:500])

        span.set_status(trace.StatusCode.OK)
        span.end()
        _tool_span_var.set(None)
        _tool_start_time_var.set(0.0)

    if token:
        trace.context_api.detach(token)
        _tool_span_token_var.set(None)

    return None
