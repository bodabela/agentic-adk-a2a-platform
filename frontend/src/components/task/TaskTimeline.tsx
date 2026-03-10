import { useEffect, useRef, useState } from 'react';
import { useTaskStore } from '../../stores/taskStore';

type TaskEvent = { event_type: string; timestamp: string; data: unknown };

/** Format a single history entry for display. */
function formatHistoryEntry(entry: Record<string, unknown>): { label: string; color: string; text: string } {
  if (entry.tool_call) {
    return {
      label: `${entry.author || '?'} -> ${entry.tool_call}`,
      color: '#fbbf24',
      text: JSON.stringify(entry.args || {}, null, 2),
    };
  }
  if (entry.tool_result) {
    return {
      label: `${entry.tool_result} result`,
      color: '#34d399',
      text: String(entry.response || ''),
    };
  }
  return {
    label: String(entry.author || 'message'),
    color: entry.author === 'user' ? '#60a5fa' : '#e2e8f0',
    text: String(entry.text || ''),
  };
}

/** Centered modal popup for transfer_to_agent context data. */
function TransferContextPopup({ context }: { context: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const state = context.state as Record<string, unknown> | undefined;
  const history = context.history as Record<string, unknown>[] | undefined;

  return (
    <>
      <span
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        style={{
          fontSize: '0.95rem',
          padding: '0.15rem 0.5rem',
          borderRadius: 4,
          background: '#1e3a5f',
          color: '#60a5fa',
          marginLeft: '0.5rem',
          cursor: 'pointer',
          fontWeight: 600,
        }}
      >
        context
      </span>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#0f172a',
              border: '1px solid #475569',
              borderRadius: 10,
              padding: '1.5rem',
              width: '70vw',
              maxWidth: 800,
              maxHeight: '75vh',
              overflowY: 'auto',
              boxShadow: '0 12px 48px rgba(0,0,0,0.8)',
              color: '#e2e8f0',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#60a5fa' }}>
                Transfer Context
              </span>
              <button
                onClick={() => setOpen(false)}
                style={{
                  background: 'none',
                  border: '1px solid #475569',
                  borderRadius: 6,
                  color: '#94a3b8',
                  fontSize: '1.1rem',
                  padding: '0.25rem 0.75rem',
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
            </div>

            {/* Session State */}
            {state && Object.keys(state).length > 0 && (
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ color: '#fbbf24', fontWeight: 700, fontSize: '1.1rem', marginBottom: '0.5rem', borderBottom: '1px solid #334155', paddingBottom: '0.35rem' }}>
                  Session State
                </div>
                {Object.entries(state).map(([key, val]) => (
                  <div key={key} style={{ marginBottom: '0.6rem', fontSize: '1.05rem', lineHeight: 1.5 }}>
                    <span style={{ color: '#a78bfa', fontWeight: 700 }}>{key}: </span>
                    <span style={{ color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {typeof val === 'string' ? val : JSON.stringify(val, null, 2)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Conversation History */}
            {history && history.length > 0 && (
              <div>
                <div style={{ color: '#22d3ee', fontWeight: 700, fontSize: '1.1rem', marginBottom: '0.5rem', borderBottom: '1px solid #334155', paddingBottom: '0.35rem' }}>
                  Conversation History ({history.length} events)
                </div>
                {history.map((entry, i) => {
                  const { label, color, text } = formatHistoryEntry(entry);
                  return (
                    <div key={i} style={{ marginBottom: '0.5rem', paddingLeft: '0.75rem', borderLeft: `3px solid ${color}` }}>
                      <div style={{ color, fontWeight: 700, fontSize: '1rem' }}>{label}</div>
                      {text && (
                        <div style={{ color: '#cbd5e1', fontSize: '1rem', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                          {text.length > 2000 ? text.slice(0, 2000) + '...' : text}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Fallback */}
            {(!state || Object.keys(state).length === 0) && (!history || history.length === 0) && (
              <div style={{ color: '#64748b', fontSize: '1.1rem' }}>No context available (first transfer)</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/** Format millisecond delta as human-readable elapsed time. */
function formatDelta(ms: number): string {
  if (ms < 1000) return `+${ms}ms`;
  if (ms < 60_000) return `+${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `+${m}m ${String(s).padStart(2, '0')}s`;
}

/** Format total elapsed ms as human-readable duration. */
function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`;
  return `${s}s`;
}

/** Shows live elapsed time for running tasks, final duration for completed ones. */
function ElapsedTime({ events, isRunning }: { events: { timestamp: string }[]; isRunning: boolean }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  if (events.length === 0) return null;
  const startTs = new Date(events[0].timestamp).getTime();
  const endTs = isRunning ? now : new Date(events[events.length - 1].timestamp).getTime();
  const elapsed = endTs - startTs;
  if (elapsed < 0) return null;

  return (
    <span style={{ color: isRunning ? '#fbbf24' : '#94a3b8', fontSize: '1.05rem', fontFamily: 'monospace' }}>
      {formatElapsed(elapsed)}
    </span>
  );
}

/** Derive a color pair for each event type. */
function eventStyle(eventType: string): { color: string; border: string } {
  if (eventType.includes('thinking')) return { color: '#a78bfa', border: '#2e1065' };
  if (eventType.includes('tool_use') || eventType.includes('tool_call')) return { color: '#fbbf24', border: '#451a03' };
  if (eventType.includes('tool_result')) return { color: '#34d399', border: '#064e3b' };
  if (eventType === 'streaming_text') return { color: '#22d3ee', border: '#164e63' };
  if (eventType === 'agent_response') return { color: '#e2e8f0', border: '#334155' };
  if (eventType.includes('completed') || eventType.includes('success')) return { color: '#4ade80', border: '#064e3b' };
  if (eventType.includes('failed') || eventType.includes('error')) return { color: '#f87171', border: '#7f1d1d' };
  return { color: '#60a5fa', border: '#1e293b' };
}

/** Build a human-readable summary from event data. */
function eventSummary(evt: TaskEvent): string {
  const d = evt.data as Record<string, unknown> | undefined;
  if (!d) return '';

  const evtType = evt.event_type;

  if (evtType.includes('thinking')) {
    return `${d.is_thought ? 'thought' : 'thinking'}: ${d.text || ''}`;
  }
  if (evtType.includes('tool_use') || evtType.includes('tool_call')) {
    return `calling tool: ${d.tool_name}(${JSON.stringify(d.tool_args || {})})`;
  }
  if (evtType.includes('tool_result')) {
    const resp = typeof d.tool_response === 'string'
      ? d.tool_response
      : JSON.stringify(d.tool_response || '', null, 2);
    const truncated = resp.length > 300 ? resp.slice(0, 300) + '...' : resp;
    return `tool result [${d.tool_name}]: ${truncated}`;
  }
  if (evtType === 'streaming_text') {
    const text = String(d.text || '');
    return text.length > 500 ? text.slice(0, 500) + '...' : text;
  }
  if (evtType === 'agent_response') {
    const text = String(d.text || '');
    return text.length > 500 ? text.slice(0, 500) + '...' : text;
  }

  // Fallback: use summary field or stringify relevant fields
  if (d.text) return String(d.text).slice(0, 500);
  if (d.summary) return String(d.summary);
  if (d.result) return String(d.result).slice(0, 500);
  return '';
}

function EventList({ events }: { events: TaskEvent[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Also scroll when streaming text appends (length stays same, content grows)
  const lastEvent = events[events.length - 1];
  const lastData = lastEvent?.data as Record<string, unknown> | undefined;
  const scrollTrigger = lastEvent?.event_type === 'streaming_text'
    ? (lastData?.text as string)?.length ?? 0
    : 0;

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length, scrollTrigger]);

  return (
    <div
      ref={containerRef}
      style={{
        maxHeight: 300,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem',
        marginTop: '0.375rem',
      }}
    >
      {events.map((evt, i) => {
        const time = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '';
        const prevTs = i > 0 ? new Date(events[i - 1].timestamp).getTime() : 0;
        const curTs = evt.timestamp ? new Date(evt.timestamp).getTime() : 0;
        const delta = i > 0 && prevTs && curTs ? curTs - prevTs : 0;
        const summary = eventSummary(evt);
        const style = eventStyle(evt.event_type);
        const d = evt.data as Record<string, unknown> | undefined;
        const agent = (d?.agent as string) || (d?.author as string) || '';
        const model = (d?.model as string) || '';

        return (
          <div
            key={i}
            style={{
              fontSize: '1.05rem',
              padding: '0.375rem 0.5rem',
              background: '#020617',
              border: `1px solid ${style.border}`,
              borderRadius: 4,
              fontFamily: 'monospace',
            }}
          >
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: summary ? '0.25rem' : 0, alignItems: 'center' }}>
              <span style={{ color: '#475569' }}>{time}</span>
              {delta > 0 && <span style={{ color: '#f59e0b' }}>{formatDelta(delta)}</span>}
              <span style={{ color: style.color }}>{evt.event_type}</span>
              {agent && <span style={{ color: '#a78bfa' }}>{agent}</span>}
              {model && <span style={{ color: '#64748b' }}>[{model}]</span>}
              {d?.transfer_context && typeof d.transfer_context === 'object' && (
                <TransferContextPopup context={d.transfer_context as Record<string, unknown>} />
              )}
            </div>
            {summary && (
              <div style={{ color: '#94a3b8', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {summary}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function TaskTimeline() {
  const tasks = useTaskStore((s) => s.tasks);
  const activeTaskId = useTaskStore((s) => s.activeTaskId);
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});

  const toggleExpanded = (taskId: string) => {
    setExpandedTasks((prev) => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  const taskList = Object.values(tasks).reverse();

  if (taskList.length === 0) {
    return (
      <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>
        No tasks submitted yet. Use the input above to submit a task.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {taskList.map((task) => {
        const isExpanded = expandedTasks[task.task_id] ?? false;
        const isRunning = task.status === 'submitted' || task.status === 'running';

        return (
          <div
            key={task.task_id}
            style={{
              background: task.task_id === activeTaskId ? '#1e3a5f' : '#0f172a',
              border: `1px solid ${task.task_id === activeTaskId ? '#2563eb' : '#334155'}`,
              borderRadius: 8,
              padding: '1rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: '#e2e8f0', fontWeight: 600 }}>
                {task.description.slice(0, 80)}{task.description.length > 80 ? '...' : ''}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ElapsedTime events={task.events} isRunning={isRunning} />
                <span
                  style={{
                    fontSize: '1.125rem',
                    padding: '0.125rem 0.5rem',
                    borderRadius: 4,
                    background:
                      task.status === 'completed' ? '#14532d' :
                      task.status === 'failed' ? '#7f1d1d' :
                      '#1e3a5f',
                    color:
                      task.status === 'completed' ? '#4ade80' :
                      task.status === 'failed' ? '#f87171' :
                      '#60a5fa',
                  }}
                >
                  {task.status}{isRunning ? '...' : ''}
                </span>
              </div>
            </div>

            {task.error && (
              <div
                style={{
                  fontSize: '1.125rem',
                  color: '#fca5a5',
                  background: '#450a0a',
                  border: '1px solid #7f1d1d',
                  borderRadius: 4,
                  padding: '0.5rem 0.625rem',
                  marginBottom: '0.5rem',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {task.error}
              </div>
            )}

            {task.events.length > 0 && (
              <div>
                <button
                  onClick={() => toggleExpanded(task.task_id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#94a3b8',
                    fontSize: '1.125rem',
                    cursor: 'pointer',
                    padding: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                  }}
                >
                  <span style={{ display: 'inline-block', transform: isExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>
                    &#9654;
                  </span>
                  {task.events.length} event(s)
                  {!isExpanded && task.events.length > 0 && (
                    <span style={{ color: '#64748b' }}>
                      {' '}| Latest: {task.events[task.events.length - 1]?.event_type}
                    </span>
                  )}
                </button>
                {isExpanded && <EventList events={task.events} />}
              </div>
            )}

            <div style={{ fontSize: '1.05rem', color: '#475569', fontFamily: 'monospace', marginTop: '0.25rem' }}>
              {task.task_id}
            </div>
          </div>
        );
      })}
    </div>
  );
}
