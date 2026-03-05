import { useState } from 'react';
import { TaskInput } from './TaskInput';
import { TaskTimeline } from './TaskTimeline';
import { TaskAgentDiagram } from './TaskAgentDiagram';
import { AgentPanel } from './AgentPanel';
import { useTaskStore, type TaskPendingInteraction } from '../../stores/taskStore';

function TaskInteractionForm({ interaction, onResolved }: {
  interaction: TaskPendingInteraction;
  onResolved: (id: string) => void;
}) {
  const [freeText, setFreeText] = useState('');

  const submitResponse = async (response: unknown) => {
    await fetch('/api/tasks/interact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interaction_id: interaction.interaction_id,
        response,
      }),
    });
    onResolved(interaction.interaction_id);
  };

  return (
    <div
      style={{
        background: '#1c1917',
        border: '1px solid #f59e0b',
        borderRadius: 8,
        padding: '1rem',
      }}
    >
      <div style={{ color: '#e2e8f0', marginBottom: '0.75rem' }}>
        {interaction.prompt || 'The agent has a question. Please provide more details.'}
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
    </div>
  );
}

export function TaskPanel() {
  const tasks = useTaskStore((s) => s.tasks);
  const activeTaskId = useTaskStore((s) => s.activeTaskId);
  const pendingInteractions = useTaskStore((s) => s.pendingInteractions);
  const resolveInteraction = useTaskStore((s) => s.resolveInteraction);

  const activeTask = activeTaskId ? tasks[activeTaskId] : null;

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
          <TaskAgentDiagram events={activeTask.events} status={activeTask.status} />
        )}

        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Task History
          </h2>
          <TaskTimeline />
        </div>
      </div>
      <div style={{ width: 300, flexShrink: 0 }}>
        <AgentPanel />
      </div>
    </div>
  );
}
