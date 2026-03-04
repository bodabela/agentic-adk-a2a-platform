import { create } from 'zustand';

interface FlowState {
  flowId: string;
  flowName: string;
  currentState: string;
  status: string;
  states: Record<string, { status: string; output?: unknown }>;
}

interface PendingInteraction {
  interaction_id: string;
  flow_id: string;
  interaction_type: string;
  prompt: string;
  options?: { id: string; label: string; recommended?: boolean }[];
}

interface FlowStore {
  activeFlows: Record<string, FlowState>;
  pendingInteractions: PendingInteraction[];
  updateFlowState: (flowId: string, update: Partial<FlowState>) => void;
  addInteraction: (interaction: PendingInteraction) => void;
  resolveInteraction: (interactionId: string) => void;
  startFlow: (flowFile: string, input: Record<string, unknown>, provider?: string, model?: string) => Promise<void>;
}

export const useFlowStore = create<FlowStore>((set) => ({
  activeFlows: {},
  pendingInteractions: [],

  updateFlowState: (flowId, update) =>
    set((state) => ({
      activeFlows: {
        ...state.activeFlows,
        [flowId]: { ...state.activeFlows[flowId], ...update } as FlowState,
      },
    })),

  addInteraction: (interaction) =>
    set((state) => ({
      pendingInteractions: [...state.pendingInteractions, interaction],
    })),

  resolveInteraction: (interactionId) =>
    set((state) => ({
      pendingInteractions: state.pendingInteractions.filter(
        (i) => i.interaction_id !== interactionId,
      ),
    })),

  startFlow: async (flowFile, input, provider?, model?) => {
    await fetch('/api/flows/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flow_file: flowFile, input, provider, model }),
    });
  },
}));
