import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '~' },
  { path: '/tasks', label: 'Tasks', icon: '>' },
  { path: '/flows', label: 'Flows', icon: '#' },
  { path: '/costs', label: 'Costs', icon: '$' },
];

export function Sidebar() {
  return (
    <nav
      style={{
        width: 250,
        background: '#0f172a',
        borderRight: '1px solid #334155',
        padding: '1rem 0',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          padding: '0 1rem 1.5rem',
          borderBottom: '1px solid #334155',
          marginBottom: '1rem',
        }}
      >
        <h1 style={{ color: '#e2e8f0', fontSize: '1.4rem', margin: 0, fontWeight: 700 }}>
          Agent Platform
        </h1>
        <span style={{ color: '#64748b', fontSize: '1rem' }}>v0.1.0</span>
      </div>

      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.75rem 1.25rem',
            color: isActive ? '#38bdf8' : '#94a3b8',
            background: isActive ? '#1e293b' : 'transparent',
            textDecoration: 'none',
            fontSize: '1.15rem',
            borderLeft: isActive ? '3px solid #38bdf8' : '3px solid transparent',
          })}
        >
          <span style={{ fontFamily: 'monospace', width: 20, textAlign: 'center', fontSize: '1.2rem' }}>
            {item.icon}
          </span>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
