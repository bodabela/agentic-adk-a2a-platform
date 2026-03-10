import { create } from 'zustand';

export interface RootAgentDefinition {
  name: string;
  version: string;
  description: string;
  model: string;
  max_iterations: number;
  sub_agents: string[];
}

export interface RootAgentInstance {
  instance_id: string;
  definition_name: string;
  status: string;
  started_at: string;
  task_ids: string[];
}

export interface RootAgentDetail {
  name: string;
  yaml_content: string;
  definition: RootAgentDefinition | null;
}

interface RootAgentStore {
  definitions: RootAgentDefinition[];
  instances: RootAgentInstance[];
  selectedDefinition: RootAgentDetail | null;
  loading: boolean;
  fetchDefinitions: () => Promise<void>;
  fetchDefinitionDetail: (name: string) => Promise<void>;
  createDefinition: (name: string, yamlContent: string) => Promise<void>;
  updateDefinition: (name: string, yamlContent: string) => Promise<void>;
  deleteDefinition: (name: string) => Promise<void>;
  fetchInstances: () => Promise<void>;
  startInstance: (definitionName: string) => Promise<void>;
  stopInstance: (instanceId: string) => Promise<void>;
  clearSelection: () => void;
}

export const useRootAgentStore = create<RootAgentStore>((set) => ({
  definitions: [],
  instances: [],
  selectedDefinition: null,
  loading: false,

  fetchDefinitions: async () => {
    set({ loading: true });
    try {
      const res = await fetch('/api/root-agents/definitions');
      const data = await res.json();
      set({ definitions: data.definitions || [] });
    } finally {
      set({ loading: false });
    }
  },

  fetchDefinitionDetail: async (name: string) => {
    const res = await fetch(`/api/root-agents/definitions/${name}`);
    if (!res.ok) return;
    const data = await res.json();
    set({ selectedDefinition: data });
  },

  createDefinition: async (name, yamlContent) => {
    const res = await fetch('/api/root-agents/definitions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, yaml_content: yamlContent }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create root agent');
    }
    const listRes = await fetch('/api/root-agents/definitions');
    const listData = await listRes.json();
    set({ definitions: listData.definitions || [] });
  },

  updateDefinition: async (name, yamlContent) => {
    const res = await fetch(`/api/root-agents/definitions/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml_content: yamlContent }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update root agent');
    }
    const listRes = await fetch('/api/root-agents/definitions');
    const listData = await listRes.json();
    set({ definitions: listData.definitions || [] });
  },

  deleteDefinition: async (name) => {
    const res = await fetch(`/api/root-agents/definitions/${name}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete root agent');
    }
    set((state) => ({
      definitions: state.definitions.filter((d) => d.name !== name),
      selectedDefinition: state.selectedDefinition?.name === name ? null : state.selectedDefinition,
    }));
  },

  fetchInstances: async () => {
    const res = await fetch('/api/root-agents/instances');
    const data = await res.json();
    set({ instances: data.instances || [] });
  },

  startInstance: async (definitionName) => {
    const res = await fetch('/api/root-agents/instances', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ definition_name: definitionName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start instance');
    }
    // Refresh instances
    const listRes = await fetch('/api/root-agents/instances');
    const listData = await listRes.json();
    set({ instances: listData.instances || [] });
  },

  stopInstance: async (instanceId) => {
    await fetch(`/api/root-agents/instances/${instanceId}`, { method: 'DELETE' });
    set((state) => ({
      instances: state.instances.filter((i) => i.instance_id !== instanceId),
    }));
  },

  clearSelection: () => set({ selectedDefinition: null }),
}));
