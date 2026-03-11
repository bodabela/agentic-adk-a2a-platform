import { useState, useEffect, useRef } from 'react';
import { FlowStatus, MultiQuestionForm } from '../components/flow/FlowStatus';
import { FlowDiagram, type FlowDefinitionData } from '../components/flow/FlowDiagram';
import { useFlowStore } from '../stores/flowStore';

interface FlowInfo {
  name: string;
  file: string;
  description: string;
  default_input: Record<string, unknown>;
}

interface ProviderInfo {
  display_name: string;
  available: boolean;
  models: Record<string, { display_name: string; max_tokens: number }>;
}

interface ProvidersResponse {
  defaults: { provider: string; model: string };
  providers: Record<string, ProviderInfo>;
}

const selectStyle: React.CSSProperties = {
  padding: '0.625rem 1rem',
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: 6,
  color: '#e2e8f0',
  fontSize: '1.3rem',
  outline: 'none',
  flex: 1,
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

const yamlTextareaStyle: React.CSSProperties = {
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

const cardStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 8,
  padding: '1rem',
};

export function FlowsPage() {
  const [availableFlows, setAvailableFlows] = useState<FlowInfo[]>([]);
  const [flowFile, setFlowFile] = useState('');
  const [triggerInput, setTriggerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const startFlow = useFlowStore((s) => s.startFlow);
  const pendingInteractions = useFlowStore((s) => s.pendingInteractions);
  const resolveInteraction = useFlowStore((s) => s.resolveInteraction);
  const [freeTextValues, setFreeTextValues] = useState<Record<string, string>>({});
  const [multiAnswers, setMultiAnswers] = useState<Record<string, Record<string, string>>>({});
  const eventDetailRef = useRef<HTMLDivElement>(null);

  // YAML editing state
  const [editingFlow, setEditingFlow] = useState<string | null>(null);
  const [editYaml, setEditYaml] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newFlowName, setNewFlowName] = useState('');
  const [newFlowYaml, setNewFlowYaml] = useState('');
  const [yamlError, setYamlError] = useState('');

  // LLM provider/model state
  const [providersData, setProvidersData] = useState<Record<string, ProviderInfo>>({});
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  // Channel state
  const [channels, setChannels] = useState<string[]>([]);
  const [selectedChannel, setSelectedChannel] = useState('');

  // Flow diagram definition
  const [flowDefinition, setFlowDefinition] = useState<FlowDefinitionData | null>(null);
  const [diagramLoading, setDiagramLoading] = useState(false);

  // Agent model map: { agentName: { model, provider? } }
  const [agentModels, setAgentModels] = useState<Record<string, { model: string }>>({});

  // Fetch available flows + agent models + channels on mount
  useEffect(() => {
    fetch('/api/flows/')
      .then((r) => r.json())
      .then((data: { flows: FlowInfo[] }) => {
        setAvailableFlows(data.flows);
      })
      .catch(() => {});
    fetch('/api/interactions/channels')
      .then((r) => r.json())
      .then((d) => { if (d.channels) setChannels(d.channels); })
      .catch(() => {});
    fetch('/api/agents/')
      .then((r) => r.json())
      .then((data: { agents: { name: string; model: string }[] }) => {
        const map: Record<string, { model: string }> = {};
        for (const a of data.agents) {
          if (a.model) map[a.name] = { model: a.model };
        }
        setAgentModels(map);
      })
      .catch(() => {});
  }, []);

  // Fetch providers on mount
  useEffect(() => {
    fetch('/api/llm/providers')
      .then((r) => r.json())
      .then((data: ProvidersResponse) => {
        setProvidersData(data.providers);
        setSelectedProvider(data.defaults.provider);
        setSelectedModel(data.defaults.model);
      })
      .catch(() => {});
  }, []);

  // When provider changes, reset model to first available
  useEffect(() => {
    if (selectedProvider && providersData[selectedProvider]) {
      const models = Object.keys(providersData[selectedProvider].models);
      if (models.length > 0 && !models.includes(selectedModel)) {
        setSelectedModel(models[0]);
      }
    }
  }, [selectedProvider, providersData]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!flowFile.trim() || loading) return;
    setLoading(true);
    try {
      let triggerData = {};
      if (triggerInput.trim()) {
        try {
          triggerData = JSON.parse(triggerInput.trim());
        } catch {
          alert('Invalid JSON in trigger data');
          return;
        }
      }
      await startFlow(
        flowFile.trim(),
        triggerData,
        selectedProvider || undefined,
        selectedModel || undefined,
        selectedChannel || undefined,
      );
    } finally {
      setLoading(false);
    }
  };

  const handleFlowChange = (file: string) => {
    setFlowFile(file);
    const flow = availableFlows.find((f) => f.file === file);
    if (flow && Object.keys(flow.default_input).length > 0) {
      setTriggerInput(JSON.stringify(flow.default_input, null, 2));
    } else {
      setTriggerInput('');
    }

    // Fetch full flow definition for diagram
    if (file) {
      setDiagramLoading(true);
      fetch(`/api/flows/definition/${encodeURIComponent(file)}`)
        .then((r) => r.json())
        .then((data: FlowDefinitionData) => {
          setFlowDefinition(data);
        })
        .catch(() => {
          setFlowDefinition(null);
        })
        .finally(() => setDiagramLoading(false));
    } else {
      setFlowDefinition(null);
    }
  };

  const refreshFlows = () => {
    fetch('/api/flows/')
      .then((r) => r.json())
      .then((data: { flows: FlowInfo[] }) => setAvailableFlows(data.flows))
      .catch(() => {});
  };

  const handleEditYaml = async (file: string) => {
    setYamlError('');
    try {
      const res = await fetch(`/api/flows/raw/${encodeURIComponent(file)}`);
      if (!res.ok) throw new Error('Failed to load flow YAML');
      const data = await res.json();
      setEditYaml(data.content);
      setEditingFlow(file);
    } catch (e: unknown) { setYamlError((e as Error).message); }
  };

  const handleSaveYaml = async () => {
    if (!editingFlow) return;
    setYamlError('');
    try {
      const res = await fetch(`/api/flows/${encodeURIComponent(editingFlow)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editYaml }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to save flow');
      }
      setEditingFlow(null);
      refreshFlows();
    } catch (e: unknown) { setYamlError((e as Error).message); }
  };

  const handleCreateFlow = async () => {
    if (!newFlowName.trim() || !newFlowYaml.trim()) return;
    setYamlError('');
    try {
      const filename = newFlowName.endsWith('.yaml') ? newFlowName : `${newFlowName}.yaml`;
      const res = await fetch('/api/flows/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, content: newFlowYaml }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create flow');
      }
      setShowCreate(false);
      setNewFlowName('');
      setNewFlowYaml('');
      refreshFlows();
    } catch (e: unknown) { setYamlError((e as Error).message); }
  };

  const handleDeleteFlow = async (file: string) => {
    if (!confirm(`Delete flow "${file}"?`)) return;
    setYamlError('');
    try {
      const res = await fetch(`/api/flows/${encodeURIComponent(file)}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to delete flow');
      }
      if (editingFlow === file) setEditingFlow(null);
      if (flowFile === file) setFlowFile('');
      refreshFlows();
    } catch (e: unknown) { setYamlError((e as Error).message); }
  };

  // Find the active flow matching the selected flow to track current state + tool usage
  const activeFlows = useFlowStore((s) => s.activeFlows);
  const matchingFlow = (() => {
    if (!flowDefinition) return undefined;
    const matching = Object.values(activeFlows)
      .filter((f) => f.flowName === flowDefinition.name)
      .reverse();
    return matching.find((f) => f.status === 'running') || matching[0];
  })();
  const activeState = matchingFlow?.currentState || undefined;

  // Derive the previous state (the state before the current one) for edge highlighting
  const previousState: string | undefined = (() => {
    if (!matchingFlow || !activeState) return undefined;
    const stateEntries = matchingFlow.events
      .filter((e) => e.event_type === 'flow_state_entered')
      .map((e) => e.data.state as string);
    // Find the state just before the current active one
    for (let i = stateEntries.length - 1; i >= 0; i--) {
      if (stateEntries[i] === activeState && i > 0) {
        return stateEntries[i - 1];
      }
    }
    return undefined;
  })();

  // Compute per-state tool usage counts from events: { [stateName]: { [toolName]: count } }
  const toolUsageByState: Record<string, Record<string, number>> = (() => {
    if (!matchingFlow) return {};
    const result: Record<string, Record<string, number>> = {};
    let currentSt = '';
    for (const evt of matchingFlow.events) {
      if (evt.event_type === 'flow_state_entered') {
        currentSt = evt.data.state as string;
      } else if (evt.event_type === 'flow_agent_tool_use' && currentSt) {
        const tool = evt.data.tool_name as string;
        if (!result[currentSt]) result[currentSt] = {};
        result[currentSt][tool] = (result[currentSt][tool] || 0) + 1;
      }
    }
    return result;
  })();

  // Auto-scroll event detail to bottom when new content arrives
  useEffect(() => {
    const el = eventDetailRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [matchingFlow?.events.length]);

  const currentModels = selectedProvider && providersData[selectedProvider]
    ? providersData[selectedProvider].models
    : {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top section: form on left, diagram on right */}
      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>
        {/* Left panel – Start Flow form */}
        <div style={{ width: "50%", flexShrink: 0 }}>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Start Flow
          </h2>
          <form onSubmit={handleStart} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <select
              value={flowFile}
              onChange={(e) => handleFlowChange(e.target.value)}
              disabled={loading}
              style={selectStyle}
            >
              <option value="">-- Select a flow --</option>
              {availableFlows.map((flow) => (
                <option key={flow.file} value={flow.file}>
                  {flow.name}{flow.description ? ` – ${flow.description}` : ''}
                </option>
              ))}
            </select>
            <textarea
              value={triggerInput}
              onChange={(e) => setTriggerInput(e.target.value)}
              placeholder='Trigger data (JSON, optional): {"task_description": "..."}'
              disabled={loading}
              rows={3}
              style={{
                padding: '0.625rem 1rem',
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 6,
                color: '#e2e8f0',
                fontSize: '1.3rem',
                outline: 'none',
                resize: 'vertical',
                fontFamily: 'monospace',
              }}
            />

            {/* LLM Provider / Model / Channel selectors */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                disabled={loading}
                style={selectStyle}
              >
                {Object.entries(providersData).map(([key, info]) => (
                  <option key={key} value={key} disabled={!info.available}>
                    {info.display_name}{!info.available ? ' (no API key)' : ''}
                  </option>
                ))}
              </select>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={loading}
                style={selectStyle}
              >
                {Object.entries(currentModels).map(([key, info]) => (
                  <option key={key} value={key}>
                    {info.display_name}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {channels.length > 1 && (
                <select
                  value={selectedChannel}
                  onChange={(e) => setSelectedChannel(e.target.value)}
                  disabled={loading}
                  style={{
                    padding: '0.5rem 0.75rem',
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: 6,
                    color: '#e2e8f0',
                    fontSize: '0.9rem',
                    outline: 'none',
                  }}
                >
                  <option value="">web_ui</option>
                  {channels.filter(c => c !== 'web_ui').map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              )}
              <button
                type="submit"
                disabled={loading || !flowFile.trim()}
                style={{
                  padding: '0.625rem 1.5rem',
                  background: '#7c3aed',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: loading ? 'wait' : 'pointer',
                  opacity: loading || !flowFile.trim() ? 0.5 : 1,
                  fontSize: '1.3rem',
                }}
              >
                {loading ? 'Starting...' : 'Start Flow'}
              </button>
            </div>
          </form>

          {/* Current event – live detail of the latest event */}
          {matchingFlow && matchingFlow.events.length > 0 && (() => {
            const evt = matchingFlow.events[matchingFlow.events.length - 1];
            const time = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : '';
            const agent = (evt.data.agent as string) || (evt.data.author as string) || '';
            const rawModel = (evt.data.model as string) || '';
            const rawProvider = (evt.data.provider as string) || '';
            const evtModel = rawProvider && rawModel ? `${rawProvider}/${rawModel}` : rawModel;

            let eventColor = '#60a5fa';
            let borderColor = '#1e293b';
            if (evt.event_type === 'flow_agent_thinking') {
              eventColor = '#a78bfa'; borderColor = '#2e1065';
            } else if (evt.event_type === 'flow_agent_tool_use') {
              eventColor = '#fbbf24'; borderColor = '#451a03';
            } else if (evt.event_type === 'flow_agent_tool_result') {
              eventColor = '#34d399'; borderColor = '#064e3b';
            } else if (evt.event_type === 'flow_agent_streaming_text') {
              eventColor = '#22d3ee'; borderColor = '#164e63';
            } else if (evt.event_type === 'flow_completed') {
              eventColor = '#4ade80'; borderColor = '#14532d';
            } else if (evt.event_type === 'flow_started') {
              eventColor = '#818cf8'; borderColor = '#312e81';
            }

            const d = evt.data;
            let summary = evt.event_type;
            switch (evt.event_type) {
              case 'flow_started':
                summary = `Flow "${d.flow_name}" started`; break;
              case 'flow_state_entered':
                summary = `Entered state: ${d.state} (${d.node_type})`; break;
              case 'flow_agent_task_started': {
                const input = d.input as Record<string, unknown> | undefined;
                const inputStr = input ? JSON.stringify(input, null, 2) : '';
                summary = `Agent "${d.agent}" started\n${inputStr}`; break;
              }
              case 'flow_agent_task_completed': {
                const files = (d.workspace_files as string[]) || [];
                const fileLine = files.length > 0 ? `\nFiles: ${files.join(', ')}` : '';
                summary = `Agent "${d.agent}" completed${d.output_summary ? `\n${d.output_summary}` : ''}${fileLine}`; break;
              }
              case 'flow_agent_thinking':
                summary = `${d.is_thought ? 'thought' : 'thinking'}: ${d.text}`; break;
              case 'flow_agent_tool_use':
                summary = `calling tool: ${d.tool_name}(${JSON.stringify(d.tool_args || {})})`; break;
              case 'flow_agent_tool_result': {
                const resp = typeof d.tool_response === 'string'
                  ? d.tool_response
                  : JSON.stringify(d.tool_response || '', null, 2);
                const truncated = resp.length > 400 ? resp.slice(0, 400) + '...' : resp;
                summary = `tool result [${d.tool_name}]: ${truncated}`; break;
              }
              case 'flow_agent_streaming_text':
                summary = String(d.text || ''); break;
              case 'flow_llm_decision':
                summary = `LLM decision: ${d.decision}${d.reason ? ` — ${d.reason}` : ''}`; break;
              case 'flow_input_required':
                summary = `Waiting for user input: ${d.prompt || d.interaction_type}`; break;
              case 'flow_user_response':
                summary = `User responded: ${d.response}`; break;
              case 'flow_completed': {
                summary = `Flow completed (${d.status})`;
                const output = d.output as Record<string, unknown> | undefined;
                if (output?.result) {
                  const resultStr = typeof output.result === 'string'
                    ? output.result
                    : JSON.stringify(output.result, null, 2);
                  summary += `\n\n${resultStr}`;
                }
                break;
              }
              case 'flow_retry_exceeded':
                summary = `Retry limit exceeded: ${d.loop}`; break;
            }

            return (
              <div
                ref={eventDetailRef}
                style={{
                  marginTop: '0.75rem',
                  padding: '0.5rem 0.625rem',
                  background: '#020617',
                  border: `1px solid ${borderColor}`,
                  borderRadius: 6,
                  fontFamily: 'monospace',
                  maxHeight: 200,
                  overflowY: 'auto',
                }}
              >
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span style={{ color: '#475569', fontSize: '1.05rem' }}>{time}</span>
                  <span style={{ color: eventColor, fontSize: '1.05rem' }}>{evt.event_type}</span>
                  {agent && <span style={{ color: '#a78bfa', fontSize: '1.05rem' }}>{agent}</span>}
                  {evtModel && <span style={{ color: '#64748b', fontSize: '1.05rem' }}>[{evtModel}]</span>}
                </div>
                <div style={{ color: '#94a3b8', fontSize: '1.05rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {summary}
                </div>
              </div>
            );
          })()}

          {/* Pending Interactions – below form */}
          {pendingInteractions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              <h3 style={{ color: '#f59e0b', fontSize: '1rem', margin: 0 }}>Agent Questions</h3>
              {pendingInteractions.map((interaction) => (
                <div
                  key={interaction.interaction_id}
                  style={{
                    background: '#1c1917',
                    border: '1px solid #f59e0b',
                    borderRadius: 8,
                    padding: '1rem',
                  }}
                >
                  <div style={{ color: '#e2e8f0', marginBottom: '0.75rem' }}>
                    {interaction.prompt || 'The agent has a question. Please provide more details.'}
                  </div>

                  {interaction.interaction_type === 'multi_question' && interaction.questions && interaction.questions.length > 0 ? (
                    <MultiQuestionForm
                      interaction={interaction}
                      answers={multiAnswers[interaction.interaction_id] ?? {}}
                      onAnswerChange={(questionId, value) =>
                        setMultiAnswers((prev) => ({
                          ...prev,
                          [interaction.interaction_id]: {
                            ...prev[interaction.interaction_id],
                            [questionId]: value,
                          },
                        }))
                      }
                      onSubmit={async () => {
                        const answers = multiAnswers[interaction.interaction_id] ?? {};
                        await fetch('/api/flows/interact', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            interaction_id: interaction.interaction_id,
                            response: answers,
                          }),
                        });
                        resolveInteraction(interaction.interaction_id);
                        setMultiAnswers((prev) => {
                          const next = { ...prev };
                          delete next[interaction.interaction_id];
                          return next;
                        });
                      }}
                    />
                  ) : interaction.options && interaction.options.length > 0 ? (
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {interaction.options.map((opt) => (
                        <button
                          key={opt.id}
                          onClick={async () => {
                            await fetch('/api/flows/interact', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                interaction_id: interaction.interaction_id,
                                response: { id: opt.id },
                              }),
                            });
                            resolveInteraction(interaction.interaction_id);
                          }}
                          style={{
                            padding: '0.5rem 1rem',
                            background: opt.recommended ? '#2563eb' : '#334155',
                            color: '#e2e8f0',
                            border: 'none',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: '1.2rem',
                          }}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <form
                      style={{ display: 'flex', gap: '0.5rem' }}
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const text = freeTextValues[interaction.interaction_id] ?? '';
                        if (!text.trim()) return;
                        await fetch('/api/flows/interact', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            interaction_id: interaction.interaction_id,
                            response: text,
                          }),
                        });
                        resolveInteraction(interaction.interaction_id);
                        setFreeTextValues((prev) => {
                          const next = { ...prev };
                          delete next[interaction.interaction_id];
                          return next;
                        });
                      }}
                    >
                      <input
                        type="text"
                        placeholder="Type your response..."
                        value={freeTextValues[interaction.interaction_id] ?? ''}
                        onChange={(e) =>
                          setFreeTextValues((prev) => ({
                            ...prev,
                            [interaction.interaction_id]: e.target.value,
                          }))
                        }
                        style={{
                          flex: 1,
                          padding: '0.5rem 0.75rem',
                          background: '#1e293b',
                          border: '1px solid #475569',
                          borderRadius: 6,
                          color: '#e2e8f0',
                          fontSize: '1.275rem',
                          outline: 'none',
                        }}
                      />
                      <button
                        type="submit"
                        style={{
                          padding: '0.5rem 1rem',
                          background: '#f59e0b',
                          color: '#1c1917',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontSize: '1.2rem',
                          fontWeight: 600,
                        }}
                      >
                        Send
                      </button>
                    </form>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right panel – Flow Diagram */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {diagramLoading ? (
            <div style={{ color: '#64748b', padding: '2rem', textAlign: 'center' }}>
              Loading flow diagram...
            </div>
          ) : flowDefinition ? (
            <FlowDiagram definition={flowDefinition} activeState={activeState} previousState={previousState} flowStatus={matchingFlow?.status} toolUsageByState={toolUsageByState} agentModels={agentModels} />
          ) : (
            <div style={{
              color: '#475569',
              padding: '3rem 2rem',
              textAlign: 'center',
              background: '#020617',
              borderRadius: 8,
              border: '1px solid #1e293b',
            }}>
              Select a flow to see its diagram
            </div>
          )}
        </div>
      </div>

      {/* Flow YAML Management */}
      <section style={{ ...cardStyle, marginTop: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '1.1rem' }}>Flow Definitions</h2>
          <button style={primaryBtn} onClick={() => { setShowCreate(true); setYamlError(''); }}>+ New Flow</button>
        </div>

        {yamlError && (
          <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '0.75rem', borderRadius: 6, marginBottom: '0.75rem' }}>
            {yamlError}
          </div>
        )}

        {showCreate && (
          <div style={{ ...cardStyle, marginBottom: '1rem', borderColor: '#38bdf8' }}>
            <input
              placeholder="Flow filename (e.g. my_flow.yaml)"
              value={newFlowName}
              onChange={(e) => setNewFlowName(e.target.value)}
              style={{ ...yamlTextareaStyle, minHeight: 'auto', marginBottom: '0.75rem' }}
            />
            <textarea
              value={newFlowYaml}
              onChange={(e) => setNewFlowYaml(e.target.value)}
              placeholder="Paste flow YAML content here..."
              style={yamlTextareaStyle}
            />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button style={primaryBtn} onClick={handleCreateFlow}>Create</button>
              <button style={secondaryBtn} onClick={() => { setShowCreate(false); setNewFlowName(''); setNewFlowYaml(''); }}>Cancel</button>
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0.75rem' }}>
          {availableFlows.map((flow) => (
            <div key={flow.file} style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{flow.name}</div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{flow.description || flow.file}</div>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: 'auto' }}>
                <button style={secondaryBtn} onClick={() => handleEditYaml(flow.file)}>Edit YAML</button>
                <button style={dangerBtn} onClick={() => handleDeleteFlow(flow.file)}>Delete</button>
              </div>
            </div>
          ))}
        </div>

        {editingFlow && (
          <div style={{ ...cardStyle, marginTop: '1rem', borderColor: '#38bdf8' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3 style={{ color: '#e2e8f0', margin: 0 }}>Edit: {editingFlow}</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button style={primaryBtn} onClick={handleSaveYaml}>Save</button>
                <button style={secondaryBtn} onClick={() => setEditingFlow(null)}>Cancel</button>
              </div>
            </div>
            <textarea value={editYaml} onChange={(e) => setEditYaml(e.target.value)} style={yamlTextareaStyle} />
          </div>
        )}
      </section>

      {/* Full-width section below */}
      <FlowStatus />
    </div>
  );
}
