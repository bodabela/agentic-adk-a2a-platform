"""Tests for the Flow DSL parser and validator."""

import pytest

from src.features.flows.engine.dsl.parser import FlowParser
from src.features.flows.engine.dsl.validator import FlowValidator
from src.features.flows.engine.dsl.schema import (
    AgentTaskNode,
    LLMDecisionNode,
    HumanInteractionNode,
    TerminalNode,
)


@pytest.fixture
def parser():
    return FlowParser()


@pytest.fixture
def validator():
    return FlowValidator()


class TestFlowParser:
    def test_parse_simple_flow_file(self, parser, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        assert flow.name == "simple_code_task"
        assert len(flow.nodes) == 5

    def test_parse_flow_states(self, parser, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        assert isinstance(flow.get_node("generate_code"), AgentTaskNode)
        assert isinstance(flow.get_node("review_result"), LLMDecisionNode)
        assert isinstance(flow.get_node("ask_user_input"), HumanInteractionNode)
        assert isinstance(flow.get_node("handle_error"), TerminalNode)
        assert isinstance(flow.get_node("complete_success"), TerminalNode)

    def test_initial_state(self, parser, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        assert flow.get_initial_state() == "generate_code"

    def test_agent_task_node_fields(self, parser, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        node = flow.get_node("generate_code")
        assert node.agent == "coder_agent"
        assert node.on_complete == "review_result"
        assert node.on_error == "handle_error"
        assert "requirement" in node.input

    def test_llm_decision_transitions(self, parser, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        node = flow.get_node("review_result")
        assert "accept" in node.transitions
        assert "revise" in node.transitions
        assert "ask_user" in node.transitions

    def test_parse_string(self, parser):
        yaml_str = """
flow:
  name: "test_flow"
  states:
    start:
      type: "agent_task"
      agent: "test_agent"
      on_complete: "done"
    done:
      type: "terminal"
      status: "success"
"""
        flow = parser.parse_string(yaml_str)
        assert flow.name == "test_flow"
        assert len(flow.nodes) == 2

    def test_unknown_node_type_raises(self, parser):
        yaml_str = """
flow:
  name: "bad_flow"
  states:
    start:
      type: "nonexistent_type"
"""
        with pytest.raises(ValueError, match="Unknown node type"):
            parser.parse_string(yaml_str)


class TestFlowValidator:
    def test_validate_simple_flow(self, parser, validator, flows_dir):
        flow = parser.parse_file(flows_dir / "simple_code_task.flow.yaml")
        errors = validator.validate(flow)
        assert len(errors) == 0

    def test_detect_missing_transition_target(self, parser, validator):
        yaml_str = """
flow:
  name: "bad_flow"
  states:
    start:
      type: "agent_task"
      agent: "test"
      on_complete: "nonexistent_state"
    done:
      type: "terminal"
"""
        flow = parser.parse_string(yaml_str)
        errors = validator.validate(flow)
        error_msgs = [e.message for e in errors if e.severity == "error"]
        assert any("nonexistent_state" in m for m in error_msgs)

    def test_detect_unreachable_state(self, parser, validator):
        yaml_str = """
flow:
  name: "unreachable"
  states:
    start:
      type: "agent_task"
      agent: "test"
      on_complete: "done"
    done:
      type: "terminal"
    orphan:
      type: "terminal"
      status: "failed"
"""
        flow = parser.parse_string(yaml_str)
        errors = validator.validate(flow)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("orphan" in e.state for e in warnings)

    def test_no_terminal_warning(self, parser, validator):
        yaml_str = """
flow:
  name: "no_terminal"
  states:
    start:
      type: "agent_task"
      agent: "test"
      on_complete: "start"
"""
        flow = parser.parse_string(yaml_str)
        errors = validator.validate(flow)
        warnings = [e for e in errors if e.severity == "warning"]
        assert any("terminal" in e.message.lower() for e in warnings)
