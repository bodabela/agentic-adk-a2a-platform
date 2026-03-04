import { useState, useEffect } from 'react';

interface AgentInfo {
  name: string;
  version: string;
  description: string;
  capabilities: string[];
  category: string;
  model: string;
  tools: string[];
}

export function AgentPanel() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/agents/')
      .then((r) => r.json())
      .then((data: { agents: AgentInfo[] }) => {
        setAgents(data.agents);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.8rem', padding: '1rem' }}>
        Loading agents...
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.8rem', padding: '1rem' }}>
        No agent modules discovered.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <h3 style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
        Available Agents
      </h3>
      {agents.map((agent) => (
        <div
          key={agent.name}
          style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.375rem' }}>
            <span style={{ color: '#e2e8f0', fontSize: '0.8rem', fontWeight: 600 }}>
              {agent.name}
            </span>
            <span style={{ color: '#475569', fontSize: '0.65rem', fontFamily: 'monospace' }}>
              v{agent.version}
            </span>
          </div>

          <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginBottom: '0.5rem' }}>
            {agent.description}
          </div>

          {agent.capabilities.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginBottom: '0.375rem' }}>
              {agent.capabilities.map((cap) => (
                <span
                  key={cap}
                  style={{
                    fontSize: '0.65rem',
                    padding: '0.125rem 0.375rem',
                    borderRadius: 4,
                    background: '#1e3a5f',
                    color: '#60a5fa',
                  }}
                >
                  {cap}
                </span>
              ))}
            </div>
          )}

          {agent.tools.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
              {agent.tools.map((tool) => (
                <span
                  key={tool}
                  style={{
                    fontSize: '0.65rem',
                    padding: '0.125rem 0.375rem',
                    borderRadius: 4,
                    background: '#14532d',
                    color: '#4ade80',
                  }}
                >
                  {tool}
                </span>
              ))}
            </div>
          )}

          {agent.model && (
            <div style={{ color: '#475569', fontSize: '0.65rem', marginTop: '0.375rem' }}>
              model: {agent.model}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
