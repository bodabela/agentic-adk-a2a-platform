import { useFlowStore } from '../../stores/flowStore';

export function FlowStatus() {
  const activeFlows = useFlowStore((s) => s.activeFlows);
  const pendingInteractions = useFlowStore((s) => s.pendingInteractions);
  const resolveInteraction = useFlowStore((s) => s.resolveInteraction);

  const flows = Object.values(activeFlows);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem' }}>Active Flows</h2>

      {flows.length === 0 ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>
          No active flows. Start a flow from the API or submit a task.
        </div>
      ) : (
        flows.map((flow) => (
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
          </div>
        ))
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
                {interaction.prompt}
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
                <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                  Type: {interaction.interaction_type}
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
