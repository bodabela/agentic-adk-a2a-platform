import { useEffect } from 'react';
import { useToolStore, type ToolDefinition, type ToolParameter } from '../stores/toolStore';

const cardStyle: React.CSSProperties = {
  background: '#1e293b',
  border: '1px solid #334155',
  borderRadius: 8,
  padding: '0.85rem 1rem',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
};

const activeCardStyle: React.CSSProperties = {
  ...cardStyle,
  borderColor: '#38bdf8',
};

const badgeBase: React.CSSProperties = {
  display: 'inline-block',
  fontSize: '0.7rem',
  fontWeight: 600,
  padding: '2px 8px',
  borderRadius: 999,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const mcpBadge: React.CSSProperties = {
  ...badgeBase,
  background: '#164e63',
  color: '#67e8f9',
};

const builtinBadge: React.CSSProperties = {
  ...badgeBase,
  background: '#3b0764',
  color: '#d8b4fe',
};

function CategoryBadge({ category }: { category: string }) {
  return (
    <span style={category === 'mcp' ? mcpBadge : builtinBadge}>
      {category}
    </span>
  );
}

function ParamRow({ param }: { param: ToolParameter }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '140px 100px 1fr',
      gap: '0.5rem',
      padding: '0.4rem 0',
      borderBottom: '1px solid #1e293b',
      alignItems: 'start',
    }}>
      <div>
        <code style={{ color: '#f8fafc', fontSize: '0.85rem' }}>{param.name}</code>
        {!param.required && (
          <span style={{ color: '#64748b', fontSize: '0.7rem', marginLeft: 4 }}>optional</span>
        )}
      </div>
      <div style={{ color: '#94a3b8', fontSize: '0.8rem', fontFamily: 'monospace' }}>
        {param.type}
      </div>
      <div style={{ color: '#cbd5e1', fontSize: '0.85rem' }}>
        {param.description || '—'}
        {param.default !== undefined && (
          <span style={{ color: '#64748b', fontSize: '0.8rem', marginLeft: 6 }}>
            default: <code>{JSON.stringify(param.default)}</code>
          </span>
        )}
      </div>
    </div>
  );
}

function ToolDetail({ tool }: { tool: ToolDefinition }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header */}
      <div style={{ background: '#1e293b', borderRadius: 8, padding: '1.5rem', border: '1px solid #334155' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <h3 style={{ color: '#e2e8f0', margin: 0, fontSize: '1.3rem', fontFamily: 'monospace' }}>
            {tool.name}
          </h3>
          <CategoryBadge category={tool.category} />
        </div>
        <p style={{ color: '#94a3b8', margin: 0, lineHeight: 1.6 }}>{tool.description}</p>

        <div style={{ display: 'flex', gap: '2rem', marginTop: '1rem', flexWrap: 'wrap' }}>
          {tool.transport && (
            <div>
              <div style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Transport</div>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.85rem' }}>{tool.transport}</div>
            </div>
          )}
          {tool.server && (
            <div>
              <div style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Server</div>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.85rem' }}>{tool.server}</div>
            </div>
          )}
          {tool.url && (
            <div>
              <div style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>URL</div>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.85rem' }}>{tool.url}</div>
            </div>
          )}
          {tool.command && (
            <div>
              <div style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Command</div>
              <div style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.85rem' }}>{tool.command}</div>
            </div>
          )}
          <div>
            <div style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Used by</div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: 2 }}>
              {tool.used_by.length > 0 ? tool.used_by.map((a) => (
                <span key={a} style={{
                  background: '#1e3a5f',
                  color: '#93c5fd',
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: 4,
                }}>
                  {a}
                </span>
              )) : (
                <span style={{ color: '#64748b', fontSize: '0.85rem' }}>none</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Parameters */}
      <div style={{ background: '#1e293b', borderRadius: 8, padding: '1.25rem', border: '1px solid #334155' }}>
        <h4 style={{ color: '#e2e8f0', margin: '0 0 0.75rem', fontSize: '0.95rem' }}>
          Parameters {tool.parameters.length === 0 && <span style={{ color: '#64748b', fontWeight: 400 }}>(none)</span>}
        </h4>
        {tool.parameters.length > 0 && (
          <div style={{ background: '#0f172a', borderRadius: 6, padding: '0.75rem' }}>
            {/* Header row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '140px 100px 1fr',
              gap: '0.5rem',
              padding: '0 0 0.4rem',
              borderBottom: '1px solid #334155',
              marginBottom: '0.25rem',
            }}>
              <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</div>
              <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Type</div>
              <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</div>
            </div>
            {tool.parameters.map((p) => (
              <ParamRow key={p.name} param={p} />
            ))}
          </div>
        )}
      </div>

      {/* Full docstring */}
      {tool.docstring && (
        <div style={{ background: '#1e293b', borderRadius: 8, padding: '1.25rem', border: '1px solid #334155' }}>
          <h4 style={{ color: '#e2e8f0', margin: '0 0 0.75rem', fontSize: '0.95rem' }}>Documentation</h4>
          <pre style={{
            background: '#0f172a',
            color: '#cbd5e1',
            padding: '1rem',
            borderRadius: 6,
            fontSize: '0.85rem',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            margin: 0,
            fontFamily: 'monospace',
          }}>
            {tool.docstring}
          </pre>
        </div>
      )}
    </div>
  );
}

export function ToolsPage() {
  const { tools, selectedTool, loading, summary, fetchTools, selectTool } = useToolStore();

  useEffect(() => { fetchTools(); }, [fetchTools]);

  return (
    <div style={{ display: 'flex', gap: '1.5rem', height: '100%', padding: '1.5rem' }}>
      {/* Left: Tool list */}
      <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <div style={{ marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '1.2rem' }}>Tools</h2>
          {summary && (
            <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: 4 }}>
              {summary.total} tools ({summary.mcp_count} MCP, {summary.builtin_count} builtin)
            </div>
          )}
        </div>

        {loading && <div style={{ color: '#94a3b8' }}>Loading...</div>}

        {tools.map((t: ToolDefinition) => (
          <div
            key={t.name}
            style={selectedTool?.name === t.name ? activeCardStyle : cardStyle}
            onClick={() => selectTool(t.name)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontWeight: 600, color: '#e2e8f0', fontFamily: 'monospace', fontSize: '0.9rem' }}>
                {t.name}
              </span>
              <CategoryBadge category={t.category} />
            </div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 4, lineHeight: 1.4 }}>
              {t.description.length > 80 ? t.description.slice(0, 80) + '...' : t.description}
            </div>
            <div style={{ display: 'flex', gap: '0.3rem', marginTop: 6, flexWrap: 'wrap' }}>
              {t.used_by.map((a) => (
                <span key={a} style={{
                  background: '#1e3a5f',
                  color: '#93c5fd',
                  fontSize: '0.65rem',
                  padding: '1px 6px',
                  borderRadius: 3,
                }}>
                  {a}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Right: Detail panel */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {selectedTool ? (
          <ToolDetail tool={selectedTool} />
        ) : (
          <div style={{ color: '#64748b', textAlign: 'center', marginTop: '4rem' }}>
            Select a tool to view its schema, parameters and documentation.
          </div>
        )}
      </div>
    </div>
  );
}
