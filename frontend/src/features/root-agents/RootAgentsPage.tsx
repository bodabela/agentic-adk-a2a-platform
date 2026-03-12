import { useEffect, useState } from 'react';
import { useRootAgentStore } from './rootAgentStore';

const btnStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  borderRadius: 6,
  border: 'none',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: '0.85rem',
};
const primaryBtn: React.CSSProperties = { ...btnStyle, background: '#38bdf8', color: '#0f172a' };
const dangerBtn: React.CSSProperties = { ...btnStyle, background: '#ef4444', color: '#fff' };
const secondaryBtn: React.CSSProperties = { ...btnStyle, background: '#334155', color: '#e2e8f0' };

const textareaStyle: React.CSSProperties = {
  width: '100%',
  minHeight: 250,
  fontFamily: 'monospace',
  fontSize: '0.85rem',
  background: '#0f172a',
  color: '#e2e8f0',
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '0.75rem',
  resize: 'vertical',
};

const cardStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 8,
  padding: '1rem',
};

const DEFAULT_YAML = `root_agent:
  name: ""
  description: ""
  model: "gemini-2.5-flash"
  orchestration:
    strategy: "loop"
    max_iterations: 10
  sub_agents:
    - "coder_agent"
    - "user_agent"
  instruction: |
    You are the orchestrator agent.
  generate_content_config:
    thinking: true
`;

export function RootAgentsPage() {
  const {
    definitions, instances, selectedDefinition, loading,
    fetchDefinitions, fetchDefinitionDetail, createDefinition, updateDefinition, deleteDefinition,
    fetchInstances, startInstance, stopInstance, clearSelection,
  } = useRootAgentStore();

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newYaml, setNewYaml] = useState(DEFAULT_YAML);
  const [editYaml, setEditYaml] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { fetchDefinitions(); fetchInstances(); }, [fetchDefinitions, fetchInstances]);

  useEffect(() => {
    if (selectedDefinition) setEditYaml(selectedDefinition.yaml_content);
  }, [selectedDefinition]);

  const handleCreate = async () => {
    try {
      setError('');
      await createDefinition(newName, newYaml);
      setShowCreate(false);
      setNewName('');
    } catch (e: unknown) { setError((e as Error).message); }
  };

  const handleSave = async () => {
    if (!selectedDefinition) return;
    try {
      setError('');
      await updateDefinition(selectedDefinition.name, editYaml);
    } catch (e: unknown) { setError((e as Error).message); }
  };

  const handleDelete = async () => {
    if (!selectedDefinition || !confirm(`Delete "${selectedDefinition.name}"?`)) return;
    try {
      await deleteDefinition(selectedDefinition.name);
      clearSelection();
    } catch (e: unknown) { setError((e as Error).message); }
  };

  return (
    <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {error && (
        <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '0.75rem', borderRadius: 6 }}>
          {error}
        </div>
      )}

      {/* Definitions */}
      <section>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, color: '#e2e8f0' }}>Root Agent Definitions</h2>
          <button style={primaryBtn} onClick={() => setShowCreate(true)}>+ New</button>
        </div>

        {showCreate && (
          <div style={{ ...cardStyle, marginBottom: '1rem' }}>
            <input
              placeholder="Definition name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{ ...textareaStyle, minHeight: 'auto', marginBottom: '0.75rem' }}
            />
            <textarea value={newYaml} onChange={(e) => setNewYaml(e.target.value)} style={textareaStyle} />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button style={primaryBtn} onClick={handleCreate}>Create</button>
              <button style={secondaryBtn} onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </div>
        )}

        {loading && <div style={{ color: '#94a3b8' }}>Loading...</div>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
          {definitions.map((d) => (
            <div
              key={d.name}
              style={{ ...cardStyle, cursor: 'pointer', borderColor: selectedDefinition?.name === d.name ? '#38bdf8' : '#334155' }}
              onClick={() => fetchDefinitionDetail(d.name)}
            >
              <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{d.name}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{d.description}</div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 4 }}>
                {d.model} | max {d.max_iterations} iter | agents: {d.sub_agents.join(', ')}
              </div>
            </div>
          ))}
        </div>

        {selectedDefinition && (
          <div style={{ ...cardStyle, marginTop: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3 style={{ color: '#e2e8f0', margin: 0 }}>Edit: {selectedDefinition.name}</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button style={primaryBtn} onClick={handleSave}>Save</button>
                <button style={dangerBtn} onClick={handleDelete}>Delete</button>
              </div>
            </div>
            <textarea value={editYaml} onChange={(e) => setEditYaml(e.target.value)} style={textareaStyle} />
          </div>
        )}
      </section>

      {/* Instances */}
      <section>
        <h2 style={{ color: '#e2e8f0', marginBottom: '1rem' }}>Running Instances</h2>

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          {definitions.map((d) => (
            <button key={d.name} style={secondaryBtn} onClick={() => startInstance(d.name)}>
              Start {d.name}
            </button>
          ))}
        </div>

        {instances.length === 0 && <div style={{ color: '#64748b' }}>No running instances.</div>}

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #334155' }}>
              {['Instance ID', 'Definition', 'Status', 'Started', 'Tasks', ''].map((h) => (
                <th key={h} style={{ textAlign: 'left', padding: '0.5rem', color: '#94a3b8', fontSize: '0.8rem' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {instances.map((inst) => (
              <tr key={inst.instance_id} style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: '0.5rem', color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {inst.instance_id.slice(0, 8)}...
                </td>
                <td style={{ padding: '0.5rem', color: '#e2e8f0' }}>{inst.definition_name}</td>
                <td style={{ padding: '0.5rem' }}>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: '0.75rem',
                    background: inst.status === 'running' ? '#166534' : '#334155',
                    color: inst.status === 'running' ? '#86efac' : '#94a3b8',
                  }}>
                    {inst.status}
                  </span>
                </td>
                <td style={{ padding: '0.5rem', color: '#94a3b8', fontSize: '0.8rem' }}>
                  {new Date(inst.started_at).toLocaleTimeString()}
                </td>
                <td style={{ padding: '0.5rem', color: '#94a3b8' }}>{inst.task_ids.length}</td>
                <td style={{ padding: '0.5rem' }}>
                  <button style={dangerBtn} onClick={() => stopInstance(inst.instance_id)}>Stop</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
