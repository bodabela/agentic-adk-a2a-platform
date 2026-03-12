import { useEffect, useState } from 'react';

interface ObservabilityConfig {
  tracing_enabled: boolean;
  grafana_base_url: string;
  langfuse_enabled: boolean;
  langfuse_base_url: string;
}

let cachedConfig: ObservabilityConfig | null = null;

async function fetchConfig(): Promise<ObservabilityConfig> {
  if (cachedConfig) return cachedConfig;
  try {
    const res = await fetch('/api/traces/config');
    cachedConfig = await res.json();
    return cachedConfig!;
  } catch {
    return { tracing_enabled: false, grafana_base_url: '', langfuse_enabled: false, langfuse_base_url: '' };
  }
}

interface TraceLinksProps {
  traceId: string | undefined;
  entityType: 'task' | 'flow';
  entityId: string;
}

export function TraceLinks({ traceId, entityType, entityId }: TraceLinksProps) {
  const [config, setConfig] = useState<ObservabilityConfig | null>(cachedConfig);

  useEffect(() => {
    if (!cachedConfig) {
      fetchConfig().then(setConfig);
    }
  }, []);

  if (!traceId || !config?.tracing_enabled) return null;

  const grafanaUrl = config.grafana_base_url
    ? `${config.grafana_base_url}/explore?left=${encodeURIComponent(
        JSON.stringify({
          datasource: 'tempo',
          queries: [{ refId: 'A', queryType: 'traceql', query: `{resource.service.name="agent-platform" && span.${entityType}.id="${entityId}"}` }],
          range: { from: 'now-1h', to: 'now' },
        })
      )}`
    : '';

  const langfuseUrl = config.langfuse_enabled && config.langfuse_base_url
    ? `${config.langfuse_base_url}/trace/${traceId}`
    : '';

  return (
    <span style={{ display: 'inline-flex', gap: 6, marginLeft: 8 }}>
      {grafanaUrl && (
        <a
          href={grafanaUrl}
          target="_blank"
          rel="noopener noreferrer"
          title="View trace in Grafana Tempo"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 4,
            background: '#1e293b',
            border: '1px solid #334155',
            color: '#f97316',
            fontSize: 11,
            fontWeight: 500,
            textDecoration: 'none',
            cursor: 'pointer',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
          Grafana
        </a>
      )}
      {langfuseUrl && (
        <a
          href={langfuseUrl}
          target="_blank"
          rel="noopener noreferrer"
          title="View trace in Langfuse"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 4,
            background: '#1e293b',
            border: '1px solid #334155',
            color: '#818cf8',
            fontSize: 11,
            fontWeight: 500,
            textDecoration: 'none',
            cursor: 'pointer',
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          Langfuse
        </a>
      )}
    </span>
  );
}
