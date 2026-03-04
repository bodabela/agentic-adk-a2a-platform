import { useState } from 'react';
import { useFlowStore, type FlowEvent, type InteractionQuestion } from '../../stores/flowStore';

/** Human-readable summary for each flow event type. */
function eventSummary(evt: FlowEvent): string {
  const d = evt.data;
  switch (evt.event_type) {
    case 'flow_started':
      return `Flow "${d.flow_name}" started`;
    case 'flow_state_entered':
      return `Entered state: ${d.state} (${d.node_type})`;
    case 'flow_agent_task_started': {
      const input = d.input as Record<string, unknown> | undefined;
      const inputStr = input ? JSON.stringify(input, null, 2) : '';
      return `Agent "${d.agent}" started\n${inputStr}`;
    }
    case 'flow_agent_task_completed': {
      const files = (d.workspace_files as string[]) || [];
      const fileLine = files.length > 0 ? `\nFiles: ${files.join(', ')}` : '';
      return `Agent "${d.agent}" completed${d.output_summary ? `\n${d.output_summary}` : ''}${fileLine}`;
    }
    case 'flow_agent_thinking':
      return `${d.agent} thinking: ${d.text}`;
    case 'flow_agent_tool_use':
      return `${d.agent} calling tool: ${d.tool_name}(${JSON.stringify(d.tool_args || {})})`;
    case 'flow_agent_tool_result': {
      const resp = typeof d.tool_response === 'string'
        ? d.tool_response
        : JSON.stringify(d.tool_response || '', null, 2);
      const truncated = resp.length > 300 ? resp.slice(0, 300) + '...' : resp;
      return `${d.agent} tool result [${d.tool_name}]: ${truncated}`;
    }
    case 'flow_llm_decision':
      return `LLM decision: ${d.decision}${d.reason ? ` — ${d.reason}` : ''} [${d.provider}/${d.model}]`;
    case 'flow_input_required':
      return `Waiting for user input: ${d.prompt || d.interaction_type}`;
    case 'flow_user_response':
      return `User responded: ${d.response}`;
    case 'flow_completed':
      return `Flow completed (${d.status})`;
    case 'flow_retry_exceeded':
      return `Retry limit exceeded: ${d.loop}`;
    default:
      return evt.event_type;
  }
}

/** Renders a form with one input per question, submitted together. */
function MultiQuestionForm({
  interaction,
  answers,
  onAnswerChange,
  onSubmit,
}: {
  interaction: { questions?: InteractionQuestion[] };
  answers: Record<string, string>;
  onAnswerChange: (questionId: string, value: string) => void;
  onSubmit: () => void;
}) {
  const questions = interaction.questions ?? [];
  const allRequired = questions.filter((q) => q.required !== false);
  const allAnswered = allRequired.every((q) => (answers[q.id] ?? '').trim() !== '');

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (allAnswered) onSubmit();
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
    >
      {questions.map((q, idx) => (
        <div key={q.id} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ color: '#cbd5e1', fontSize: '0.8rem', fontWeight: 500 }}>
            {idx + 1}. {q.text}
            {q.required !== false && <span style={{ color: '#f87171' }}> *</span>}
          </label>

          {q.question_type === 'choice' && q.options && q.options.length > 0 ? (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {q.options.map((opt) => (
                <button
                  type="button"
                  key={opt.id}
                  onClick={() => onAnswerChange(q.id, opt.id)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    background: answers[q.id] === opt.id ? '#2563eb' : '#334155',
                    color: '#e2e8f0',
                    border: answers[q.id] === opt.id ? '2px solid #60a5fa' : '1px solid #475569',
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
            <input
              type="text"
              placeholder="Type your answer..."
              value={answers[q.id] ?? ''}
              onChange={(e) => onAnswerChange(q.id, e.target.value)}
              style={{
                padding: '0.5rem 0.75rem',
                background: '#1e293b',
                border: '1px solid #475569',
                borderRadius: 6,
                color: '#e2e8f0',
                fontSize: '0.85rem',
                outline: 'none',
              }}
            />
          )}
        </div>
      ))}

      <button
        type="submit"
        disabled={!allAnswered}
        style={{
          padding: '0.5rem 1rem',
          background: allAnswered ? '#f59e0b' : '#44403c',
          color: allAnswered ? '#1c1917' : '#78716c',
          border: 'none',
          borderRadius: 6,
          cursor: allAnswered ? 'pointer' : 'not-allowed',
          fontSize: '0.8rem',
          fontWeight: 600,
          alignSelf: 'flex-start',
          marginTop: '0.25rem',
        }}
      >
        Submit All Answers
      </button>
    </form>
  );
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

        // Color coding for streaming events
        let eventColor = '#60a5fa'; // default blue
        let borderColor = '#1e293b';
        if (evt.event_type === 'flow_agent_thinking') {
          eventColor = '#a78bfa'; borderColor = '#2e1065';
        } else if (evt.event_type === 'flow_agent_tool_use') {
          eventColor = '#fbbf24'; borderColor = '#451a03';
        } else if (evt.event_type === 'flow_agent_tool_result') {
          eventColor = '#34d399'; borderColor = '#064e3b';
        }

        return (
          <div
            key={i}
            style={{
              fontSize: '0.7rem',
              padding: '0.375rem 0.5rem',
              background: '#020617',
              border: `1px solid ${borderColor}`,
              borderRadius: 4,
              fontFamily: 'monospace',
            }}
          >
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: summary ? '0.25rem' : 0 }}>
              <span style={{ color: '#475569' }}>{time}</span>
              <span style={{ color: eventColor }}>{evt.event_type}</span>
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
  // For multi_question: { [interaction_id]: { [question_id]: answer } }
  const [multiAnswers, setMultiAnswers] = useState<Record<string, Record<string, string>>>({});
  const [expandedFlows, setExpandedFlows] = useState<Record<string, boolean>>({});

  const flows = Object.values(activeFlows).reverse();

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

              {/* ── Multi-question form ── */}
              {interaction.interaction_type === 'multi_question' && interaction.questions && interaction.questions.length > 0 ? (
                <MultiQuestionForm
                  interaction={interaction}
                  answers={multiAnswers[interaction.interaction_id] ?? {}}
                  onAnswerChange={(questionId, value) =>
                    setMultiAnswers((prev) => ({
                      ...prev,
                      [interaction.interaction_id]: {
                        ...prev[interaction.interaction_id],
                        [questionId]: value,
                      },
                    }))
                  }
                  onSubmit={async () => {
                    const answers = multiAnswers[interaction.interaction_id] ?? {};
                    await fetch('/api/flows/interact', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        interaction_id: interaction.interaction_id,
                        response: answers,
                      }),
                    });
                    resolveInteraction(interaction.interaction_id);
                    setMultiAnswers((prev) => {
                      const next = { ...prev };
                      delete next[interaction.interaction_id];
                      return next;
                    });
                  }}
                />
              ) : interaction.options && interaction.options.length > 0 ? (
                /* ── Choice buttons ── */
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
                /* ── Free text input ── */
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
