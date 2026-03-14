"""ADK agent callbacks for OpenTelemetry + Langfuse instrumentation.

These callbacks are injected into ADK Agent() constructors to create
spans for agent runs, LLM calls, and tool invocations.

Uses Langfuse @observe() decorators to automatically set observation types
(AGENT, TOOL, GENERATION) enabling the Agent Graph visualization.
OTel context propagation maintains the span hierarchy:

    Task/Flow span > Agent span > LLM/Tool span
"""

from __future__ import annotations

import json
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

# Langfuse observation type attribute key
_LANGFUSE_OBS_TYPE = "langfuse.observation.type"
_LANGFUSE_OBS_MODEL = "langfuse.observation.model.name"
_LANGFUSE_OBS_INPUT = "langfuse.observation.input"
_LANGFUSE_OBS_OUTPUT = "langfuse.observation.output"


def _to_json(obj: Any, max_len: int = 32000) -> str:
    """Serialize an object to a JSON string for Langfuse OTLP attributes.

    Langfuse expects valid JSON strings for input/output values.
    We use a generous limit — OTel attribute limits can be configured separately.
    """
    try:
        if obj is None:
            return ""
        if isinstance(obj, str):
            # Truncate the string BEFORE json.dumps so the JSON stays valid
            truncated = obj[:max_len]
            return json.dumps(truncated, ensure_ascii=False)
        if isinstance(obj, (dict, list)):
            raw = json.dumps(obj, default=str, ensure_ascii=False)
            if len(raw) > max_len:
                # Fallback: convert to string repr and wrap as JSON string
                return json.dumps(str(obj)[:max_len], ensure_ascii=False)
            return raw
        return json.dumps(str(obj)[:max_len], ensure_ascii=False)
    except Exception:
        return ""


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


def _before_agent(callback_context: Any = None, **_kwargs: Any) -> Any:
    """Start an agent span when the agent begins processing."""
    tracer = get_tracer()
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"

    # Extract user input from callback_context.user_content (ADK Content object)
    input_text = ""
    try:
        user_content = getattr(callback_context, "user_content", None)
        if user_content and hasattr(user_content, "parts"):
            parts_text = []
            for part in user_content.parts:
                if hasattr(part, "text") and part.text:
                    parts_text.append(part.text)
            if parts_text:
                input_text = _to_json(" ".join(parts_text))
        logger.info("_before_agent %s | user_content=%s | input=%r",
                     agent_name, type(user_content).__name__ if user_content else None,
                     input_text[:200] if input_text else "EMPTY")
    except Exception as exc:
        logger.warning("_before_agent input extraction failed: %s", exc)

    attrs: dict[str, str] = {
        "agent.name": agent_name,
        "span.kind": "agent",
        _LANGFUSE_OBS_TYPE: "agent",
    }
    if input_text:
        attrs[_LANGFUSE_OBS_INPUT] = input_text

    span = tracer.start_span(f"agent:{agent_name}", attributes=attrs)
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _agent_span_var.set(span)
    _agent_span_token_var.set(token)
    return None  # Don't override agent behavior


def _after_agent(callback_context: Any = None, **_kwargs: Any) -> Any:
    """End the agent span."""
    span = _agent_span_var.get(None)
    token = _agent_span_token_var.get(None)
    if span:
        # Try to capture agent output from the session events
        try:
            session = getattr(callback_context, "session", None)
            if session and hasattr(session, "events"):
                events = session.events or []
                for event in reversed(events):
                    content = getattr(event, "content", None)
                    if content and hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                span.set_attribute(_LANGFUSE_OBS_OUTPUT, _to_json(part.text))
                                break
                        break
        except Exception:
            pass
        span.set_status(trace.StatusCode.OK)
        span.end()
        _agent_span_var.set(None)
    if token:
        trace.context_api.detach(token)
        _agent_span_token_var.set(None)
    return None


# -- Model (LLM) callbacks -------------------------------------------------


