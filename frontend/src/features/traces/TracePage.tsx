import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TraceLinks } from '../../shared/components/TraceLinks';

interface TraceDiagramData {
  trace_id: string;
  entity_type: 'task' | 'flow';
  entity_id: string;
  cost_report: {
    task_id: string;
    total_cost_usd: number;
    llm_calls: number;
    tool_invocations: number;
    total_input_tokens: number;
    total_output_tokens: number;
    events: Array<{
      event_id: string;
      timestamp: string;
      module: string;
      agent: string;
      operation_type: string;
      trace_id: string;
      span_id: string;
      llm?: { model: string; input_tokens: number; output_tokens: number; total_cost_usd: number; latency_ms: number };
      tool?: { tool_id: string; latency_ms: number };
    }>;
  } | null;
  error?: string;
}

export function TracePage() {
  const { traceId } = useParams<{ traceId: string }>();
  const [data, setData] = useState<TraceDiagramData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!traceId) return;
    fetch(`/api/traces/${traceId}/diagram`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [traceId]);

  if (loading) {
    return (
      <div style={{ padding: '2rem', color: '#94a3b8' }}>Loading trace data...</div>
    );
  }

  if (!data || data.error) {
    return (
      <div style={{ padding: '2rem' }}>
        <h2 style={{ color: '#e2e8f0', marginBottom: '1rem' }}>Trace Not Found</h2>
        <p style={{ color: '#94a3b8' }}>
          Trace <code style={{ color: '#f97316' }}>{traceId}</code> was not found.
          It may have expired from the in-memory registry.
        </p>
        <Link to="/" style={{ color: '#818cf8', marginTop: '1rem', display: 'inline-block' }}>
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const report = data.cost_report;

  return (
    <div style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <h2 style={{ color: '#e2e8f0', margin: 0, fontSize: '1.25rem' }}>
          Trace: {data.entity_type === 'task' ? 'Task' : 'Flow'}
        </h2>
        <code style={{ color: '#64748b', fontSize: '0.8rem' }}>{data.entity_id}</code>
        <TraceLinks traceId={data.trace_id} entityType={data.entity_type} entityId={data.entity_id} />
      </div>

      {/* Link to entity page */}
      <div style={{ marginBottom: '1.5rem' }}>
        <Link
          to={data.entity_type === 'task' ? '/tasks' : '/flows'}
          style={{ color: '#818cf8', fontSize: '0.9rem' }}
        >
          View in {data.entity_type === 'task' ? 'Tasks' : 'Flows'} page
        </Link>
      </div>

      {/* Cost summary */}
      {report && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}>
          {[
            { label: 'Total Cost', value: `$${report.total_cost_usd.toFixed(6)}`, color: '#f97316' },
            { label: 'LLM Calls', value: report.llm_calls, color: '#3b82f6' },
            { label: 'Tool Calls', value: report.tool_invocations, color: '#fbbf24' },
            { label: 'Input Tokens', value: report.total_input_tokens.toLocaleString(), color: '#22d3ee' },
            { label: 'Output Tokens', value: report.total_output_tokens.toLocaleString(), color: '#a78bfa' },
          ].map((stat) => (
            <div key={stat.label} style={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 8,
              padding: '1rem',
            }}>
              <div style={{ color: '#64748b', fontSize: '0.75rem', marginBottom: 4 }}>{stat.label}</div>
              <div style={{ color: stat.color, fontSize: '1.25rem', fontWeight: 600 }}>{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Event timeline */}
      {report && report.events.length > 0 && (
        <div>
          <h3 style={{ color: '#e2e8f0', fontSize: '1rem', marginBottom: '0.75rem' }}>
            Cost Events ({report.events.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {report.events.map((evt) => (
              <div key={evt.event_id} style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 6,
                padding: '0.75rem 1rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.85rem',
              }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <span style={{
                    color: evt.operation_type === 'llm_call' ? '#3b82f6' : '#fbbf24',
                    fontWeight: 500,
                    minWidth: 90,
                  }}>
                    {evt.operation_type}
                  </span>
                  <span style={{ color: '#94a3b8' }}>{evt.agent}</span>
                  {evt.llm && (
                    <span style={{ color: '#64748b' }}>
                      {evt.llm.model} ({evt.llm.input_tokens}+{evt.llm.output_tokens} tokens, {evt.llm.latency_ms}ms)
                    </span>
                  )}
                  {evt.tool && (
                    <span style={{ color: '#64748b' }}>
                      {evt.tool.tool_id} ({evt.tool.latency_ms}ms)
                    </span>
                  )}
                </div>
                <div style={{ color: '#64748b', fontSize: '0.75rem' }}>
                  {evt.llm ? `$${evt.llm.total_cost_usd.toFixed(6)}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
