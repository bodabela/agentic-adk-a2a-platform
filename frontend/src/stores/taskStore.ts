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

interface TaskStore {
  tasks: Record<string, Task>;
  activeTaskId: string | null;
  submitTask: (description: string) => Promise<string>;
  addEvent: (taskId: string, event: TaskEvent) => void;
  setActiveTask: (taskId: string | null) => void;
  updateTaskStatus: (taskId: string, status: string, error?: string) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: {},
  activeTaskId: null,

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
}));
