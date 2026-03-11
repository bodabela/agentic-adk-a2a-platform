import { create } from 'zustand';

export interface ToolParameter {
  name: string;
  type: string;
  required: boolean;
  default?: unknown;
  description?: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  docstring?: string;
  category: 'mcp' | 'builtin';
  transport?: string;
  server?: string;
  url?: string;
  command?: string;
  parameters: ToolParameter[];
  used_by: string[];
}

interface ToolStore {
  tools: ToolDefinition[];
  selectedTool: ToolDefinition | null;
  loading: boolean;
  summary: { mcp_count: number; builtin_count: number; total: number } | null;
  fetchTools: () => Promise<void>;
  selectTool: (name: string | null) => void;
}

export const useToolStore = create<ToolStore>((set, get) => ({
  tools: [],
  selectedTool: null,
  loading: false,
  summary: null,

  fetchTools: async () => {
    set({ loading: true });
    try {
      const res = await fetch('/api/tools/');
      const data = await res.json();
      set({ tools: data.tools || [], summary: data.summary || null });
    } finally {
      set({ loading: false });
    }
  },

  selectTool: (name) => {
    if (!name) {
      set({ selectedTool: null });
      return;
    }
    const tool = get().tools.find((t) => t.name === name) || null;
    set({ selectedTool: tool });
  },
}));
