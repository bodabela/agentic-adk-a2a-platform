import { create } from 'zustand';

export interface AgentDefinition {
  name: string;
  version: string;
  description: string;
  category: string;
  model: string;
  model_fallback: string | null;
  capabilities: string[];
  tools: {
    mcp: Array<{ transport: string; server?: string; workspace?: string }>;
    builtin: string[];
  };
}

export interface AgentDetail {
  name: string;
  yaml_content: string;
  prompt_content: string;
  definition: AgentDefinition | null;
}

interface AgentStore {
  agents: AgentDefinition[];
  selectedAgent: AgentDetail | null;
  loading: boolean;
  fetchAgents: () => Promise<void>;
  fetchAgentDetail: (name: string) => Promise<void>;
  createAgent: (name: string, yamlContent: string, promptContent?: string) => Promise<void>;
  updateAgent: (name: string, yamlContent?: string, promptContent?: string) => Promise<void>;
  deleteAgent: (name: string) => Promise<void>;
  clearSelection: () => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents: [],
  selectedAgent: null,
  loading: false,

  fetchAgents: async () => {
    set({ loading: true });
    try {
      const res = await fetch('/api/agents/');
      const data = await res.json();
      set({ agents: data.agents || [] });
    } finally {
      set({ loading: false });
    }
  },

  fetchAgentDetail: async (name: string) => {
    const res = await fetch(`/api/agents/${name}`);
    if (!res.ok) return;
    const data = await res.json();
    set({ selectedAgent: data });
  },

  createAgent: async (name, yamlContent, promptContent) => {
    const res = await fetch('/api/agents/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, yaml_content: yamlContent, prompt_content: promptContent }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create agent');
    }
    // Refresh list
    const listRes = await fetch('/api/agents/');
    const listData = await listRes.json();
    set({ agents: listData.agents || [] });
  },

  updateAgent: async (name, yamlContent, promptContent) => {
    const res = await fetch(`/api/agents/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml_content: yamlContent, prompt_content: promptContent }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update agent');
    }
    // Refresh list and detail
    const listRes = await fetch('/api/agents/');
    const listData = await listRes.json();
    set({ agents: listData.agents || [] });

    const detailRes = await fetch(`/api/agents/${name}`);
    if (detailRes.ok) {
      const detailData = await detailRes.json();
      set({ selectedAgent: detailData });
    }
  },

  deleteAgent: async (name) => {
    const res = await fetch(`/api/agents/${name}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete agent');
    }
    set((state) => ({
      agents: state.agents.filter((a) => a.name !== name),
      selectedAgent: state.selectedAgent?.name === name ? null : state.selectedAgent,
    }));
  },

  clearSelection: () => set({ selectedAgent: null }),
}));
