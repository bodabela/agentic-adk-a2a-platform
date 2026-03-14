import { useState, useMemo } from 'react';
import { TaskInput } from './TaskInput';
import { TaskTimeline } from './TaskTimeline';
import { TaskAgentDiagram } from './TaskAgentDiagram';
import { AgentPanel } from './AgentPanel';
import { A2UIRenderer } from '../../../shared/components/A2UIRenderer';
import { useTaskStore, type TaskPendingInteraction } from '../taskStore';

function TaskInteractionForm({ interaction, onResolved }: {
  interaction: TaskPendingInteraction;
  onResolved: (id: string) => void;
}) {
  const [freeText, setFreeText] = useState('');

  const submitResponse = async (response: unknown) => {
    await fetch('/api/interactions/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interaction_id: interaction.interaction_id,
        response,
      }),
    });
    onResolved(interaction.interaction_id);
  };

  const channelLabel = interaction.channel && interaction.channel !== 'web_ui'
    ? interaction.channel
    : null;

  const hasA2UI = interaction.a2ui_payload && interaction.a2ui_payload.length > 0;

  return (
    <div
      style={{
        background: '#1c1917',
        border: `1px solid ${hasA2UI ? '#3b82f6' : '#f59e0b'}`,
        borderRadius: 8,
        padding: '1rem',
      }}
    >
      {/* A2UI rich UI rendering */}
      {hasA2UI ? (
        <div>
          <A2UIRenderer
            payload={interaction.a2ui_payload!}
            onSubmit={submitResponse}
          />
        </div>
      ) : (
        /* Standard text-based interaction */
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#e2e8f0', marginBottom: '0.75rem' }}>
            <span>{interaction.prompt || 'The agent has a question. Please provide more details.'}</span>
            {channelLabel && (
              <span style={{
                fontSize: '0.85rem',
                padding: '0.1rem 0.4rem',
                borderRadius: 4,
                background: '#1e3a5f',
                color: '#60a5fa',
                fontWeight: 600,
              }}>
                via {channelLabel}
              </span>
            )}
          </div>

          {interaction.options && interaction.options.length > 0 ? (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {interaction.options.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => submitResponse({ id: opt.id })}
                  style={{
                    padding: '0.5rem 1rem',
                    background: opt.recommended ? '#2563eb' : '#334155',
                    color: '#e2e8f0',
                    border: 'none',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontSize: '1.2rem',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          ) : (
            <form
              style={{ display: 'flex', gap: '0.5rem' }}
              onSubmit={async (e) => {
                e.preventDefault();
                if (!freeText.trim()) return;
                await submitResponse(freeText);
                setFreeText('');
              }}
            >
              <input
                type="text"
                placeholder="Type your response..."
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.5rem 0.75rem',
                  background: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: 6,
                  color: '#e2e8f0',
                  fontSize: '1.275rem',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '0.5rem 1rem',
                  background: '#f59e0b',
                  color: '#1c1917',
                  border: 'none',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: '1.2rem',
                  fontWeight: 600,
                }}
              >
                Send
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}

export function TaskPanel() {
  const tasks = useTaskStore((s) => s.tasks);
  const activeTaskId = useTaskStore((s) => s.activeTaskId);
  const pendingInteractions = useTaskStore((s) => s.pendingInteractions);
  const resolveInteraction = useTaskStore((s) => s.resolveInteraction);

  const activeTask = activeTaskId ? tasks[activeTaskId] : null;

  // Derive active agent name from the latest task events
  const activeAgentName = useMemo(() => {
    if (!activeTask || activeTask.status === 'completed' || activeTask.status === 'failed') return '';
    const evts = activeTask.events;
    for (let i = evts.length - 1; i >= 0; i--) {
      const d = evts[i].data as Record<string, unknown>;
      const agent = (d.agent as string) || (d.author as string) || '';
      if (agent && ['streaming_text', 'tool_call', 'agent_response', 'thinking'].includes(evts[i].event_type)) {
        return agent;
      }
    }
    return '';
  }, [activeTask]);

  return (
    <div style={{ display: 'flex', gap: '1.5rem' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Submit Task
          </h2>
          <TaskInput />
        </div>

        {pendingInteractions.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h3 style={{ color: '#f59e0b', fontSize: '1rem', margin: 0 }}>Agent Questions</h3>
            {pendingInteractions.map((interaction) => (
              <TaskInteractionForm
                key={interaction.interaction_id}
                interaction={interaction}
                onResolved={resolveInteraction}
              />
            ))}
          </div>
        )}

        {activeTask && activeTask.events.length > 0 && (
          <TaskAgentDiagram events={activeTask.events} status={activeTask.status} taskId={activeTask.task_id} traceId={activeTask.traceId} />
        )}

        {activeTask && activeTask.notifications.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {activeTask.notifications.map((msg, i) => (
              <div key={i} style={{
                background: '#1a1a2e',
                border: '1px solid #6366f1',
                borderRadius: 8,
                padding: '0.75rem 1rem',
              }}>
                <div style={{ color: '#a5b4fc', fontWeight: 600, fontSize: '0.75rem', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Notification
                </div>
                <div style={{ color: '#e2e8f0', fontSize: '1rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                  {msg}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTask?.finalResult && (
          <div style={{
            background: '#0c2d1b',
            border: '1px solid #22c55e',
            borderRadius: 8,
            padding: '1rem 1.25rem',
          }}>
            <div style={{ color: '#4ade80', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Result
            </div>
            <div style={{ color: '#e2e8f0', fontSize: '1.1rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {activeTask.finalResult}
            </div>
          </div>
        )}

        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Task History
          </h2>
          <TaskTimeline />
        </div>
      </div>
      <div style={{ width: 300, flexShrink: 0 }}>
        <AgentPanel activeAgentName={activeAgentName} />
      </div>
    </div>
  );
}
