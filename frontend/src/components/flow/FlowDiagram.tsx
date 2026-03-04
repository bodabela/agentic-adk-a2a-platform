import { useMemo } from 'react';

/* ── Types ─────────────────────────────────────────────── */

interface StateNode {
  type: string;
  agent?: string;
  description?: string;
  provider?: string;
  model?: string;
  on_complete?: string;
  on_error?: string;
  on_response?: string;
  on_event?: string;
  on_timeout?: string;
  if_true?: string;
  if_false?: string;
  transitions?: Record<string, string>;
  branches?: Record<string, unknown>;
  status?: string;
  flow_name?: string;
  interaction_type?: string;
}

export interface FlowDefinitionData {
  name: string;
  description: string;
  version?: string;
  config: {
    provider?: string;
    model?: string;
    max_retry_loops?: number;
    timeout_minutes?: number;
    [key: string]: unknown;
  };
  states: Record<string, StateNode>;
}

/* ── Style constants ───────────────────────────────────── */

const NODE_W = 200;
const NODE_H = 72;
const DIAMOND_W = 260;
const DIAMOND_H = 110;
const H_GAP = 80;
const V_GAP = 80;
const PADDING = 60;
const BACK_EDGE_MARGIN = 50;

function nodeWidth(node: StateNode) {
  return (node.type === 'llm_decision' || node.type === 'conditional') ? DIAMOND_W : NODE_W;
}
function nodeHeight(node: StateNode) {
  return (node.type === 'llm_decision' || node.type === 'conditional') ? DIAMOND_H : NODE_H;
}

const TYPE_COLORS: Record<string, string> = {
  agent_task: '#3b82f6',
  llm_decision: '#8b5cf6',
  human_interaction: '#f59e0b',
  parallel: '#06b6d4',
  conditional: '#f97316',
  wait_for_event: '#6b7280',
  trigger_flow: '#6366f1',
  terminal: '#22c55e',
};

const TYPE_LABELS: Record<string, string> = {
  agent_task: 'Agent Task',
  llm_decision: 'LLM Decision',
  human_interaction: 'Human Input',
  parallel: 'Parallel',
  conditional: 'Condition',
  wait_for_event: 'Wait Event',
  trigger_flow: 'Trigger Flow',
  terminal: 'Terminal',
};

/* ── Edge extraction ───────────────────────────────────── */

interface Edge {
  from: string;
  to: string;
  label: string;
  style: 'normal' | 'error' | 'decision';
}

function extractEdges(states: Record<string, StateNode>): Edge[] {
  const edges: Edge[] = [];
  for (const [name, node] of Object.entries(states)) {
    if (node.on_complete && states[node.on_complete]) {
      edges.push({ from: name, to: node.on_complete, label: '', style: 'normal' });
    }
    if (node.on_error && states[node.on_error]) {
      edges.push({ from: name, to: node.on_error, label: 'error', style: 'error' });
    }
    if (node.on_response && states[node.on_response]) {
      edges.push({ from: name, to: node.on_response, label: 'response', style: 'normal' });
    }
    if (node.on_event && states[node.on_event]) {
      edges.push({ from: name, to: node.on_event, label: 'event', style: 'normal' });
    }
    if (node.on_timeout && states[node.on_timeout]) {
      edges.push({ from: name, to: node.on_timeout, label: 'timeout', style: 'error' });
    }
    if (node.if_true && states[node.if_true]) {
      edges.push({ from: name, to: node.if_true, label: 'true', style: 'decision' });
    }
    if (node.if_false && states[node.if_false]) {
      edges.push({ from: name, to: node.if_false, label: 'false', style: 'error' });
    }
    if (node.transitions) {
      for (const [label, target] of Object.entries(node.transitions)) {
        if (states[target]) {
          edges.push({ from: name, to: target, label, style: 'decision' });
        }
      }
    }
  }
  return edges;
}

/* ── BFS layering ──────────────────────────────────────── */

interface NodePos {
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  layer: number;
}

