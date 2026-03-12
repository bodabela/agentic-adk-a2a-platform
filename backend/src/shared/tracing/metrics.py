"""OpenTelemetry Metrics for the agent platform.

Defines counters and histograms for LLM calls, tool invocations,
task/flow durations. Exposed via Prometheus /metrics endpoint.
"""

from __future__ import annotations

import logging

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("tracing.metrics")

_meter: metrics.Meter | None = None

# Instruments (initialized lazily)
llm_call_duration: metrics.Histogram | None = None
llm_tokens_total: metrics.Counter | None = None
llm_cost_usd_total: metrics.Counter | None = None
tool_call_duration: metrics.Histogram | None = None
tool_call_total: metrics.Counter | None = None
task_duration: metrics.Histogram | None = None
flow_duration: metrics.Histogram | None = None


def init_metrics(prometheus_port: int = 0) -> MeterProvider | None:
    """Initialize OTel MeterProvider with optional Prometheus exporter.

    Args:
        prometheus_port: If > 0, starts a Prometheus HTTP server on this port.
            If 0, uses a PrometheusMetricReader that can be mounted on FastAPI.

    Returns:
        The MeterProvider, or None if Prometheus is not available.
    """
    global _meter, llm_call_duration, llm_tokens_total, llm_cost_usd_total
    global tool_call_duration, tool_call_total, task_duration, flow_duration

    resource = Resource.create({"service.name": "agent-platform"})

    readers = []
    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        prometheus_reader = PrometheusMetricReader()
        readers.append(prometheus_reader)
        logger.info("Prometheus metric reader configured")
    except ImportError:
        logger.warning("opentelemetry-exporter-prometheus not installed — metrics disabled")
        return None

    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)

    _meter = metrics.get_meter("agent-platform")

    # LLM metrics
    llm_call_duration = _meter.create_histogram(
        name="llm.call.duration",
        description="LLM call duration in milliseconds",
        unit="ms",
    )
    llm_tokens_total = _meter.create_counter(
        name="llm.tokens.total",
        description="Total LLM tokens processed",
        unit="tokens",
    )
    llm_cost_usd_total = _meter.create_counter(
        name="llm.cost.usd.total",
        description="Total LLM cost in USD",
        unit="usd",
    )

    # Tool metrics
    tool_call_duration = _meter.create_histogram(
        name="tool.call.duration",
        description="Tool invocation duration in milliseconds",
        unit="ms",
    )
    tool_call_total = _meter.create_counter(
        name="tool.call.total",
        description="Total tool invocations",
    )

    # Task/Flow metrics
    task_duration = _meter.create_histogram(
        name="task.duration",
        description="Task execution duration in milliseconds",
        unit="ms",
    )
    flow_duration = _meter.create_histogram(
        name="flow.duration",
        description="Flow execution duration in milliseconds",
        unit="ms",
    )

    logger.info("OpenTelemetry metrics initialized")
    return provider


def record_llm_metrics(
    model: str, provider: str, agent: str,
    input_tokens: int, output_tokens: int,
    latency_ms: int, cost_usd: float,
) -> None:
    """Record LLM call metrics."""
    labels = {"model": model, "provider": provider, "agent": agent}
    if llm_call_duration:
        llm_call_duration.record(latency_ms, labels)
    if llm_tokens_total:
        llm_tokens_total.add(input_tokens, {**labels, "direction": "input"})
        llm_tokens_total.add(output_tokens, {**labels, "direction": "output"})
    if llm_cost_usd_total and cost_usd > 0:
        llm_cost_usd_total.add(cost_usd, labels)


def record_tool_metrics(
    tool_name: str, agent: str, latency_ms: int, status: str = "ok",
) -> None:
    """Record tool invocation metrics."""
    labels = {"tool_name": tool_name, "agent": agent, "status": status}
    if tool_call_duration:
        tool_call_duration.record(latency_ms, labels)
    if tool_call_total:
        tool_call_total.add(1, labels)


def record_task_duration(task_id: str, duration_ms: int) -> None:
    """Record task execution duration."""
    if task_duration:
        task_duration.record(duration_ms, {"task_id": task_id})


def record_flow_duration(flow_id: str, flow_name: str, duration_ms: int) -> None:
    """Record flow execution duration."""
    if flow_duration:
        flow_duration.record(duration_ms, {"flow_id": flow_id, "flow_name": flow_name})
