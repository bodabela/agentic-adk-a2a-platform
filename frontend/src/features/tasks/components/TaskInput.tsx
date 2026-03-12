import { useState, useEffect } from 'react';
import { useTaskStore } from '../taskStore';
import { useRootAgentStore, type RootAgentDefinition } from '../../root-agents/rootAgentStore';

export function TaskInput() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedRootAgent, setSelectedRootAgent] = useState('');
  const [selectedChannel, setSelectedChannel] = useState('');
  const [channels, setChannels] = useState<string[]>([]);
  const submitTask = useTaskStore((s) => s.submitTask);
  const { definitions, fetchDefinitions } = useRootAgentStore();

  useEffect(() => { fetchDefinitions(); }, [fetchDefinitions]);

  useEffect(() => {
    fetch('/api/interactions/channels').then(r => r.json()).then(d => {
      if (d.channels) setChannels(d.channels);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (definitions.length > 0 && !selectedRootAgent) {
      setSelectedRootAgent(definitions[0].name);
    }
  }, [definitions, selectedRootAgent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    setLoading(true);
    try {
      await submitTask(input.trim(), selectedRootAgent || undefined, selectedChannel || undefined);
      setInput('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
      <select
        value={selectedRootAgent}
        onChange={(e) => setSelectedRootAgent(e.target.value)}
        style={{
          padding: '0.625rem 0.75rem',
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 6,
          color: '#e2e8f0',
          fontSize: '0.9rem',
          outline: 'none',
          minWidth: 160,
        }}
      >
        {definitions.map((d: RootAgentDefinition) => (
          <option key={d.name} value={d.name}>{d.name}</option>
        ))}
      </select>
      {channels.length > 1 && (
        <select
          value={selectedChannel}
          onChange={(e) => setSelectedChannel(e.target.value)}
          style={{
            padding: '0.625rem 0.75rem',
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 6,
            color: '#e2e8f0',
            fontSize: '0.9rem',
            outline: 'none',
            minWidth: 120,
          }}
        >
          <option value="">web_ui</option>
          {channels.filter(c => c !== 'web_ui').map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      )}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Describe a task for the agent..."
        disabled={loading}
        style={{
          flex: 1,
          padding: '0.625rem 1rem',
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 6,
          color: '#e2e8f0',
          fontSize: '1.3rem',
          outline: 'none',
        }}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        style={{
          padding: '0.625rem 1.5rem',
          background: '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          cursor: loading ? 'wait' : 'pointer',
          opacity: loading || !input.trim() ? 0.5 : 1,
          fontSize: '1.3rem',
        }}
      >
        {loading ? 'Sending...' : 'Submit'}
      </button>
    </form>
  );
}
