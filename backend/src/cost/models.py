"""Cost tracking data models — maps to spec Section 7."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OperationType(str, Enum):
    LLM_CALL = "llm_call"
    LLM_CALL_STREAMING = "llm_call_streaming"
    TOOL_INVOCATION = "tool_invocation"
    A2A_DELEGATION = "a2a_delegation"
    FILE_PROCESSING = "file_processing"
    EMBEDDING = "embedding"
    CACHE_HIT = "cache_hit"
    USER_INTERACTION_WAIT = "user_interaction_wait"


class LLMCostDetail(BaseModel):
    provider: str = "google"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    thinking_tokens: int = 0
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    total_cost_usd: float = 0.0
    latency_ms: int = 0


class ToolCostDetail(BaseModel):
    tool_id: str
    tool_source: str  # "local" | "remote" | "shared"
    endpoint: str | None = None
    invocation_cost_usd: float = 0.0
    data_transfer_bytes: int | None = None
    latency_ms: int = 0


class CostEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    parent_task_id: str | None = None
    trace_id: str = ""
    span_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    module: str
    agent: str
    operation_type: OperationType
    llm: LLMCostDetail | None = None
    tool: ToolCostDetail | None = None
    cumulative_task_cost_usd: float = 0.0


class TaskCostReport(BaseModel):
    task_id: str
    total_cost_usd: float = 0.0
    llm_calls: int = 0
    tool_invocations: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    events: list[CostEvent] = Field(default_factory=list)
