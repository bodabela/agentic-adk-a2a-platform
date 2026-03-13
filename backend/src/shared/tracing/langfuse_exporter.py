"""OpenTelemetry SpanExporter that sends spans to Langfuse via its OTLP ingestion endpoint.

Langfuse v3+ accepts OTLP/HTTP traces at /api/public/otel/v1/traces.
Observation types (AGENT, TOOL, GENERATION) are set via the
``langfuse.observation.type`` span attribute, which the Langfuse OTLP
processor respects (unlike the REST ingestion API which only allows
SPAN/GENERATION/EVENT).

The exporter enriches each OTel span with Langfuse-specific attributes
before forwarding to the standard OTLP HTTP exporter.
"""

from __future__ import annotations

import logging
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger("tracing.langfuse")

# Langfuse OTel attribute keys (from langfuse._client.span.LangfuseOtelSpanAttributes)
_ATTR_OBS_TYPE = "langfuse.observation.type"
_ATTR_OBS_INPUT = "langfuse.observation.input"
_ATTR_OBS_OUTPUT = "langfuse.observation.output"
_ATTR_OBS_MODEL = "langfuse.observation.model.name"
_ATTR_OBS_METADATA = "langfuse.observation.metadata"
_ATTR_TRACE_NAME = "langfuse.trace.name"
_ATTR_TRACE_INPUT = "langfuse.trace.input"


class LangfuseSpanExporter(SpanExporter):
    """Enriches OTel spans with Langfuse attributes and forwards via OTLP/HTTP."""

    def __init__(self, public_key: str, secret_key: str, host: str = "http://localhost:3000"):
        self._otlp = None
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            endpoint = f"{host}/api/public/otel/v1/traces"
            self._otlp = OTLPSpanExporter(
                endpoint=endpoint,
                headers={
                    "Authorization": f"Basic {self._encode_auth(public_key, secret_key)}",
                },
            )
            logger.info("Langfuse OTLP exporter configured: %s", endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp-proto-http not installed")
        except Exception as exc:
            logger.warning("Langfuse OTLP exporter init failed: %s", exc)

    @staticmethod
    def _encode_auth(public_key: str, secret_key: str) -> str:
        import base64
        return base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not self._otlp:
            return SpanExportResult.SUCCESS

        enriched = []
        for span in spans:
            enriched_span = self._enrich(span)
            if enriched_span:
                enriched.append(enriched_span)

        if enriched:
            return self._otlp.export(enriched)
        return SpanExportResult.SUCCESS

    def _enrich(self, span: ReadableSpan) -> ReadableSpan | None:
        """Add langfuse.observation.type and other Langfuse attributes to the span."""
        attrs = dict(span.attributes or {})
        span_kind = attrs.get("span.kind", "")
        name = span.name

        extra_attrs: dict[str, str] = {}

        if span_kind in ("task", "flow"):
            extra_attrs[_ATTR_TRACE_NAME] = name
            extra_attrs[_ATTR_TRACE_INPUT] = attrs.get(
                "task.description", attrs.get("flow.name", "")
            )
            # Don't set observation type for trace root spans

        elif span_kind == "llm":
            extra_attrs[_ATTR_OBS_TYPE] = "generation"
            extra_attrs[_ATTR_OBS_MODEL] = attrs.get("llm.model", "")
            if attrs.get("llm.prompt"):
                extra_attrs[_ATTR_OBS_INPUT] = attrs["llm.prompt"]
            if attrs.get("llm.completion"):
                extra_attrs[_ATTR_OBS_OUTPUT] = attrs["llm.completion"]

        elif span_kind == "agent":
            extra_attrs[_ATTR_OBS_TYPE] = "agent"

        elif span_kind == "tool":
            extra_attrs[_ATTR_OBS_TYPE] = "tool"
            if attrs.get("tool.name"):
                extra_attrs[_ATTR_OBS_INPUT] = attrs["tool.name"]
            if attrs.get("tool.response_preview"):
                extra_attrs[_ATTR_OBS_OUTPUT] = attrs["tool.response_preview"]

        else:
            # ADK internal spans — infer type from span name
            if name.startswith("invoke_agent") or name.startswith("run_agent"):
                extra_attrs[_ATTR_OBS_TYPE] = "agent"
            elif name.startswith("execute_tool"):
                extra_attrs[_ATTR_OBS_TYPE] = "tool"
            elif name.startswith("generate_content") or name.startswith("call_llm"):
                extra_attrs[_ATTR_OBS_TYPE] = "generation"
            # else: remains a plain span

        if not extra_attrs:
            return span

        # Merge extra attributes into the span
        merged = {**attrs, **extra_attrs}
        return _with_attributes(span, merged)

    def shutdown(self) -> None:
        if self._otlp:
            self._otlp.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        if self._otlp:
            return self._otlp.force_flush(timeout_millis)
        return True


def _with_attributes(span: ReadableSpan, new_attrs: dict) -> ReadableSpan:
    """Return a shallow copy of span with replaced attributes.

    ReadableSpan is immutable, so we create a new instance with the updated
    attributes while preserving all other fields.
    """
    from opentelemetry.sdk.trace import ReadableSpan as RS

    new_span = RS(
        name=span.name,
        context=span.context,
        kind=span.kind,
        parent=span.parent,
        resource=span.resource,
        attributes=new_attrs,
        events=span.events,
        links=span.links,
        status=span.status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_info=span.instrumentation_info,
    )
    return new_span
