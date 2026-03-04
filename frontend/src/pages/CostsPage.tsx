import { useMemo } from 'react';
import {
  useCostStore,
  aggregateByTask,
  aggregateByModule,
  aggregateByAgent,
  type CostEntry,
  type CostAggregation,
  type GranularityLevel,
} from '../stores/costStore';
import { useTaskStore } from '../stores/taskStore';
import { useFlowStore } from '../stores/flowStore';

// --- Formatting helpers ---

function fmtCost(usd: number): string {
  return '$' + usd.toFixed(usd >= 0.01 ? 4 : 6);
}

function fmtTokens(n: number): string {
  return n.toLocaleString();
}

function fmtLatency(ms: number): string {
  if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
  return ms + 'ms';
}

function opColor(op: string): string {
  if (op.includes('llm_call')) return '#60a5fa';
  if (op.includes('tool')) return '#fbbf24';
  if (op.includes('a2a')) return '#a78bfa';
  if (op.includes('cache')) return '#22d3ee';
  if (op.includes('embedding')) return '#34d399';
  return '#94a3b8';
}

// --- Resolve task_id → friendly name ---

function resolveLabel(
  taskId: string,
  tasks: Record<string, { description: string }>,
  flows: Record<string, { flowName: string }>,
): string {
  const flow = flows[taskId];
  if (flow) return `Flow: ${flow.flowName}`;
  const task = tasks[taskId];
  if (task?.description) {
    return task.description.length > 50 ? task.description.slice(0, 50) + '...' : task.description;
  }
  return taskId.slice(0, 12) + '...';
}

// --- Granularity selector ---

const GRANULARITY_OPTIONS: { value: GranularityLevel; label: string }[] = [
  { value: 'total', label: 'Total' },
  { value: 'task', label: 'Task / Flow' },
  { value: 'module', label: 'Module' },
  { value: 'agent', label: 'Agent' },
  { value: 'event', label: 'Event' },
];

