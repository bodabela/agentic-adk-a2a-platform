import { useEffect, useRef, useState } from 'react';
import { useFlowStore, type FlowEvent, type InteractionQuestion } from '../../stores/flowStore';

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

/** Shows live elapsed time for running flows, final duration for completed ones. */
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
      return `${d.is_thought ? 'thought' : 'thinking'}: ${d.text}`;
    case 'flow_agent_tool_use':
      return `calling tool: ${d.tool_name}(${JSON.stringify(d.tool_args || {})})`;
    case 'flow_agent_tool_result': {
      const resp = typeof d.tool_response === 'string'
        ? d.tool_response
        : JSON.stringify(d.tool_response || '', null, 2);
      const truncated = resp.length > 300 ? resp.slice(0, 300) + '...' : resp;
      return `tool result [${d.tool_name}]: ${truncated}`;
    }
    case 'flow_agent_streaming_text': {
      const text = String(d.text || '');
      return text.length > 500 ? text.slice(0, 500) + '...' : text;
    }
    case 'flow_llm_decision':
      return `LLM decision: ${d.decision}${d.reason ? ` — ${d.reason}` : ''}`;
    case 'flow_input_required':
      return `Waiting for user input: ${d.prompt || d.interaction_type}`;
    case 'flow_user_response':
      return `User responded: ${d.response}`;
    case 'flow_completed': {
      let completedMsg = `Flow completed (${d.status})`;
      const output = d.output as Record<string, unknown> | undefined;
      if (output?.result) {
        const resultStr = typeof output.result === 'string'
          ? output.result
          : JSON.stringify(output.result, null, 2);
        completedMsg += `\n\n${resultStr}`;
      }
      return completedMsg;
    }
    case 'flow_retry_exceeded':
      return `Retry limit exceeded: ${d.loop}`;
    default:
      return evt.event_type;
  }
}

/** Renders a form with one input per question, submitted together. */
export function MultiQuestionForm({
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
          <label style={{ color: '#cbd5e1', fontSize: '1.2rem', fontWeight: 500 }}>
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
                    fontSize: '1.2rem',
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
                fontSize: '1.275rem',
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
          fontSize: '1.2rem',
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
  const containerRef = useRef<HTMLDivElement>(null);

  // Also scroll when streaming text appends (length stays same, content grows)
  const lastEvent = events[events.length - 1];
  const scrollTrigger = lastEvent?.event_type === 'flow_agent_streaming_text'
    ? (lastEvent.data.text as string)?.length ?? 0
    : 0;

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length, scrollTrigger]);

  return (
    <div
      ref={containerRef}
      style={{
        maxHeight: 500,
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
        const agent = (evt.data.agent as string) || (evt.data.author as string) || '';
        const rawModel = (evt.data.model as string) || '';
        const rawProvider = (evt.data.provider as string) || '';
        const model = rawProvider && rawModel ? `${rawProvider}/${rawModel}` : rawModel;

        // Color coding for streaming events
        let eventColor = '#60a5fa'; // default blue
        let borderColor = '#1e293b';
        if (evt.event_type === 'flow_agent_thinking') {
          eventColor = '#a78bfa'; borderColor = '#2e1065';
        } else if (evt.event_type === 'flow_agent_tool_use') {
          eventColor = '#fbbf24'; borderColor = '#451a03';
        } else if (evt.event_type === 'flow_agent_tool_result') {
          eventColor = '#34d399'; borderColor = '#064e3b';
        } else if (evt.event_type === 'flow_agent_streaming_text') {
          eventColor = '#22d3ee'; borderColor = '#164e63';
        }

        return (
          <div
            key={i}
            style={{
              fontSize: '1.05rem',
              padding: '0.375rem 0.5rem',
              background: '#020617',
              border: `1px solid ${borderColor}`,
              borderRadius: 4,
              fontFamily: 'monospace',
            }}
          >
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: summary ? '0.25rem' : 0 }}>
              <span style={{ color: '#475569' }}>{time}</span>
              {delta > 0 && <span style={{ color: '#f59e0b' }}>{formatDelta(delta)}</span>}
              <span style={{ color: eventColor }}>{evt.event_type}</span>
              {agent && <span style={{ color: '#a78bfa' }}>{agent}</span>}
              {model && <span style={{ color: '#64748b' }}>[{model}]</span>}
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ElapsedTime events={events} isRunning={flow.status !== 'completed' && flow.status !== 'failed'} />
                  <span
                    style={{
                      fontSize: '1.125rem',
                      padding: '0.125rem 0.5rem',
                      borderRadius: 4,
                      background: flow.status === 'completed' ? '#14532d' : '#1e3a5f',
                      color: flow.status === 'completed' ? '#4ade80' : '#60a5fa',
                    }}
                  >
                    {flow.status}
                  </span>
                </div>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '1.2rem' }}>
                Current state: <span style={{ color: '#38bdf8' }}>{flow.currentState || '...'}</span>
              </div>
              {flow.provider && flow.model && (
                <div style={{ color: '#64748b', fontSize: '1.125rem', marginTop: '0.25rem' }}>
                  Model: <span style={{ color: '#a78bfa' }}>{flow.provider}/{flow.model}</span>
                </div>
              )}

              {/* Event timeline */}
              {events.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <button
                    onClick={() => toggleExpanded(flow.flowId)}
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
                  <div style={{ color: '#4ade80', fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                    Result
                  </div>
                  <pre
                    style={{
                      color: '#cbd5e1',
                      fontSize: '1.125rem',
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

    </div>
  );
}
