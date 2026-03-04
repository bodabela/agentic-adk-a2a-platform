"""Tests for the Cost Tracker."""

import pytest

from src.cost.tracker import CostTracker
from src.cost.models import OperationType
from src.events.bus import EventBus
from src.llm.config import LLMProvidersConfig, ProviderConfig, ModelConfig, ModelPricing


def _test_llm_config() -> LLMProvidersConfig:
    return LLMProvidersConfig(
        providers={
            "google": ProviderConfig(
                display_name="Google Gemini",
                api_key_env="GOOGLE_API_KEY",
                models={
                    "gemini-2.0-flash": ModelConfig(
                        display_name="Gemini 2.0 Flash",
                        pricing=ModelPricing(
                            input_per_token=0.0000001,
                            output_per_token=0.0000004,
                        ),
                    ),
                },
            ),
        },
    )


class TestCostTracker:
    @pytest.fixture
    def tracker(self):
        bus = EventBus()
        return CostTracker(bus, llm_config=_test_llm_config())

    @pytest.mark.asyncio
    async def test_record_llm_call(self, tracker):
        event = await tracker.record_llm_call(
            task_id="task-1",
            module="coder_agent",
            agent="coder",
            model="gemini-2.0-flash",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=1200,
        )
        assert event.operation_type == OperationType.LLM_CALL
        assert event.llm.input_tokens == 1000
        assert event.llm.output_tokens == 500
        assert event.llm.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_cumulative_cost(self, tracker):
        await tracker.record_llm_call(
            task_id="task-1",
            module="test",
            agent="test",
            model="gemini-2.0-flash",
            input_tokens=1000,
            output_tokens=500,
            latency_ms=100,
        )
        event2 = await tracker.record_llm_call(
            task_id="task-1",
            module="test",
            agent="test",
            model="gemini-2.0-flash",
            input_tokens=2000,
            output_tokens=1000,
            latency_ms=200,
        )
        report = tracker.get_report("task-1")
        assert report.llm_calls == 2
        assert report.total_input_tokens == 3000
        assert event2.cumulative_task_cost_usd == report.total_cost_usd

    @pytest.mark.asyncio
    async def test_record_tool_invocation(self, tracker):
        event = await tracker.record_tool_invocation(
            task_id="task-1",
            module="coder_agent",
            agent="coder",
            tool_id="code_generator",
            tool_source="local",
            latency_ms=50,
        )
        assert event.operation_type == OperationType.TOOL_INVOCATION
        report = tracker.get_report("task-1")
        assert report.tool_invocations == 1

    def test_nonexistent_report(self, tracker):
        assert tracker.get_report("nonexistent") is None
