import { create } from 'zustand';

interface CostEntry {
  task_id: string;
  module: string;
  agent: string;
  operation_type: string;
  cost_usd: number;
  timestamp: string;
}

interface CostStore {
  totalCostUsd: number;
  costByTask: Record<string, number>;
  recentEvents: CostEntry[];
  addCostEvent: (event: CostEntry) => void;
}

export const useCostStore = create<CostStore>((set) => ({
  totalCostUsd: 0,
  costByTask: {},
  recentEvents: [],

  addCostEvent: (event) =>
    set((state) => ({
      totalCostUsd: state.totalCostUsd + event.cost_usd,
      costByTask: {
        ...state.costByTask,
        [event.task_id]: (state.costByTask[event.task_id] || 0) + event.cost_usd,
      },
      recentEvents: [...state.recentEvents.slice(-99), event],
    })),
}));
