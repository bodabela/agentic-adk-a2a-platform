import { create } from 'zustand';

export interface SessionEventPart {
  type: 'text' | 'function_call' | 'function_response';
  text?: string;
  name?: string;
  args?: Record<string, unknown>;
  response?: unknown;
}

export interface SessionEvent {
  author: string;
  timestamp: number | null;
  parts: SessionEventPart[];
}

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
  /** session_id → events (loaded on expand) */
  sessionEvents: Record<string, SessionEvent[]>;
  /** session_id → loading flag */
  eventsLoading: Record<string, boolean>;
  fetchSessions: () => Promise<void>;
  fetchSessionEvents: (sessionId: string) => Promise<void>;
  stopSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  sessions: [],
  loading: false,
  sessionEvents: {},
  eventsLoading: {},

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

  fetchSessionEvents: async (sessionId: string) => {
    set((state) => ({ eventsLoading: { ...state.eventsLoading, [sessionId]: true } }));
    try {
      const res = await fetch(`/api/sessions/${sessionId}/events`);
      const data = await res.json();
      set((state) => ({
        sessionEvents: { ...state.sessionEvents, [sessionId]: data.events || [] },
      }));
    } catch {
      console.error('[Sessions] Failed to fetch events', sessionId);
    } finally {
      set((state) => ({ eventsLoading: { ...state.eventsLoading, [sessionId]: false } }));
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