function computeLayout(
  states: Record<string, StateNode>,
  edges: Edge[],
): { positions: Record<string, NodePos>; width: number; height: number } {
  const stateNames = Object.keys(states);
  if (stateNames.length === 0) return { positions: {}, width: 0, height: 0 };

  const initial = stateNames[0];

  // Build adjacency (forward only for layering; skip back-edges)
  const adj: Record<string, string[]> = {};
  for (const name of stateNames) adj[name] = [];
  for (const edge of edges) {
    if (!adj[edge.from]) adj[edge.from] = [];
    adj[edge.from].push(edge.to);
  }

  // BFS to assign layers
  const layerOf: Record<string, number> = {};
  const queue: string[] = [initial];
  layerOf[initial] = 0;
  while (queue.length > 0) {
    const cur = queue.shift()!;
    for (const next of adj[cur] || []) {
      if (layerOf[next] === undefined) {
        layerOf[next] = layerOf[cur] + 1;
        queue.push(next);
      }
    }
  }

  const maxLayer = Math.max(0, ...Object.values(layerOf));
  for (const name of stateNames) {
    if (layerOf[name] === undefined) layerOf[name] = maxLayer + 1;
  }

  // Group by layer
  const layers: Record<number, string[]> = {};
  for (const name of stateNames) {
    const l = layerOf[name];
    if (!layers[l]) layers[l] = [];
    layers[l].push(name);
  }

  const totalLayers = Math.max(...Object.keys(layers).map(Number)) + 1;

  // Compute max width per layer (accounting for variable node widths)
  let maxLayerWidth = 0;
  for (let layer = 0; layer < totalLayers; layer++) {
    const nodesInLayer = layers[layer] || [];
    let w = 0;
    for (const name of nodesInLayer) {
      w += nodeWidth(states[name]) + H_GAP;
    }
    w -= H_GAP;
    if (w > maxLayerWidth) maxLayerWidth = w;
  }

  // Compute max height per layer
  const layerYStart: number[] = [];
  let currentY = PADDING;
  for (let layer = 0; layer < totalLayers; layer++) {
    layerYStart.push(currentY);
    const nodesInLayer = layers[layer] || [];
    let maxH = NODE_H;
    for (const name of nodesInLayer) {
      const h = nodeHeight(states[name]);
      if (h > maxH) maxH = h;
    }
    currentY += maxH + V_GAP;
  }

  const totalWidth = maxLayerWidth + PADDING * 2 + BACK_EDGE_MARGIN;
  const totalHeight = currentY - V_GAP + PADDING;

  const positions: Record<string, NodePos> = {};
  for (let layer = 0; layer < totalLayers; layer++) {
    const nodesInLayer = layers[layer] || [];
    // Center this layer's nodes
    let layerWidth = 0;
    for (const name of nodesInLayer) layerWidth += nodeWidth(states[name]) + H_GAP;
    layerWidth -= H_GAP;
    let offsetX = (totalWidth - BACK_EDGE_MARGIN - layerWidth) / 2;

    // Find max height in this layer to vertically center each node
    let maxH = NODE_H;
    for (const name of nodesInLayer) {
      const h = nodeHeight(states[name]);
      if (h > maxH) maxH = h;
    }

    for (const name of nodesInLayer) {
      const w = nodeWidth(states[name]);
      const h = nodeHeight(states[name]);
      positions[name] = {
        name,
        x: offsetX,
        y: layerYStart[layer] + (maxH - h) / 2,
        w,
        h,
        layer,
      };
      offsetX += w + H_GAP;
    }
  }

  return { positions, width: totalWidth, height: totalHeight };
}

/* ── SVG node shape renderers ──────────────────────────── */

