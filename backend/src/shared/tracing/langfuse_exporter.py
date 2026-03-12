"""Custom OpenTelemetry SpanExporter that translates spans into Langfuse observations.

This allows a single instrumentation layer (OTel callbacks) to feed both
Grafana/Tempo AND Langfuse without duplicate callback wiring.

Span mapping:
    - Root spans (task/flow)  → Langfuse Trace
    - Agent spans             → Langfuse Span
    - LLM spans               → Langfuse Generation (with prompt, completion, tokens, cost)
    - Tool spans              → Langfuse Span with tool metadata
"""

from __future__ import annotations

import logging
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger("tracing.langfuse")


class LangfuseSpanExporter(SpanExporter):
    """Exports OTel spans to Langfuse."""

    def __init__(self, public_key: str, secret_key: str, host: str = "http://localhost:3000"):
        self._client = None
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host
        self._init_client()

    def _init_client(self) -> None:
        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
            logger.info("Langfuse client initialized: %s", self._host)
        except ImportError:
            logger.warning("langfuse package not installed — Langfuse export disabled")
        except Exception as exc:
            logger.warning("Langfuse client init failed: %s", exc)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not self._client:
            return SpanExportResult.SUCCESS

        for span in spans:
            try:
                self._export_span(span)
            except Exception as exc:
                logger.debug("Langfuse export error for span %s: %s", span.name, exc)

        return SpanExportResult.SUCCESS

    def _export_span(self, span: ReadableSpan) -> None:
        attrs = dict(span.attributes or {})
        span_kind = attrs.get("span.kind", "")
        trace_id = format(span.context.trace_id, "032x")
        span_id = format(span.context.span_id, "016x")

        # Determine parent span ID
        parent_id = None
        if span.parent and span.parent.span_id:
            parent_id = format(span.parent.span_id, "016x")

        # Convert timestamps (nanoseconds → datetime)
        start_time = None
        end_time = None
        if span.start_time:
            import datetime
            start_time = datetime.datetime.fromtimestamp(
                span.start_time / 1e9, tz=datetime.timezone.utc,
            )
        if span.end_time:
            import datetime
            end_time = datetime.datetime.fromtimestamp(
                span.end_time / 1e9, tz=datetime.timezone.utc,
            )

        if span_kind in ("task", "flow"):
            # Root span → Langfuse Trace
            self._client.trace(
                id=trace_id,
                name=span.name,
                metadata={k: v for k, v in attrs.items() if k != "span.kind"},
                input=attrs.get("task.description", attrs.get("flow.name", "")),
            )

        elif span_kind == "llm":
            # LLM span → Langfuse Generation
            self._client.generation(
                trace_id=trace_id,
                id=span_id,
                parent_observation_id=parent_id,
                name=span.name,
                model=attrs.get("llm.model", ""),
                input=attrs.get("llm.prompt", ""),
                output=attrs.get("llm.completion", ""),
                usage={
                    "input": attrs.get("llm.input_tokens", 0),
                    "output": attrs.get("llm.output_tokens", 0),
                    "total": attrs.get("llm.total_tokens", 0),
                },
                metadata={
                    "agent": attrs.get("llm.agent", ""),
                    "latency_ms": attrs.get("llm.latency_ms", 0),
                },
                start_time=start_time,
                end_time=end_time,
            )

        elif span_kind == "tool":
            # Tool span → Langfuse Span
            self._client.span(
                trace_id=trace_id,
                id=span_id,
                parent_observation_id=parent_id,
                name=span.name,
                metadata={
                    "tool.name": attrs.get("tool.name", ""),
                    "tool.agent": attrs.get("tool.agent", ""),
                    "tool.latency_ms": attrs.get("tool.latency_ms", 0),
                    "tool.response_size": attrs.get("tool.response_size", 0),
                },
                input=attrs.get("tool.name", ""),
                output=attrs.get("tool.response_preview", ""),
                start_time=start_time,
                end_time=end_time,
            )

        elif span_kind == "agent":
            # Agent span → Langfuse Span
            self._client.span(
                trace_id=trace_id,
                id=span_id,
                parent_observation_id=parent_id,
                name=span.name,
                metadata={k: v for k, v in attrs.items() if k != "span.kind"},
                start_time=start_time,
                end_time=end_time,
            )

        elif span_kind == "state":
            # Flow state span → Langfuse Span
            self._client.span(
                trace_id=trace_id,
                id=span_id,
                parent_observation_id=parent_id,
                name=span.name,
                metadata={
                    "flow.state": attrs.get("flow.state", ""),
                    "flow.node_type": attrs.get("flow.node_type", ""),
                },
                start_time=start_time,
                end_time=end_time,
            )

    def shutdown(self) -> None:
        if self._client:
            try:
                self._client.flush()
            except Exception:
                pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        if self._client:
            try:
                self._client.flush()
            except Exception:
                pass
        return True
