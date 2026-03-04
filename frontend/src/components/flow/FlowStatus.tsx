import { useState } from 'react';
import { useFlowStore, type FlowEvent } from '../../stores/flowStore';

/** Human-readable summary for each flow event type. */
function eventSummary(evt: FlowEvent): string {
  const d = evt.data;
  switch (evt.event_type) {
    case 'flow_started':
      return `Flow "${d.flow_name}" started`;
    case 'flow_state_entered':
      return `Entered state: ${d.state} (${d.node_type})`;
    case 'flow_agent_task_started':
      return `Agent "${d.agent}" started — ${(d.input_summary as string) || ''}`;
    case 'flow_agent_task_completed': {
      const files = (d.workspace_files as string[]) || [];
      const fileLine = files.length > 0 ? `\nFiles: ${files.join(', ')}` : '';
      return `Agent "${d.agent}" completed${d.output_summary ? `\n${d.output_summary}` : ''}${fileLine}`;
    }
    case 'flow_llm_decision':
      return `LLM decision: ${d.decision}${d.reason ? ` — ${d.reason}` : ''} [${d.provider}/${d.model}]`;
    case 'flow_input_required':
      return `Waiting for user input: ${d.prompt || d.interaction_type}`;
    case 'flow_completed':
      return `Flow completed (${d.status})`;
    case 'flow_retry_exceeded':
      return `Retry limit exceeded: ${d.loop}`;
    default:
      return evt.event_type;
  }
}

function FlowEventList({ events }: { events: FlowEvent[] }) {
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
        const time = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '';
        const summary = eventSummary(evt);

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

export function FlowStatus() {
  const activeFlows = useFlowStore((s) => s.activeFlows);
  const pendingInteractions = useFlowStore((s) => s.pendingInteractions);
  const resolveInteraction = useFlowStore((s) => s.resolveInteraction);

  const [freeTextValues, setFreeTextValues] = useState<Record<string, string>>({});
  const [expandedFlows, setExpandedFlows] = useState<Record<string, boolean>>({});

  const flows = Object.values(activeFlows);

  const toggleExpanded = (flowId: string) => {
    setExpandedFlows((prev) => ({ ...prev, [flowId]: !prev[flowId] }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem' }}>Active Flows</h2>

      {flows.length === 0 ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>
          No active flows. Start a flow from the API or submit a task.
        </div>
      ) : (
        flows.map((flow) => {
          const events = flow.events || [];
          const isExpanded = expandedFlows[flow.flowId] ?? false;

          return (
            <div
              key={flow.flowId}
              style={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{flow.flowName}</span>
                <span
                  style={{
                    fontSize: '0.75rem',
                    padding: '0.125rem 0.5rem',
                    borderRadius: 4,
                    background: flow.status === 'completed' ? '#14532d' : '#1e3a5f',
                    color: flow.status === 'completed' ? '#4ade80' : '#60a5fa',
                  }}
                >
                  {flow.status}
                </span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                Current state: <span style={{ color: '#38bdf8' }}>{flow.currentState || '...'}</span>
              </div>

              {/* Event timeline */}
              {events.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <button
                    onClick={() => toggleExpanded(flow.flowId)}
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
                    {events.length} event(s)
                    {!isExpanded && events.length > 0 && (
                      <span style={{ color: '#64748b' }}>
                        {' '}| Latest: {events[events.length - 1]?.event_type}
                      </span>
                    )}
                  </button>
                  {isExpanded && <FlowEventList events={events} />}
                </div>
              )}

              {/* Completed flow output */}
              {flow.status === 'completed' && flow.output && (
                <div
                  style={{
                    marginTop: '0.75rem',
                    padding: '0.75rem',
                    background: '#0a1628',
                    border: '1px solid #1e3a5f',
                    borderRadius: 6,
                  }}
                >
                  <div style={{ color: '#4ade80', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                    Result
                  </div>
                  <pre
                    style={{
                      color: '#cbd5e1',
                      fontSize: '0.75rem',
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      maxHeight: '400px',
                      overflow: 'auto',
                    }}
                  >
                    {JSON.stringify(flow.output, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })
      )}

      {pendingInteractions.length > 0 && (
        <>
          <h3 style={{ color: '#f59e0b', fontSize: '1rem' }}>Pending Interactions</h3>
          {pendingInteractions.map((interaction) => (
            <div
              key={interaction.interaction_id}
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
                      onClick={async () => {
                        await fetch('/api/flows/interact', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            interaction_id: interaction.interaction_id,
                            response: { id: opt.id },
                          }),
                        });
                        resolveInteraction(interaction.interaction_id);
                      }}
                      style={{
                        padding: '0.5rem 1rem',
                        background: opt.recommended ? '#2563eb' : '#334155',
                        color: '#e2e8f0',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: '0.8rem',
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
                    const text = freeTextValues[interaction.interaction_id] ?? '';
                    if (!text.trim()) return;
                    await fetch('/api/flows/interact', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        interaction_id: interaction.interaction_id,
                        response: text,
                      }),
                    });
                    resolveInteraction(interaction.interaction_id);
                    setFreeTextValues((prev) => {
                      const next = { ...prev };
                      delete next[interaction.interaction_id];
                      return next;
                    });
                  }}
                >
                  <input
                    type="text"
                    placeholder="Type your response..."
                    value={freeTextValues[interaction.interaction_id] ?? ''}
                    onChange={(e) =>
                      setFreeTextValues((prev) => ({
                        ...prev,
                        [interaction.interaction_id]: e.target.value,
                      }))
                    }
                    style={{
                      flex: 1,
                      padding: '0.5rem 0.75rem',
                      background: '#1e293b',
                      border: '1px solid #475569',
                      borderRadius: 6,
                      color: '#e2e8f0',
                      fontSize: '0.85rem',
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
                      fontSize: '0.8rem',
                      fontWeight: 600,
                    }}
                  >
                    Send
                  </button>
                </form>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
