"""Pydantic models representing the Flow DSL node types and structure."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    AGENT_TASK = "agent_task"
    LLM_DECISION = "llm_decision"
    HUMAN_INTERACTION = "human_interaction"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    WAIT_FOR_EVENT = "wait_for_event"
    TRIGGER_FLOW = "trigger_flow"
    TERMINAL = "terminal"


class FlowTrigger(BaseModel):
    type: str = "manual"
    input_schema: dict[str, Any] | None = None


class FlowConfig(BaseModel):
    max_retry_loops: int = 5
    max_parallel_branches: int = 4
    timeout_minutes: int = 120

    # LLM provider/model (optional; falls back to llm_providers.yaml defaults)
    provider: str | None = None
    model: str | None = None
    fallback_model: str | None = None

    # Backward compat: mapped to `model` via get_effective_model()
    llm_decision_model: str | None = None

    auto_deploy_policy: dict[str, Any] | None = None
    canary_config: dict[str, Any] | None = None
    rollback_policy: dict[str, Any] | None = None

    def get_effective_model(self) -> str | None:
        """Return model, falling back to legacy llm_decision_model."""
        return self.model or self.llm_decision_model


class SideEffect(BaseModel):
    set: dict[str, str] = Field(default_factory=dict)


# ── Node Types ──────────────────────────────────────────


class AgentTaskNode(BaseModel):
    type: Literal["agent_task"] = "agent_task"
    agent: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    input: dict[str, str] = Field(default_factory=dict)
    output: list[str] = Field(default_factory=list)
    mode: str | None = None
    duration_minutes: str | None = None
    retry_loop: str | None = None
    condition: str | None = None
    side_effect: SideEffect | None = None
    on_complete: str | None = None
    on_error: str | None = None
    on_event: str | None = None


class LLMDecisionNode(BaseModel):
    type: Literal["llm_decision"] = "llm_decision"
    provider: str | None = None
    model: str | None = None
    context: list[str] = Field(default_factory=list)
    decision_prompt: str = ""
    transitions: dict[str, str] = Field(default_factory=dict)
    side_effect: SideEffect | None = None


class HumanInteractionNode(BaseModel):
    type: Literal["human_interaction"] = "human_interaction"
    interaction_type: str = "free_text"
    prompt: str = ""
    context: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    file_upload: dict[str, Any] | None = None
    timeout_seconds: int | None = None
    default_value: str | None = None
    on_response: str | None = None
    on_timeout: str | None = None
    transitions: dict[str, str] = Field(default_factory=dict)


class ParallelBranch(BaseModel):
    type: str
    agent: str = ""
    tools: list[str] = Field(default_factory=list)
    input: dict[str, str] = Field(default_factory=dict)
    output: list[str] = Field(default_factory=list)
    condition: str | None = None


class ParallelNode(BaseModel):
    type: Literal["parallel"] = "parallel"
    branches: dict[str, ParallelBranch] = Field(default_factory=dict)
    join: str = "all"
    on_complete: str | None = None


class ConditionalNode(BaseModel):
    type: Literal["conditional"] = "conditional"
    condition: str = ""
    if_true: str = ""
    if_false: str = ""


class WaitForEventNode(BaseModel):
    type: Literal["wait_for_event"] = "wait_for_event"
    event_source: str = ""
    event_type: str = ""
    timeout_minutes: int = 60
    on_event: str = ""
    on_timeout: str = ""


class TriggerFlowNode(BaseModel):
    type: Literal["trigger_flow"] = "trigger_flow"
    flow_name: str = ""
    input: dict[str, str] = Field(default_factory=dict)
    on_complete: str = ""


class TerminalNode(BaseModel):
    type: Literal["terminal"] = "terminal"
    status: str = "success"
    output: dict[str, str] = Field(default_factory=dict)


# Union of all node types
FlowNode = (
    AgentTaskNode
    | LLMDecisionNode
    | HumanInteractionNode
    | ParallelNode
    | ConditionalNode
    | WaitForEventNode
    | TriggerFlowNode
    | TerminalNode
)


class FlowDefinition(BaseModel):
    """Top-level flow definition parsed from YAML."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    trigger: FlowTrigger = Field(default_factory=FlowTrigger)
    config: FlowConfig = Field(default_factory=FlowConfig)
    states: dict[str, dict[str, Any]]
