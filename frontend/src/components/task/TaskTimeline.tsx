import { useState } from 'react';
import { useTaskStore } from '../../stores/taskStore';

function EventList({ events }: { events: { event_type: string; timestamp: string; data: unknown }[] }) {
  return (
    <div
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
        const d = evt.data as Record<string, unknown> | undefined;
        const author = (d?.author as string) || '';
        const summary = (d?.summary as string) || '';
        const time = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '';

        return (
          <div
            key={i}
            style={{
              fontSize: '0.7rem',
              padding: '0.375rem 0.5rem',
              background: '#020617',
              border: '1px solid #1e293b',
              borderRadius: 4,
              fontFamily: 'monospace',
            }}
          >
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: summary ? '0.25rem' : 0 }}>
              <span style={{ color: '#475569' }}>{time}</span>
              <span style={{ color: '#60a5fa' }}>{evt.event_type}</span>
              {author && <span style={{ color: '#a78bfa' }}>{author}</span>}
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
              <span style={{ color: '#e2e8f0', fontSize: '0.875rem', fontWeight: 600 }}>
                {task.description.slice(0, 80)}{task.description.length > 80 ? '...' : ''}
              </span>
              <span
                style={{
                  fontSize: '0.75rem',
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

            {task.error && (
              <div
                style={{
                  fontSize: '0.75rem',
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
                    fontSize: '0.75rem',
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

            <div style={{ fontSize: '0.7rem', color: '#475569', fontFamily: 'monospace', marginTop: '0.25rem' }}>
              {task.task_id}
            </div>
          </div>
        );
      })}
    </div>
  );
}