function NodeShape({ node, state, pos, config, isActive }: {
  node: StateNode;
  state: string;
  pos: NodePos;
  config: FlowDefinitionData['config'];
  isActive?: boolean;
}) {
  const color = node.type === 'terminal' && node.status === 'failed'
    ? '#ef4444'
    : TYPE_COLORS[node.type] || '#64748b';
  const label = TYPE_LABELS[node.type] || node.type;
  const effectiveModel = node.model || config.model || '';
  const effectiveProvider = node.provider || config.provider || '';

  const cx = pos.x + pos.w / 2;
  const cy = pos.y + pos.h / 2;

  let detail = '';
  if (node.type === 'agent_task' && node.agent) {
    detail = node.agent;
  } else if (node.type === 'human_interaction' && node.interaction_type) {
    detail = node.interaction_type;
  } else if (node.type === 'trigger_flow' && node.flow_name) {
    detail = node.flow_name;
  } else if (node.type === 'terminal' && node.status) {
    detail = node.status;
  }

  const modelLine = (node.type === 'agent_task' || node.type === 'llm_decision') && effectiveModel
    ? `${effectiveProvider}/${effectiveModel}`
    : '';

  let shape: React.ReactNode;
  if (node.type === 'llm_decision' || node.type === 'conditional') {
    shape = (
      <polygon
        points={`${cx},${pos.y} ${pos.x + pos.w},${cy} ${cx},${pos.y + pos.h} ${pos.x},${cy}`}
        fill={color + '18'}
        stroke={color}
        strokeWidth={2}
      />
    );
  } else if (node.type === 'terminal') {
    shape = (
      <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
        rx={pos.h / 2} ry={pos.h / 2}
        fill={color + '18'} stroke={color} strokeWidth={2} />
    );
  } else if (node.type === 'human_interaction') {
    shape = (
      <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
        rx={16} ry={16}
        fill={color + '18'} stroke={color} strokeWidth={2} />
    );
  } else if (node.type === 'wait_for_event') {
    shape = (
      <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
        rx={6} ry={6}
        fill={color + '18'} stroke={color} strokeWidth={2} strokeDasharray="6 3" />
    );
  } else if (node.type === 'parallel') {
    shape = (
      <>
        <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
          rx={6} ry={6}
          fill={color + '18'} stroke={color} strokeWidth={2} />
        <rect x={pos.x + 4} y={pos.y + 4} width={pos.w - 8} height={pos.h - 8}
          rx={4} ry={4}
          fill="none" stroke={color} strokeWidth={1} opacity={0.5} />
      </>
    );
  } else {
    shape = (
      <rect x={pos.x} y={pos.y} width={pos.w} height={pos.h}
        rx={6} ry={6}
        fill={color + '18'} stroke={color} strokeWidth={2} />
    );
  }

  const lines: { text: string; fontSize: number; fill: string; fontWeight?: string }[] = [];
  lines.push({ text: state, fontSize: 12, fill: '#e2e8f0', fontWeight: '600' });
  lines.push({ text: label, fontSize: 10, fill: color });
  if (detail) lines.push({ text: detail, fontSize: 10, fill: '#94a3b8' });
  if (modelLine) lines.push({ text: truncate(modelLine, 30), fontSize: 9, fill: '#64748b' });

  const lineH = 14;
  const totalTextH = lines.length * lineH;
  const textStartY = cy - totalTextH / 2 + lineH / 2 + 2;

  return (
    <g>
      {isActive && (
        <rect
          x={pos.x - 4}
          y={pos.y - 4}
          width={pos.w + 8}
          height={pos.h + 8}
          rx={10}
          ry={10}
          fill="none"
          stroke="#38bdf8"
          strokeWidth={2.5}
          opacity={0.8}
        >
          <animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite" />
        </rect>
      )}
      {shape}
      {lines.map((line, i) => (
        <text
          key={i}
          x={cx}
          y={textStartY + i * lineH}
          textAnchor="middle"
          fill={line.fill}
          fontSize={line.fontSize}
          fontWeight={line.fontWeight}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {line.text}
        </text>
      ))}
    </g>
  );
}

