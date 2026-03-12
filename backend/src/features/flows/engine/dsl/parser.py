"""YAML DSL Parser - loads and parses flow definition files."""

from pathlib import Path

import yaml

from src.features.flows.engine.dsl.schema import (
    AgentTaskNode,
    ConditionalNode,
    FlowConfig,
    FlowDefinition,
    FlowNode,
    FlowTrigger,
    HumanInteractionNode,
    LLMDecisionNode,
    ParallelNode,
    TerminalNode,
    TriggerFlowNode,
    WaitForEventNode,
)

NODE_TYPE_MAP: dict[str, type] = {
    "agent_task": AgentTaskNode,
    "llm_decision": LLMDecisionNode,
    "human_interaction": HumanInteractionNode,
    "parallel": ParallelNode,
    "conditional": ConditionalNode,
    "wait_for_event": WaitForEventNode,
    "trigger_flow": TriggerFlowNode,
    "terminal": TerminalNode,
}


class ParsedFlow:
    """A fully parsed flow with typed node objects."""

    def __init__(self, definition: FlowDefinition, nodes: dict[str, FlowNode]):
        self.definition = definition
        self.nodes = nodes
        self.name = definition.name
        self.config = definition.config

    def get_initial_state(self) -> str:
        """Return the first state name (entry point)."""
        return next(iter(self.nodes.keys()))

    def get_node(self, state_name: str) -> FlowNode | None:
        return self.nodes.get(state_name)


class FlowParser:
    """Parses YAML flow definitions into typed FlowNode objects."""

    def parse_file(self, path: str | Path) -> ParsedFlow:
        path = Path(path)
        with open(path) as f:
            raw = yaml.safe_load(f)
        return self.parse_dict(raw)

    def parse_string(self, yaml_string: str) -> ParsedFlow:
        raw = yaml.safe_load(yaml_string)
        return self.parse_dict(raw)

    def parse_dict(self, raw: dict) -> ParsedFlow:
        flow_data = raw.get("flow", raw)

        definition = FlowDefinition(
            name=flow_data["name"],
            version=flow_data.get("version", "1.0.0"),
            description=flow_data.get("description", ""),
            trigger=FlowTrigger(**flow_data.get("trigger", {})),
            config=FlowConfig(**flow_data.get("config", {})),
            states=flow_data.get("states", {}),
        )

        nodes: dict[str, FlowNode] = {}
        for state_name, state_def in definition.states.items():
            node_type = state_def.get("type")
            if node_type not in NODE_TYPE_MAP:
                raise ValueError(
                    f"Unknown node type '{node_type}' in state '{state_name}'"
                )
            model_class = NODE_TYPE_MAP[node_type]
            nodes[state_name] = model_class(**state_def)

        return ParsedFlow(definition=definition, nodes=nodes)
