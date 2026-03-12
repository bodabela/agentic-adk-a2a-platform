"""Cost Tracker - records and aggregates cost events."""

from __future__ import annotations

from src.shared.cost.models import CostEvent, TaskCostReport, OperationType, LLMCostDetail, ToolCostDetail
from src.shared.events.bus import EventBus
from src.shared.tracing.context import get_current_trace_ids

# Optional: import only for type checking
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.shared.llm.config import LLMProvidersConfig


class CostTracker:
    def __init__(self, event_bus: EventBus, llm_config: LLMProvidersConfig | None = None):
        self._event_bus = event_bus
        self._llm_config = llm_config
        self._task_reports: dict[str, TaskCostReport] = {}

    def get_or_create_report(self, task_id: str) -> TaskCostReport:
        if task_id not in self._task_reports:
            self._task_reports[task_id] = TaskCostReport(task_id=task_id)
        return self._task_reports[task_id]

    async def record_llm_call(
        self,
        task_id: str,
        module: str,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        provider: str = "google",
    ) -> CostEvent:
        # Look up pricing from config instead of hardcoded dict
        if self._llm_config:
            pricing_info = self._llm_config.get_pricing(provider, model)
            pricing = {
                "input": pricing_info.input_per_token,
                "output": pricing_info.output_per_token,
            }
        else:
            pricing = {"input": 0.0, "output": 0.0}

        total_cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        report = self.get_or_create_report(task_id)
        report.total_cost_usd += total_cost
        report.llm_calls += 1
        report.total_input_tokens += input_tokens
        report.total_output_tokens += output_tokens

        trace_id, span_id = get_current_trace_ids()

        event = CostEvent(
            task_id=task_id,
            module=module,
            agent=agent,
            operation_type=OperationType.LLM_CALL,
            trace_id=trace_id,
            span_id=span_id,
            llm=LLMCostDetail(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_per_input_token=pricing["input"],
                cost_per_output_token=pricing["output"],
                total_cost_usd=total_cost,
                latency_ms=latency_ms,
            ),
            cumulative_task_cost_usd=report.total_cost_usd,
        )
        report.events.append(event)

        await self._event_bus.emit("cost_event", event.model_dump(mode="json"))
        return event

    async def record_tool_invocation(
        self,
        task_id: str,
        module: str,
        agent: str,
        tool_id: str,
        tool_source: str,
        latency_ms: int,
    ) -> CostEvent:
        report = self.get_or_create_report(task_id)
        report.tool_invocations += 1

        trace_id, span_id = get_current_trace_ids()

        event = CostEvent(
            task_id=task_id,
            module=module,
            agent=agent,
            operation_type=OperationType.TOOL_INVOCATION,
            trace_id=trace_id,
            span_id=span_id,
            tool=ToolCostDetail(
                tool_id=tool_id,
                tool_source=tool_source,
                latency_ms=latency_ms,
            ),
            cumulative_task_cost_usd=report.total_cost_usd,
        )
        report.events.append(event)
        await self._event_bus.emit("cost_event", event.model_dump(mode="json"))
        return event

    def get_report(self, task_id: str) -> TaskCostReport | None:
        return self._task_reports.get(task_id)
