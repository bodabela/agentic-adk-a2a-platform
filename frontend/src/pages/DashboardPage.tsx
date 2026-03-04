import { useTaskStore } from '../stores/taskStore';
import { useFlowStore } from '../stores/flowStore';
import { useCostStore } from '../stores/costStore';

export function DashboardPage() {
  const tasks = useTaskStore((s) => s.tasks);
  const activeFlows = useFlowStore((s) => s.activeFlows);
  const pendingInteractions = useFlowStore((s) => s.pendingInteractions);
  const totalCost = useCostStore((s) => s.totalCostUsd);

  const taskCount = Object.keys(tasks).length;
  const flowCount = Object.keys(activeFlows).length;
  const runningTasks = Object.values(tasks).filter((t) => t.status === 'running').length;

  const cards = [
    { label: 'Total Tasks', value: taskCount, color: '#60a5fa' },
    { label: 'Running', value: runningTasks, color: '#f59e0b' },
    { label: 'Active Flows', value: flowCount, color: '#a78bfa' },
    { label: 'Pending Interactions', value: pendingInteractions.length, color: '#f87171' },
    { label: 'Total Cost', value: `$${totalCost.toFixed(4)}`, color: '#22c55e' },
  ];

  return (
    <div>
      <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1.5rem' }}>
        Dashboard
      </h2>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: '1rem',
          marginBottom: '2rem',
        }}
      >
        {cards.map((card) => (
          <div
            key={card.label}
            style={{
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 8,
              padding: '1.25rem',
            }}
          >
            <div style={{ color: '#94a3b8', fontSize: '1.125rem', marginBottom: '0.5rem' }}>
              {card.label}
            </div>
            <div style={{ color: card.color, fontSize: '1.5rem', fontWeight: 700 }}>
              {card.value}
            </div>
          </div>
        ))}
      </div>

      <div style={{ color: '#64748b', fontSize: '0.875rem' }}>
        Submit a task or start a flow to get started.
      </div>
    </div>
  );
}
