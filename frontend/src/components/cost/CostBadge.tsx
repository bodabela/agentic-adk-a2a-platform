import { useCostStore } from '../../stores/costStore';

export function CostBadge() {
  const totalCost = useCostStore((s) => s.totalCostUsd);

  return (
    <div
      style={{
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 6,
        padding: '0.25rem 0.75rem',
        color: totalCost > 1 ? '#f59e0b' : '#22c55e',
        fontSize: '0.8rem',
        fontFamily: 'monospace',
      }}
    >
      ${totalCost.toFixed(4)}
    </div>
  );
}
