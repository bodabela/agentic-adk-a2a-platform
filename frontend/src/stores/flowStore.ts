import { create } from 'zustand';

export interface FlowEvent {
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

interface FlowState {
  flowId: string;
  flowName: string;
  currentState: string;
  status: string;
  states: Record<string, { status: string; output?: unknown }>;
  output?: Record<string, unknown>;
  events: FlowEvent[];
}

interface InteractionOption {
  id: string;
  label: string;
  recommended?: boolean;
}

export interface InteractionQuestion {
  id: string;
  text: string;
  question_type: 'free_text' | 'choice';
  options?: InteractionOption[];
  required?: boolean;
}

interface PendingInteraction {
  interaction_id: string;
  flow_id: string;
  interaction_type: string;
  prompt: string;
  options?: InteractionOption[];
  questions?: InteractionQuestion[];
}

interface FlowStore {
  activeFlows: Record<string, FlowState>;
  pendingInteractions: PendingInteraction[];
  updateFlowState: (flowId: string, update: Partial<FlowState>) => void;
  addFlowEvent: (flowId: string, event: FlowEvent) => void;
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

  addFlowEvent: (flowId, event) =>
    set((state) => {
      const flow = state.activeFlows[flowId];
      if (!flow) return state;
      return {
        activeFlows: {
          ...state.activeFlows,
          [flowId]: { ...flow, events: [...flow.events, event] },
        },
      };
    }),

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