function GranularitySelector({
  value,
  onChange,
}: {
  value: GranularityLevel;
  onChange: (v: GranularityLevel) => void;
}) {
  return (
    <div style={{ display: 'flex', gap: '0.25rem' }}>
      {GRANULARITY_OPTIONS.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            style={{
              padding: '0.35rem 0.75rem',
              fontSize: '1.125rem',
              fontWeight: active ? 600 : 400,
              background: active ? '#334155' : 'transparent',
              color: active ? '#e2e8f0' : '#64748b',
              border: `1px solid ${active ? '#60a5fa' : '#334155'}`,
              borderRadius: 6,
              cursor: 'pointer',
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// --- Summary stats ---

function SummaryStats({ events }: { events: CostEntry[] }) {
  const totals = useMemo(() => {
    let cost = 0;
    let inputTok = 0;
    let outputTok = 0;
    let latency = 0;
    let llmCalls = 0;
    let toolInv = 0;
    for (const e of events) {
      cost += e.cost_usd;
      if (e.llm) {
        inputTok += e.llm.input_tokens;
        outputTok += e.llm.output_tokens;
        latency += e.llm.latency_ms;
        llmCalls++;
      }
      if (e.tool) {
        latency += e.tool.latency_ms;
        toolInv++;
      }
    }
    return { cost, inputTok, outputTok, latency, llmCalls, toolInv, count: events.length };
  }, [events]);

  const cards = [
    { label: 'Total Spend', value: fmtCost(totals.cost), color: totals.cost > 1 ? '#f59e0b' : '#22c55e' },
    { label: 'Events', value: `${totals.llmCalls} LLM / ${totals.toolInv} tool`, color: '#60a5fa' },
    { label: 'Tokens', value: `${fmtTokens(totals.inputTok)} in / ${fmtTokens(totals.outputTok)} out`, color: '#a78bfa' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
      {cards.map((c) => (
        <div
          key={c.label}
          style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: '1rem',
            textAlign: 'center',
          }}
        >
          <div style={{ color: '#94a3b8', fontSize: '1.1rem', marginBottom: '0.35rem' }}>{c.label}</div>
          <div style={{ color: c.color, fontSize: '1.2rem', fontWeight: 700, fontFamily: 'monospace' }}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Event card (leaf detail) ---

function EventCard({ entry }: { entry: CostEntry }) {
  const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';
  const color = opColor(entry.operation_type);

  return (
    <div
      style={{
        fontSize: '1.05rem',
        padding: '0.5rem 0.625rem',
        background: '#020617',
        borderLeft: `3px solid ${color}`,
        borderRadius: 4,
        fontFamily: 'monospace',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.2rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>
          <span style={{ color: '#475569' }}>{time} </span>
          <span style={{ color }}>{entry.operation_type}</span>
        </span>
        <span style={{ color: '#22c55e', fontWeight: 600 }}>{fmtCost(entry.cost_usd)}</span>
      </div>
      {entry.llm && (
        <>
          <div style={{ color: '#94a3b8' }}>
            {entry.llm.provider}/{entry.llm.model}
          </div>
          <div style={{ color: '#64748b' }}>
            Tokens: {fmtTokens(entry.llm.input_tokens)} in / {fmtTokens(entry.llm.output_tokens)} out
            {entry.llm.cached_tokens > 0 && ` / ${fmtTokens(entry.llm.cached_tokens)} cached`}
            {entry.llm.thinking_tokens > 0 && ` / ${fmtTokens(entry.llm.thinking_tokens)} thinking`}
            {' | '}Latency: {fmtLatency(entry.llm.latency_ms)}
          </div>
        </>
      )}
      {entry.tool && (
        <div style={{ color: '#94a3b8' }}>
          Tool: {entry.tool.tool_id} ({entry.tool.tool_source})
          {' | '}Latency: {fmtLatency(entry.tool.latency_ms)}
        </div>
      )}
      <div style={{ color: '#475569' }}>
        {entry.module} &gt; {entry.agent}
      </div>
    </div>
  );
}

// --- Aggregation row (recursive) ---

function AggregationRow({
  agg,
  depth,
  maxCost,
  expandedKeys,
  onToggle,
  labelResolver,
}: {
  agg: CostAggregation;
  depth: number;
  maxCost: number;
  expandedKeys: Record<string, boolean>;
  onToggle: (key: string) => void;
  labelResolver: (key: string) => string;
}) {
  const isExpanded = !!expandedKeys[agg.key];
  const barWidth = maxCost > 0 ? (agg.totalCost / maxCost) * 100 : 0;
  const label = depth === 0 ? labelResolver(agg.key) : agg.label;

  const depthColors = ['#e2e8f0', '#22d3ee', '#a78bfa', '#fbbf24'];
  const labelColor = depthColors[depth] || '#94a3b8';

  const isLeaf = agg.children.length > 0 && 'event_id' in agg.children[0];

  return (
    <div style={{ marginLeft: depth > 0 ? '1rem' : 0 }}>
      <div
        onClick={() => onToggle(agg.key)}
        style={{
          position: 'relative',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: depth === 0 ? '#0f172a' : '#020617',
          border: `1px solid ${depth === 0 ? '#334155' : '#1e293b'}`,
          borderRadius: 6,
          padding: '0.6rem 0.75rem',
          cursor: 'pointer',
          overflow: 'hidden',
          marginBottom: '0.25rem',
        }}
      >
        {/* cost bar */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${barWidth}%`,
            background: 'rgba(96, 165, 250, 0.08)',
            borderRadius: 6,
            zIndex: 0,
          }}
        />
        {/* left side */}
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
          <span
            style={{
              display: 'inline-block',
              transform: isExpanded ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.15s',
              fontSize: '0.975rem',
              color: '#64748b',
            }}
          >
            &#9654;
          </span>
          <span
            style={{
              color: labelColor,
              fontSize: '1.2rem',
              fontWeight: depth === 0 ? 600 : 400,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </span>
        </div>
        {/* right side */}
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', gap: '1rem', alignItems: 'center', flexShrink: 0 }}>
          <span style={{ color: '#64748b', fontSize: '1.05rem' }}>{agg.eventCount} evt</span>
          {agg.totalInputTokens > 0 && (
            <span style={{ color: '#475569', fontSize: '0.975rem', fontFamily: 'monospace' }}>
              {fmtTokens(agg.totalInputTokens + agg.totalOutputTokens)} tok
            </span>
          )}
          <span style={{ color: '#22c55e', fontSize: '1.2rem', fontWeight: 600, fontFamily: 'monospace' }}>
            {fmtCost(agg.totalCost)}
          </span>
        </div>
      </div>

      {isExpanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginBottom: '0.25rem' }}>
          {isLeaf
            ? (agg.children as CostEntry[]).map((entry) => (
                <div key={entry.event_id} style={{ marginLeft: '1rem' }}>
                  <EventCard entry={entry} />
                </div>
              ))
            : (agg.children as CostAggregation[]).map((child) => {
                const siblingMax = Math.max(...(agg.children as CostAggregation[]).map((c) => c.totalCost));
                return (
                  <AggregationRow
                    key={child.key}
                    agg={child}
                    depth={depth + 1}
                    maxCost={siblingMax}
                    expandedKeys={expandedKeys}
                    onToggle={onToggle}
                    labelResolver={labelResolver}
                  />
                );
              })}
        </div>
      )}
    </div>
  );
}

// --- Total view ---

function TotalView({ events }: { events: CostEntry[] }) {
  const totals = useMemo(() => {
    let cost = 0;
    let inputTok = 0;
    let outputTok = 0;
    let latency = 0;
    let llmCalls = 0;
    let toolInv = 0;
    for (const e of events) {
      cost += e.cost_usd;
      if (e.llm) {
        inputTok += e.llm.input_tokens;
        outputTok += e.llm.output_tokens;
        latency += e.llm.latency_ms;
        llmCalls++;
      }
      if (e.tool) {
        latency += e.tool.latency_ms;
        toolInv++;
      }
    }
    const avgLatency = events.length > 0 ? latency / events.length : 0;
    return { cost, inputTok, outputTok, llmCalls, toolInv, avgLatency };
  }, [events]);

  const rows = [
    ['LLM Calls', String(totals.llmCalls)],
    ['Tool Invocations', String(totals.toolInv)],
    ['Input Tokens', fmtTokens(totals.inputTok)],
    ['Output Tokens', fmtTokens(totals.outputTok)],
    ['Avg Latency', fmtLatency(Math.round(totals.avgLatency))],
  ];

  return (
    <div
      style={{
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 8,
        padding: '1.25rem',
      }}
    >
      <div
        style={{
          textAlign: 'center',
          marginBottom: '1rem',
        }}
      >
        <div style={{ color: '#94a3b8', fontSize: '1.125rem', marginBottom: '0.25rem' }}>Total Spend</div>
        <div
          style={{
            color: totals.cost > 1 ? '#f59e0b' : '#22c55e',
            fontSize: '2rem',
            fontWeight: 700,
            fontFamily: 'monospace',
          }}
        >
          {fmtCost(totals.cost)}
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 2rem' }}>
        {rows.map(([label, val]) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.2rem' }}>
            <span style={{ color: '#94a3b8' }}>{label}</span>
            <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Main page ---

export function CostsPage() {
  const recentEvents = useCostStore((s) => s.recentEvents);
  const granularity = useCostStore((s) => s.granularity);
  const setGranularity = useCostStore((s) => s.setGranularity);
  const expandedKeys = useCostStore((s) => s.expandedKeys);
  const toggleExpanded = useCostStore((s) => s.toggleExpanded);

  const tasks = useTaskStore((s) => s.tasks);
  const flows = useFlowStore((s) => s.activeFlows);

  const labelResolver = (key: string) => resolveLabel(key, tasks, flows);

  const aggregations: CostAggregation[] | null = useMemo(() => {
    if (granularity === 'task') return aggregateByTask(recentEvents);
    if (granularity === 'module') return aggregateByModule(recentEvents);
    if (granularity === 'agent') return aggregateByAgent(recentEvents);
    return null;
  }, [granularity, recentEvents]);

  const topMaxCost = aggregations ? Math.max(...aggregations.map((a) => a.totalCost), 0) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', margin: 0 }}>Cost Overview</h2>

      <SummaryStats events={recentEvents} />

      <GranularitySelector value={granularity} onChange={setGranularity} />

      {recentEvents.length === 0 ? (
        <div style={{ color: '#64748b', textAlign: 'center', padding: '2rem' }}>
          No cost data yet. Submit a task or start a flow.
        </div>
      ) : granularity === 'total' ? (
        <TotalView events={recentEvents} />
      ) : granularity === 'event' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {[...recentEvents].reverse().map((entry) => (
            <EventCard key={entry.event_id} entry={entry} />
          ))}
        </div>
      ) : aggregations ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {aggregations.map((agg) => (
            <AggregationRow
              key={agg.key}
              agg={agg}
              depth={0}
              maxCost={topMaxCost}
              expandedKeys={expandedKeys}
              onToggle={toggleExpanded}
              labelResolver={labelResolver}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
