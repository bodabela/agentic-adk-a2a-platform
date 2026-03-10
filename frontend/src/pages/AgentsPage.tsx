import { useEffect, useState } from 'react';
import { useAgentStore, type AgentDefinition } from '../stores/agentStore';

const cardStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 8,
  padding: '1rem',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
};

const activeCardStyle: React.CSSProperties = {
  ...cardStyle,
  borderColor: '#38bdf8',
};

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
  minHeight: 300,
  fontFamily: 'monospace',
  fontSize: '0.85rem',
  background: '#0f172a',
  color: '#e2e8f0',
  border: '1px solid #334155',
  borderRadius: 6,
  padding: '0.75rem',
  resize: 'vertical',
};

export function AgentsPage() {
  const { agents, selectedAgent, loading, fetchAgents, fetchAgentDetail, updateAgent, deleteAgent, createAgent, clearSelection } = useAgentStore();
  const [activeTab, setActiveTab] = useState<'overview' | 'yaml' | 'prompt'>('overview');
  const [editYaml, setEditYaml] = useState('');
  const [editPrompt, setEditPrompt] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newYaml, setNewYaml] = useState('agent:\n  name: ""\n  description: ""\n  model: "gemini-2.5-flash"\n  instruction: "prompts/system_prompt.md"\n  capabilities: []\n  tools:\n    mcp: []\n    builtin: []\n');
  const [newPrompt, setNewPrompt] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  useEffect(() => {
    if (selectedAgent) {
      setEditYaml(selectedAgent.yaml_content);
      setEditPrompt(selectedAgent.prompt_content);
    }
  }, [selectedAgent]);

  const handleSelect = (name: string) => {
    fetchAgentDetail(name);
    setActiveTab('overview');
    setError('');
  };

  const handleSave = async () => {
    if (!selectedAgent) return;
    try {
      setError('');
      await updateAgent(selectedAgent.name, editYaml, editPrompt);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const handleDelete = async () => {
    if (!selectedAgent || !confirm(`Delete agent "${selectedAgent.name}"?`)) return;
    try {
      await deleteAgent(selectedAgent.name);
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const handleCreate = async () => {
    try {
      setError('');
      await createAgent(newName, newYaml, newPrompt);
      setShowCreate(false);
      setNewName('');
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '1.5rem', height: '100%', padding: '1.5rem' }}>
      {/* Left: Agent list */}
      <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '1.2rem' }}>Agents</h2>
          <button style={primaryBtn} onClick={() => setShowCreate(true)}>+ New</button>
        </div>

        {loading && <div style={{ color: '#94a3b8' }}>Loading...</div>}

        {agents.map((a: AgentDefinition) => (
          <div
            key={a.name}
            style={selectedAgent?.name === a.name ? activeCardStyle : cardStyle}
            onClick={() => handleSelect(a.name)}
          >
            <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{a.name}</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{a.category} | {a.model}</div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 4 }}>
              {a.capabilities.join(', ')}
            </div>
          </div>
        ))}
      </div>

      {/* Right: Detail panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {error && (
          <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '0.75rem', borderRadius: 6 }}>
            {error}
          </div>
        )}

        {showCreate && (
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, padding: '1.5rem' }}>
            <h3 style={{ color: '#e2e8f0', margin: '0 0 1rem' }}>Create New Agent</h3>
            <input
              placeholder="Agent name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{ ...textareaStyle, minHeight: 'auto', marginBottom: '0.75rem' }}
            />
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>agent.yaml</label>
            <textarea value={newYaml} onChange={(e) => setNewYaml(e.target.value)} style={textareaStyle} />
            <label style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.5rem', display: 'block' }}>system_prompt.md</label>
            <textarea value={newPrompt} onChange={(e) => setNewPrompt(e.target.value)} style={{ ...textareaStyle, minHeight: 150 }} />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button style={primaryBtn} onClick={handleCreate}>Create</button>
              <button style={secondaryBtn} onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </div>
        )}

        {selectedAgent && !showCreate && (
          <>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {(['overview', 'yaml', 'prompt'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    ...secondaryBtn,
                    background: activeTab === tab ? '#38bdf8' : '#334155',
                    color: activeTab === tab ? '#0f172a' : '#e2e8f0',
                  }}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
              <div style={{ flex: 1 }} />
              <button style={primaryBtn} onClick={handleSave}>Save</button>
              <button style={dangerBtn} onClick={handleDelete}>Delete</button>
            </div>

            {/* Tab content */}
            {activeTab === 'overview' && selectedAgent.definition && (
              <div style={{ background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155' }}>
                <h3 style={{ color: '#e2e8f0', margin: '0 0 1rem' }}>{selectedAgent.definition.name}</h3>
                <p style={{ color: '#94a3b8' }}>{selectedAgent.definition.description}</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '1rem' }}>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Model</div>
                    <div style={{ color: '#e2e8f0' }}>{selectedAgent.definition.model}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Category</div>
                    <div style={{ color: '#e2e8f0' }}>{selectedAgent.definition.category}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Capabilities</div>
                    <div style={{ color: '#e2e8f0' }}>{selectedAgent.definition.capabilities.join(', ')}</div>
                  </div>
                  <div>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Builtin Tools</div>
                    <div style={{ color: '#e2e8f0' }}>{selectedAgent.definition.tools.builtin.join(', ') || 'none'}</div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'yaml' && (
              <textarea value={editYaml} onChange={(e) => setEditYaml(e.target.value)} style={textareaStyle} />
            )}

            {activeTab === 'prompt' && (
              <textarea value={editPrompt} onChange={(e) => setEditPrompt(e.target.value)} style={textareaStyle} />
            )}
          </>
        )}

        {!selectedAgent && !showCreate && (
          <div style={{ color: '#64748b', textAlign: 'center', marginTop: '4rem' }}>
            Select an agent to view details, or create a new one.
          </div>
        )}
      </div>
    </div>
  );
}
