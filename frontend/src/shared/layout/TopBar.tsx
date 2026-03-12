import { CostBadge } from '../components/CostBadge';

export function TopBar() {
  return (
    <header
      style={{
        height: 48,
        background: '#0f172a',
        borderBottom: '1px solid #334155',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem',
      }}
    >
      <div style={{ color: '#94a3b8', fontSize: '1.2rem' }}>
        Modular Multi-Agent Platform
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <CostBadge />
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#22c55e',
          }}
          title="SSE Connected"
        />
      </div>
    </header>
  );
}