def _before_model(callback_context: Any = None, llm_request: Any = None, **_kwargs: Any) -> Any:
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
            _LANGFUSE_OBS_TYPE: "generation",
            _LANGFUSE_OBS_MODEL: model,
        },
    )
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _model_span_var.set(span)
    _model_span_token_var.set(token)
    _model_start_time_var.set(time.monotonic())

    # Capture prompt for Langfuse (must be valid JSON string)
    try:
        if hasattr(llm_request, "contents") and llm_request.contents:
            for content in reversed(llm_request.contents):
                if hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            val = _to_json(part.text)
                            span.set_attribute(_LANGFUSE_OBS_INPUT, val)
                            logger.debug("_before_model input set: %r", val[:200] if val else "")
                            break
                    break
        else:
            logger.debug("_before_model: no contents on llm_request (type=%s, attrs=%s)",
                          type(llm_request).__name__, dir(llm_request)[:10] if llm_request else "None")
    except Exception as exc:
        logger.debug("_before_model input extraction failed: %s", exc)

    return None  # Don't override LLM behavior


def _after_model(callback_context: Any = None, llm_response: Any = None, **_kwargs: Any) -> Any:
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

        # Capture completion text for Langfuse (must be valid JSON string)
        try:
            if hasattr(llm_response, "content") and llm_response.content:
                parts = getattr(llm_response.content, "parts", None) or []
                for part in parts:
                    if hasattr(part, "text") and part.text:
                        val = _to_json(part.text)
                        span.set_attribute(_LANGFUSE_OBS_OUTPUT, val)
                        logger.debug("_after_model output set: %r", val[:200] if val else "")
                        break
            else:
                logger.debug("_after_model: no content on llm_response (type=%s)", type(llm_response).__name__)
        except Exception as exc:
            logger.debug("_after_model output extraction failed: %s", exc)

        span.set_status(trace.StatusCode.OK)
        span.end()
        _model_span_var.set(None)
        _model_start_time_var.set(0.0)

    if token:
        trace.context_api.detach(token)
        _model_span_token_var.set(None)

    return None


# -- Tool callbacks ---------------------------------------------------------


def _before_tool(*, tool: Any = None, args: Any = None, tool_context: Any = None, **_kwargs: Any) -> Any:
    """Start a tool span before tool invocation.

    ADK calls: callback(tool=tool, args=function_args, tool_context=tool_context)
    """
    tracer = get_tracer()

    name = ""
    if tool and hasattr(tool, "name"):
        name = tool.name
    elif tool and hasattr(tool, "__name__"):
        name = tool.__name__

    agent_name = ""
    if tool_context:
        agent_name = getattr(tool_context, "agent_name", "") or ""

    # Capture tool arguments as input
    input_text = _to_json(args) if args else ""
    logger.info("_before_tool %s | args=%r | input=%r",
                name, type(args).__name__ if args else None, input_text[:200] if input_text else "EMPTY")

    attrs: dict[str, str] = {
        "tool.name": name or "unknown",
        "tool.agent": agent_name,
        "span.kind": "tool",
        _LANGFUSE_OBS_TYPE: "tool",
    }
    if input_text:
        attrs[_LANGFUSE_OBS_INPUT] = input_text

    span = tracer.start_span(f"tool:{name or 'call'}", attributes=attrs)
    token = trace.context_api.attach(trace.set_span_in_context(span))
    _tool_span_var.set(span)
    _tool_span_token_var.set(token)
    _tool_start_time_var.set(time.monotonic())
    return None  # Don't override tool behavior


def _after_tool(*, tool: Any = None, args: Any = None, tool_context: Any = None, tool_response: Any = None, **_kwargs: Any) -> Any:
    """End the tool span with result metadata.

    ADK calls: callback(tool=tool, args=function_args, tool_context=tool_context, tool_response=function_response)
    """
    span = _tool_span_var.get(None)
    token = _tool_span_token_var.get(None)
    start = _tool_start_time_var.get(0.0)

    if span:
        latency_ms = int((time.monotonic() - start) * 1000) if start else 0
        span.set_attribute("tool.latency_ms", latency_ms)

        if tool_response is not None:
            resp_str = _to_json(tool_response)
            span.set_attribute("tool.response_size", len(resp_str))
            span.set_attribute(_LANGFUSE_OBS_OUTPUT, resp_str)
            logger.debug("_after_tool output set: %r", resp_str[:200] if resp_str else "")

        span.set_status(trace.StatusCode.OK)
        span.end()
        _tool_span_var.set(None)
        _tool_start_time_var.set(0.0)

    if token:
        trace.context_api.detach(token)
        _tool_span_token_var.set(None)

    return None
