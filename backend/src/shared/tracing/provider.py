"""OpenTelemetry TracerProvider initialization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger("tracing.provider")

_tracer: trace.Tracer | None = None


def init_tracing(settings: "Settings") -> None:
    """Initialize the OTel TracerProvider with configured exporters.

    Call once during application startup (lifespan).
    """
    global _tracer

    resource = Resource.create({
        "service.name": "agent-platform",
        "service.version": "1.0.0",
        "deployment.environment": "development" if settings.debug else "production",
    })
    provider = TracerProvider(resource=resource)

    # OTLP exporter → Grafana Tempo
    if settings.otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP trace exporter configured: %s", settings.otlp_endpoint)
        except Exception as exc:
            logger.warning("OTLP exporter setup failed (install opentelemetry-exporter-otlp-proto-grpc): %s", exc)

    # OTLP HTTP exporter → Langfuse (direct, no SDK dependency)
    if settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            import base64
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHTTPExporter

            langfuse_otlp_url = f"{settings.langfuse_host}/api/public/otel/v1/traces"
            # Langfuse uses Basic auth: public_key:secret_key
            credentials = base64.b64encode(
                f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
            ).decode()
            langfuse_exporter = OTLPHTTPExporter(
                endpoint=langfuse_otlp_url,
                headers={"Authorization": f"Basic {credentials}"},
            )
            provider.add_span_processor(BatchSpanProcessor(langfuse_exporter))
            logger.info("Langfuse OTLP exporter configured: %s", langfuse_otlp_url)
        except Exception as exc:
            logger.warning("Langfuse OTLP exporter setup failed: %s", exc)

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("agent-platform")
    logger.info("OpenTelemetry tracing initialized")


def get_tracer() -> trace.Tracer:
    """Return the platform tracer. Falls back to a no-op tracer if not initialized."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("agent-platform")
    return _tracer


def shutdown_tracing() -> None:
    """Flush and shut down the TracerProvider."""
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.shutdown()
        logger.info("OpenTelemetry tracing shut down")
