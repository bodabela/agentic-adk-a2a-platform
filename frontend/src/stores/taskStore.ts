import { create } from 'zustand';

interface TaskEvent {
  event_type: string;
  timestamp: string;
  data: unknown;
}

interface Task {
  task_id: string;
  status: string;
  description: string;
  events: TaskEvent[];
  cost_usd: number;
  error?: string;
}

interface InteractionOption {
  id: string;
  label: string;
  recommended?: boolean;
}

export interface TaskPendingInteraction {
  interaction_id: string;
  task_id: string;
  interaction_type: string;
  prompt: string;
  options?: InteractionOption[];
}

interface TaskStore {
  tasks: Record<string, Task>;
  activeTaskId: string | null;
  pendingInteractions: TaskPendingInteraction[];
  submitTask: (description: string) => Promise<string>;
  addEvent: (taskId: string, event: TaskEvent) => void;
  appendStreamingText: (taskId: string, text: string, agent: string, isThought: boolean, model?: string) => void;
  setActiveTask: (taskId: string | null) => void;
  updateTaskStatus: (taskId: string, status: string, error?: string) => void;
  addInteraction: (interaction: TaskPendingInteraction) => void;
  resolveInteraction: (interactionId: string) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: {},
  activeTaskId: null,
  pendingInteractions: [],

  submitTask: async (description: string) => {
    const res = await fetch('/api/tasks/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description }),
    });
    const data = await res.json();
    set((state) => ({
      tasks: {
        ...state.tasks,
        [data.task_id]: {
          task_id: data.task_id,
          status: data.status,
          description,
          events: [],
          cost_usd: 0,
        },
      },
      activeTaskId: data.task_id,
    }));
    return data.task_id;
  },

  addEvent: (taskId, event) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;
      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...task, events: [...task.events, event] },
        },
      };
    }),

  appendStreamingText: (taskId, text, agent, isThought, model) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;
      const events = [...task.events];
      const last = events[events.length - 1];
      if (last && last.event_type === 'streaming_text') {
        const lastData = last.data as Record<string, unknown>;
        events[events.length - 1] = {
          ...last,
          data: { ...lastData, text: (lastData.text as string) + text },
        };
      } else {
        events.push({
          event_type: 'streaming_text',
          timestamp: new Date().toISOString(),
          data: { agent, text, is_thought: isThought, model: model || '' },
        });
      }
      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...task, events },
        },
      };
    }),

  setActiveTask: (taskId) => set({ activeTaskId: taskId }),

  updateTaskStatus: (taskId, status, error?) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;
      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...task, status, ...(error !== undefined && { error }) },
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
}));
