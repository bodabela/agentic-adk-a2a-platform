import { useCostStore } from '../stores/costStore';

export function CostsPage() {
  const totalCost = useCostStore((s) => s.totalCostUsd);
  const costByTask = useCostStore((s) => s.costByTask);
  const recentEvents = useCostStore((s) => s.recentEvents);

  const taskEntries = Object.entries(costByTask);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem' }}>Cost Overview</h2>

      <div
        style={{
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 8,
          padding: '1.5rem',
          textAlign: 'center',
        }}
      >
        <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
          Total Spend
        </div>
        <div
          style={{
            color: totalCost > 1 ? '#f59e0b' : '#22c55e',
            fontSize: '2rem',
            fontWeight: 700,
            fontFamily: 'monospace',
          }}
        >
          ${totalCost.toFixed(4)}
        </div>
      </div>

      {taskEntries.length > 0 && (
        <div>
          <h3 style={{ color: '#e2e8f0', fontSize: '1rem', marginBottom: '0.75rem' }}>
            Cost by Task
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {taskEntries.map(([taskId, cost]) => (
              <div
                key={taskId}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  padding: '0.75rem 1rem',
                }}
              >
                <span style={{ color: '#94a3b8', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                  {taskId.slice(0, 12)}...
                </span>
                <span style={{ color: '#22c55e', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  ${cost.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {recentEvents.length > 0 && (
        <div>
          <h3 style={{ color: '#e2e8f0', fontSize: '1rem', marginBottom: '0.75rem' }}>
            Recent Events
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {recentEvents.slice(-20).reverse().map((evt, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  padding: '0.5rem 1rem',
                  fontSize: '0.75rem',
                }}
              >
                <span style={{ color: '#94a3b8' }}>{evt.operation_type}</span>
                <span style={{ color: '#60a5fa', fontFamily: 'monospace' }}>
                  ${evt.cost_usd.toFixed(6)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {taskEntries.length === 0 && recentEvents.length === 0 && (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>
          No cost data yet. Submit a task or start a flow.
        </div>
      )}
    </div>
  );
}
