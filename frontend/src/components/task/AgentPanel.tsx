import { useState, useEffect } from 'react';
import { CapabilityBadges, ToolBadges } from '../common/AgentBadges';

interface AgentInfo {
  name: string;
  version: string;
  description: string;
  capabilities: string[];
  category: string;
  model: string;
  tools: string[];
}

export function AgentPanel({ activeAgentName = '' }: { activeAgentName?: string }) {
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
      <div style={{ color: '#64748b', fontSize: '1.2rem', padding: '1rem' }}>
        Loading agents...
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: '1.2rem', padding: '1rem' }}>
        No agent modules discovered.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <style>{`
        @keyframes agent-pulse {
          0%, 100% { box-shadow: 0 0 4px rgba(34,211,238,0.15); border-color: rgba(34,211,238,0.5); }
          50% { box-shadow: 0 0 24px rgba(34,211,238,0.55), 0 0 48px rgba(34,211,238,0.2); border-color: rgba(34,211,238,1); }
        }
      `}</style>
      <h3 style={{ color: '#94a3b8', fontSize: '1.125rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
        Available Agents
      </h3>
      {agents.map((agent) => {
        const isActive = activeAgentName === agent.name;
        return (
        <div
          key={agent.name}
          style={{
            background: isActive ? '#0c1a2e' : '#0f172a',
            border: `1px solid ${isActive ? '#22d3ee' : '#334155'}`,
            borderRadius: 8,
            padding: '0.75rem',
            boxShadow: isActive ? '0 0 12px rgba(34, 211, 238, 0.25)' : 'none',
            transition: 'border-color 0.3s, box-shadow 0.3s, background 0.3s',
            animation: isActive ? 'agent-pulse 1.5s ease-in-out infinite' : 'none',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.375rem' }}>
            <span style={{ color: isActive ? '#22d3ee' : '#e2e8f0', fontSize: '1.2rem', fontWeight: 600 }}>
              {isActive && '● '}{agent.name}
            </span>
            <span style={{ color: '#475569', fontSize: '0.975rem', fontFamily: 'monospace' }}>
              v{agent.version}
            </span>
          </div>

          <div style={{ color: '#94a3b8', fontSize: '1.125rem', marginBottom: '0.5rem' }}>
            {agent.description}
          </div>

          <div style={{ marginBottom: '0.375rem' }}>
            <CapabilityBadges items={agent.capabilities} />
          </div>
          <ToolBadges items={agent.tools} />

          {agent.model && (
            <div style={{ color: '#475569', fontSize: '0.975rem', marginTop: '0.375rem' }}>
              model: {agent.model}
            </div>
          )}
        </div>
        );
      })}
    </div>
  );
}
