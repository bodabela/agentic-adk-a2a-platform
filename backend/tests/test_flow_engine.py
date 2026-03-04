"""Tests for the Flow Engine."""

import pytest
import asyncio

from src.flow_engine.context import FlowContext
from src.flow_engine.retry_manager import RetryManager, RetryLimitExceeded
from src.flow_engine.dsl.schema import FlowConfig
from src.flow_engine.dsl.parser import FlowParser
from src.flow_engine.engine import FlowEngine
from src.events.bus import EventBus
from src.cost.tracker import CostTracker
from src.llm.config import LLMProvidersConfig


class TestFlowContext:
    def test_trigger_resolution(self):
        ctx = FlowContext(trigger_input={"name": "test_app"})
        assert ctx.resolve("{{ trigger.name }}") == "test_app"

    def test_state_output_resolution(self):
        ctx = FlowContext()
        ctx.set_state_output("step1", {"result": "hello", "count": 42})
        assert ctx.resolve("{{ states.step1.output.result }}") == "hello"
        assert ctx.resolve("{{ states.step1.output.count }}") == 42

    def test_flow_var_resolution(self):
        ctx = FlowContext()
        ctx.set_flow_var("flow.current_phase", "operate")
        assert ctx.resolve("{{ flow.current_phase }}") == "operate"

    def test_retry_count_resolution(self):
        ctx = FlowContext()
        ctx.increment_retry("build_loop")
        ctx.increment_retry("build_loop")
        assert ctx.resolve("{{ flow.retry_count.build_loop }}") == 2

    def test_history_resolution(self):
        ctx = FlowContext()
        ctx.set_state_output("fix", {"v": 1})
        ctx.set_state_output("fix", {"v": 2})
        history = ctx.resolve("{{ flow.history.fix }}")
        assert len(history) == 2

    def test_default_filter(self):
        ctx = FlowContext()
        result = ctx.resolve("{{ states.missing.output.x | default('fallback') }}")
        assert result == "fallback"

    def test_comparison_expression(self):
        ctx = FlowContext()
        ctx.set_flow_var("flow.current_phase", "operate")
        assert ctx.resolve("{{ flow.current_phase == 'operate' }}") is True
        assert ctx.resolve("{{ flow.current_phase == 'build' }}") is False

    def test_inline_template(self):
        ctx = FlowContext(trigger_input={"name": "API"})
        result = ctx.resolve("Building {{ trigger.name }} now")
        assert result == "Building API now"

    def test_resolve_dict(self):
        ctx = FlowContext(trigger_input={"task": "build"})
        resolved = ctx.resolve_dict({
            "a": "{{ trigger.task }}",
            "b": "static_value",
        })
        assert resolved["a"] == "build"
        assert resolved["b"] == "static_value"

    def test_non_template_passthrough(self):
        ctx = FlowContext()
        assert ctx.resolve("plain text") == "plain text"
        assert ctx.resolve(42) == 42


class TestRetryManager:
    def test_increment_within_limit(self):
        config = FlowConfig(max_retry_loops=3)
        mgr = RetryManager(config)
        ctx = FlowContext()
        assert mgr.check_and_increment(ctx, "loop1") == 1
        assert mgr.check_and_increment(ctx, "loop1") == 2
        assert mgr.check_and_increment(ctx, "loop1") == 3

    def test_exceed_limit_raises(self):
        config = FlowConfig(max_retry_loops=2)
        mgr = RetryManager(config)
        ctx = FlowContext()
        mgr.check_and_increment(ctx, "loop1")
        mgr.check_and_increment(ctx, "loop1")
        with pytest.raises(RetryLimitExceeded):
            mgr.check_and_increment(ctx, "loop1")


class TestFlowEngine:
    @pytest.fixture
    def engine(self):
        bus = EventBus()
        llm_config = LLMProvidersConfig()
        tracker = CostTracker(bus, llm_config=llm_config)
        return FlowEngine(event_bus=bus, cost_tracker=tracker, llm_config=llm_config)

    @pytest.mark.asyncio
    async def test_execute_simple_flow(self, engine, flows_dir):
        parser = FlowParser()
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")

        result = await engine.execute_flow(
            flow,
            trigger_input={"task_description": "Build a hello world app"},
        )

        assert result["status"] == "completed"
        assert "flow_id" in result

    @pytest.mark.asyncio
    async def test_execute_inline_flow(self, engine):
        parser = FlowParser()
        flow = parser.parse_string("""
flow:
  name: "inline_test"
  states:
    start:
      type: "agent_task"
      agent: "test_agent"
      input:
        task: "{{ trigger.desc }}"
      on_complete: "done"
    done:
      type: "terminal"
      status: "success"
      output:
        msg: "{{ states.start.output.result }}"
""")
        result = await engine.execute_flow(
            flow,
            trigger_input={"desc": "test task"},
        )
        assert result["status"] == "completed"