function truncate(s: string, max: number) {
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

/* ── SVG edge renderer ─────────────────────────────────── */

function EdgeLine({
  edge,
  fromPos,
  toPos,
  allEdgesFromSame,
  edgeIndex,
  svgWidth,
}: {
  edge: Edge;
  fromPos: NodePos;
  toPos: NodePos;
  allEdgesFromSame: number;
  edgeIndex: number;
  svgWidth: number;
}) {
  const fromCx = fromPos.x + fromPos.w / 2;
  const fromBottom = fromPos.y + fromPos.h;
  const toCx = toPos.x + toPos.w / 2;
  const toTop = toPos.y;

  const isBackEdge = toPos.layer <= fromPos.layer;

  let strokeColor = '#475569';
  let dashArray = '';
  if (edge.style === 'error') {
    strokeColor = '#ef4444';
    dashArray = '6 3';
  } else if (edge.style === 'decision') {
    strokeColor = '#a78bfa';
    dashArray = '4 2';
  }

  // Spread offset for multiple outgoing edges
  const spread = allEdgesFromSame > 1
    ? (edgeIndex - (allEdgesFromSame - 1) / 2) * 30
    : 0;

  let pathD: string;
  let labelX: number;
  let labelY: number;
  let labelAnchor: 'start' | 'end' | 'middle' = 'start';

  if (isBackEdge) {
    // Route around the right side, far from nodes
    const routeX = svgWidth - 20;
    const fromRight = fromPos.x + fromPos.w;
    const fromMidY = fromPos.y + fromPos.h / 2;
    const toRight = toPos.x + toPos.w;
    const toMidY = toPos.y + toPos.h / 2;
    pathD = [
      `M ${fromRight} ${fromMidY}`,
      `C ${fromRight + 40} ${fromMidY}, ${routeX} ${fromMidY}, ${routeX} ${fromMidY - 30}`,
      `L ${routeX} ${toMidY + 30}`,
      `C ${routeX} ${toMidY}, ${toRight + 40} ${toMidY}, ${toRight} ${toMidY}`,
    ].join(' ');
    labelX = routeX + 6;
    labelY = (fromMidY + toMidY) / 2;
  } else {
    const startX = fromCx + spread;
    const endX = toCx;
    const midY = (fromBottom + toTop) / 2;
    pathD = `M ${startX} ${fromBottom} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${toTop}`;

    // Label at the midpoint, offset to the side to avoid line
    labelX = (startX + endX) / 2 + 10;
    labelY = midY - 4;
    if (startX > endX) {
      labelX = (startX + endX) / 2 - 10;
      labelAnchor = 'end';
    }
  }

  return (
    <g>
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeDasharray={dashArray}
        markerEnd={`url(#arrow-${edge.style})`}
      />
      {edge.label && (
        <>
          <rect
            x={labelAnchor === 'end' ? labelX - edge.label.length * 6 - 4 : labelX - 3}
            y={labelY - 10}
            width={edge.label.length * 6.5 + 6}
            height={14}
            rx={3}
            fill="#0f172a"
            opacity={0.9}
          />
          <text
            x={labelX}
            y={labelY}
            fill={strokeColor}
            fontSize={10}
            fontWeight="500"
            fontFamily="system-ui, -apple-system, sans-serif"
            textAnchor={labelAnchor}
          >
            {edge.label}
          </text>
        </>
      )}
    </g>
  );
}

/* ── Main component ────────────────────────────────────── */

export function FlowDiagram({ definition, activeState }: { definition: FlowDefinitionData; activeState?: string }) {
  const { edges, positions, width, height } = useMemo(() => {
    const edges = extractEdges(definition.states);
    const { positions, width, height } = computeLayout(definition.states, edges);
    return { edges, positions, width, height };
  }, [definition]);

  if (Object.keys(definition.states).length === 0) {
    return <div style={{ color: '#64748b', padding: '2rem' }}>No states in this flow.</div>;
  }

  const edgesBySource: Record<string, Edge[]> = {};
  for (const edge of edges) {
    if (!edgesBySource[edge.from]) edgesBySource[edge.from] = [];
    edgesBySource[edge.from].push(edge);
  }

  return (
    <div style={{ overflow: 'auto', background: '#020617', borderRadius: 8, border: '1px solid #1e293b' }}>
      {/* Flow header */}
      <div style={{
        padding: '0.75rem 1rem',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.5rem',
      }}>
        <div>
          <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '1.1rem' }}>{definition.name}</span>
          {definition.description && (
            <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: 2 }}>{definition.description}</div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.8rem', flexWrap: 'wrap' }}>
          {definition.config.provider && definition.config.model && (
            <span style={{ color: '#a78bfa', background: '#1e1b4b', padding: '2px 8px', borderRadius: 4 }}>
              {definition.config.provider}/{definition.config.model}
            </span>
          )}
          {definition.config.max_retry_loops !== undefined && (
            <span style={{ color: '#64748b' }}>retries: {definition.config.max_retry_loops}</span>
          )}
          {definition.config.timeout_minutes !== undefined && (
            <span style={{ color: '#64748b' }}>timeout: {definition.config.timeout_minutes}m</span>
          )}
        </div>
      </div>

      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: 'block', minWidth: width, minHeight: height }}
      >
        <defs>
          <marker id="arrow-normal" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#475569" />
          </marker>
          <marker id="arrow-error" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#ef4444" />
          </marker>
          <marker id="arrow-decision" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#a78bfa" />
          </marker>
        </defs>

        {/* Edges (rendered first = behind nodes) */}
        {edges.map((edge, i) => {
          const fromPos = positions[edge.from];
          const toPos = positions[edge.to];
          if (!fromPos || !toPos) return null;
          const sourceEdges = edgesBySource[edge.from] || [];
          const edgeIndex = sourceEdges.indexOf(edge);
          return (
            <EdgeLine
              key={`${edge.from}-${edge.to}-${edge.label}-${i}`}
              edge={edge}
              fromPos={fromPos}
              toPos={toPos}
              allEdgesFromSame={sourceEdges.length}
              edgeIndex={edgeIndex}
              svgWidth={width}
            />
          );
        })}

        {/* Nodes */}
        {Object.entries(definition.states).map(([stateName, node]) => {
          const pos = positions[stateName];
          if (!pos) return null;
          return (
            <NodeShape
              key={stateName}
              node={node}
              state={stateName}
              pos={pos}
              config={definition.config}
              isActive={stateName === activeState}
            />
          );
        })}
      </svg>
    </div>
  );
}
