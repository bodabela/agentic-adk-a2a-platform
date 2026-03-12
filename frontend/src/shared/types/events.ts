export interface TaskEvent {
  type: string;
  task_id: string;
  event_type?: string;
  timestamp?: string;
  data?: unknown;
}

export interface FlowEvent {
  type: string;
  flow_id: string;
  state?: string;
  node_type?: string;
  decision?: string;
  next_state?: string;
  interaction_id?: string;
  interaction_type?: string;
  prompt?: string;
  options?: { id: string; label: string; recommended?: boolean }[];
  status?: string;
  output?: Record<string, unknown>;
}

export interface CostEvent {
  type: string;
  event_id: string;
  task_id: string;
  module: string;
  agent: string;
  operation_type: string;
  cumulative_task_cost_usd: number;
  llm?: {
    model: string;
    input_tokens: number;
    output_tokens: number;
    total_cost_usd: number;
    latency_ms: number;
  };
  tool?: {
    tool_id: string;
    tool_source: string;
    latency_ms: number;
  };
}
