import { useState, useEffect } from 'react';
import { FlowStatus } from '../components/flow/FlowStatus';
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
  fontSize: '0.875rem',
  outline: 'none',
  flex: 1,
};

export function FlowsPage() {
  const [availableFlows, setAvailableFlows] = useState<FlowInfo[]>([]);
  const [flowFile, setFlowFile] = useState('');
  const [triggerInput, setTriggerInput] = useState('');
  const [loading, setLoading] = useState(false);
  const startFlow = useFlowStore((s) => s.startFlow);

  // LLM provider/model state
  const [providersData, setProvidersData] = useState<Record<string, ProviderInfo>>({});
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  // Fetch available flows on mount
  useEffect(() => {
    fetch('/api/flows/')
      .then((r) => r.json())
      .then((data: { flows: FlowInfo[] }) => {
        setAvailableFlows(data.flows);
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
      .catch(() => {
        // API not available yet
      });
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
      );
      setFlowFile('');
      setTriggerInput('');
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
  };

  const currentModels = selectedProvider && providersData[selectedProvider]
    ? providersData[selectedProvider].models
    : {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
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
              fontSize: '0.875rem',
              outline: 'none',
              resize: 'vertical',
              fontFamily: 'monospace',
            }}
          />

          {/* LLM Provider / Model selectors */}
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
              fontSize: '0.875rem',
              alignSelf: 'flex-start',
            }}
          >
            {loading ? 'Starting...' : 'Start Flow'}
          </button>
        </form>
      </div>

      <FlowStatus />
    </div>
  );
}
