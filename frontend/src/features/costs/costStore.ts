import { create } from 'zustand';

// --- Detail types mirroring backend CostEvent ---

interface LLMDetail {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  thinking_tokens: number;
  cost_per_input_token: number;
  cost_per_output_token: number;
  total_cost_usd: number;
  latency_ms: number;
}

interface ToolDetail {
  tool_id: string;
  tool_source: string;
  invocation_cost_usd: number;
  latency_ms: number;
}

export interface CostEntry {
  event_id: string;
  task_id: string;
  timestamp: string;
  module: string;
  agent: string;
  operation_type: string;
  llm: LLMDetail | null;
  tool: ToolDetail | null;
  cost_usd: number;
  cumulative_task_cost_usd: number;
}

// --- Granularity ---

export type GranularityLevel = 'total' | 'task' | 'module' | 'agent' | 'event';

// --- Aggregation node ---

export interface CostAggregation {
  key: string;
  label: string;
  totalCost: number;
  eventCount: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalLatencyMs: number;
  llmCalls: number;
  toolInvocations: number;
  children: CostAggregation[] | CostEntry[];
}

// --- Store ---

interface CostStore {
  totalCostUsd: number;
  costByTask: Record<string, number>;
  recentEvents: CostEntry[];
  granularity: GranularityLevel;
  expandedKeys: Record<string, boolean>;
  addCostEvent: (event: CostEntry) => void;
  setGranularity: (level: GranularityLevel) => void;
  toggleExpanded: (key: string) => void;
}

export const useCostStore = create<CostStore>((set) => ({
  totalCostUsd: 0,
  costByTask: {},
  recentEvents: [],
  granularity: 'task',
  expandedKeys: {},

  addCostEvent: (event) =>
    set((state) => ({
      totalCostUsd: state.totalCostUsd + event.cost_usd,
      costByTask: {
        ...state.costByTask,
        [event.task_id]: (state.costByTask[event.task_id] || 0) + event.cost_usd,
      },
      recentEvents: [...state.recentEvents.slice(-99), event],
    })),

  setGranularity: (level) => set({ granularity: level }),

  toggleExpanded: (key) =>
    set((state) => {
      const current = state.expandedKeys[key];
      return {
        expandedKeys: { ...state.expandedKeys, [key]: !current },
      };
    }),
}));

// --- Aggregation helpers ---

function aggregateEntries(entries: CostEntry[]): Omit<CostAggregation, 'key' | 'label' | 'children'> {
  let totalCost = 0;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalLatencyMs = 0;
  let llmCalls = 0;
  let toolInvocations = 0;
  for (const e of entries) {
    totalCost += e.cost_usd;
    if (e.llm) {
      totalInputTokens += e.llm.input_tokens;
      totalOutputTokens += e.llm.output_tokens;
      totalLatencyMs += e.llm.latency_ms;
      llmCalls++;
    }
    if (e.tool) {
      totalLatencyMs += e.tool.latency_ms;
      toolInvocations++;
    }
  }
  return { totalCost, eventCount: entries.length, totalInputTokens, totalOutputTokens, totalLatencyMs, llmCalls, toolInvocations };
}

function aggregateChildren(children: CostAggregation[]): Omit<CostAggregation, 'key' | 'label' | 'children'> {
  let totalCost = 0;
  let eventCount = 0;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalLatencyMs = 0;
  let llmCalls = 0;
  let toolInvocations = 0;
  for (const c of children) {
    totalCost += c.totalCost;
    eventCount += c.eventCount;
    totalInputTokens += c.totalInputTokens;
    totalOutputTokens += c.totalOutputTokens;
    totalLatencyMs += c.totalLatencyMs;
    llmCalls += c.llmCalls;
    toolInvocations += c.toolInvocations;
  }
  return { totalCost, eventCount, totalInputTokens, totalOutputTokens, totalLatencyMs, llmCalls, toolInvocations };
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const key = keyFn(item);
    const arr = map.get(key);
    if (arr) arr.push(item);
    else map.set(key, [item]);
  }
  return map;
}

// --- Aggregation functions (pure, called with useMemo in components) ---

export function aggregateByTask(events: CostEntry[]): CostAggregation[] {
  const byTask = groupBy(events, (e) => e.task_id);
  return Array.from(byTask.entries()).map(([taskId, taskEvents]) => ({
    key: taskId,
    label: taskId,
    ...aggregateEntries(taskEvents),
    children: taskEvents,
  }));
}

export function aggregateByModule(events: CostEntry[]): CostAggregation[] {
  const byTask = groupBy(events, (e) => e.task_id);
  return Array.from(byTask.entries()).map(([taskId, taskEvents]) => {
    const byModule = groupBy(taskEvents, (e) => e.module);
    const moduleChildren: CostAggregation[] = Array.from(byModule.entries()).map(([mod, modEvents]) => ({
      key: `${taskId}::${mod}`,
      label: mod,
      ...aggregateEntries(modEvents),
      children: modEvents,
    }));
    return {
      key: taskId,
      label: taskId,
      ...aggregateChildren(moduleChildren),
      children: moduleChildren,
    };
  });
}

export function aggregateByAgent(events: CostEntry[]): CostAggregation[] {
  const byTask = groupBy(events, (e) => e.task_id);
  return Array.from(byTask.entries()).map(([taskId, taskEvents]) => {
    const byModule = groupBy(taskEvents, (e) => e.module);
    const moduleChildren: CostAggregation[] = Array.from(byModule.entries()).map(([mod, modEvents]) => {
      const byAgent = groupBy(modEvents, (e) => e.agent);
      const agentChildren: CostAggregation[] = Array.from(byAgent.entries()).map(([ag, agEvents]) => ({
        key: `${taskId}::${mod}::${ag}`,
        label: ag,
        ...aggregateEntries(agEvents),
        children: agEvents,
      }));
      return {
        key: `${taskId}::${mod}`,
        label: mod,
        ...aggregateChildren(agentChildren),
        children: agentChildren,
      };
    });
    return {
      key: taskId,
      label: taskId,
      ...aggregateChildren(moduleChildren),
      children: moduleChildren,
    };
  });
}
