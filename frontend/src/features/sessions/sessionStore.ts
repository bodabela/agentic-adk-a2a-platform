import { create } from 'zustand';

export interface SessionInfo {
  session_id: string;
  app_name: string;
  user_id: string;
  status: string;
  create_time: number | null;
  update_time: number | null;
  event_count: number;
}

interface SessionStore {
  sessions: SessionInfo[];
  loading: boolean;
  fetchSessions: () => Promise<void>;
  stopSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  sessions: [],
  loading: false,

  fetchSessions: async () => {
    set({ loading: true });
    try {
      const res = await fetch('/api/sessions/');
      const data = await res.json();
      set({ sessions: data.sessions || [] });
    } catch {
      console.error('[Sessions] Failed to fetch');
    } finally {
      set({ loading: false });
    }
  },

  stopSession: async (sessionId: string) => {
    try {
      await fetch(`/api/sessions/${sessionId}/stop`, { method: 'POST' });
      // Refresh after short delay to let the cancel propagate
      setTimeout(() => get().fetchSessions(), 500);
    } catch {
      console.error('[Sessions] Failed to stop', sessionId);
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      set((state) => ({
        sessions: state.sessions.filter((s) => s.session_id !== sessionId),
      }));
    } catch {
      console.error('[Sessions] Failed to delete', sessionId);
    }
  },
}));
