import { useEffect, useRef } from 'react';
import { useSessionStore, type SessionInfo } from './sessionStore';

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  running: { bg: '#164e63', color: '#22d3ee', label: 'Running' },
  completed: { bg: '#14532d', color: '#4ade80', label: 'Completed' },
  failed: { bg: '#7f1d1d', color: '#f87171', label: 'Failed' },
  cancelled: { bg: '#78350f', color: '#fbbf24', label: 'Cancelled' },
  suspended: { bg: '#4a1d96', color: '#c084fc', label: 'Suspended' },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.completed;
  return (
    <span
      style={{
        padding: '0.2rem 0.6rem',
        borderRadius: 4,
        fontSize: '0.85rem',
        fontWeight: 600,
        background: style.bg,
        color: style.color,
      }}
    >
      {style.label}
    </span>
  );
}

function formatTime(ts: number | null): string {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 8) + '...' : id;
}

function SessionRow({
  session,
  onStop,
  onDelete,
}: {
  session: SessionInfo;
  onStop: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const isRunning = session.status === 'running';

  return (
    <tr style={{ borderBottom: '1px solid #334155' }}>
      <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontFamily: 'monospace', fontSize: '0.9rem' }}>
        {shortId(session.session_id)}
      </td>
      <td style={{ padding: '0.75rem 1rem' }}>
        <StatusBadge status={session.status} />
      </td>
      <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1', fontSize: '0.9rem' }}>
        {session.event_count}
      </td>
      <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontSize: '0.85rem' }}>
        {formatTime(session.create_time)}
      </td>
      <td style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontSize: '0.85rem' }}>
        {formatTime(session.update_time)}
      </td>
      <td style={{ padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {isRunning && (
            <button
              onClick={() => onStop(session.session_id)}
              style={{
                padding: '0.3rem 0.75rem',
                background: '#7f1d1d',
                color: '#f87171',
                border: '1px solid #991b1b',
                borderRadius: 4,
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              Stop
            </button>
          )}
          {!isRunning && (
            <button
              onClick={() => onDelete(session.session_id)}
              style={{
                padding: '0.3rem 0.75rem',
                background: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #475569',
                borderRadius: 4,
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              Delete
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function SessionsPage() {
  const sessions = useSessionStore((s) => s.sessions);
  const loading = useSessionStore((s) => s.loading);
  const fetchSessions = useSessionStore((s) => s.fetchSessions);
  const stopSession = useSessionStore((s) => s.stopSession);
  const deleteSession = useSessionStore((s) => s.deleteSession);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchSessions();
    intervalRef.current = setInterval(fetchSessions, 10_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchSessions]);

  const runningCount = sessions.filter((s) => s.status === 'running').length;
  const completedCount = sessions.filter((s) => s.status !== 'running').length;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', margin: 0 }}>
            ADK Sessions
          </h2>
          <span style={{ color: '#64748b', fontSize: '0.9rem' }}>
            {runningCount} running, {completedCount} completed — SQLite persistent storage
          </span>
        </div>
        <button
          onClick={fetchSessions}
          disabled={loading}
          style={{
            padding: '0.5rem 1rem',
            background: '#1e293b',
            color: '#94a3b8',
            border: '1px solid #475569',
            borderRadius: 6,
            cursor: loading ? 'wait' : 'pointer',
            fontSize: '0.9rem',
          }}
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {sessions.length === 0 ? (
        <div
          style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '3rem',
            textAlign: 'center',
            color: '#64748b',
            fontSize: '1rem',
          }}
        >
          No sessions yet. Start a task or flow to create one.
        </div>
      ) : (
        <div
          style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #475569' }}>
                {['Session ID', 'Status', 'Events', 'Created', 'Last Update', 'Actions'].map(
                  (h) => (
                    <th
                      key={h}
                      style={{
                        padding: '0.75rem 1rem',
                        textAlign: 'left',
                        color: '#64748b',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <SessionRow
                  key={s.session_id}
                  session={s}
                  onStop={stopSession}
                  onDelete={deleteSession}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
