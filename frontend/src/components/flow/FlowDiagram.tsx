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

const NODE_W = 220;
const NODE_H = 82;
const DIAMOND_W = 280;
const DIAMOND_H = 120;
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

function NodeShape({ node, state, pos, config, isActive, isHighlighted, toolUsage }: {
  node: StateNode;
  state: string;
  pos: NodePos;
  config: FlowDefinitionData['config'];
  isActive?: boolean;
  isHighlighted?: boolean;
  toolUsage?: Record<string, number>;
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
  lines.push({ text: state, fontSize: 15, fill: '#e2e8f0', fontWeight: '600' });
  lines.push({ text: label, fontSize: 12, fill: color });
  if (detail) lines.push({ text: detail, fontSize: 12, fill: '#94a3b8' });
  if (modelLine) lines.push({ text: truncate(modelLine, 30), fontSize: 11, fill: '#64748b' });

  const lineH = 17;
  const totalTextH = lines.length * lineH;
  const textStartY = cy - totalTextH / 2 + lineH / 2 + 2;

  return (
    <g>
      {isActive && (
        <>
          <rect
            x={pos.x - 8}
            y={pos.y - 8}
            width={pos.w + 16}
            height={pos.h + 16}
            rx={12}
            ry={12}
            fill="none"
            stroke="#22d3ee"
            strokeWidth={3}
            opacity={0.35}
          >
            <animate attributeName="opacity" values="0.15;0.4;0.15" dur="2s" repeatCount="indefinite" />
          </rect>
          <rect
            x={pos.x - 4}
            y={pos.y - 4}
            width={pos.w + 8}
            height={pos.h + 8}
            rx={10}
            ry={10}
            fill="none"
            stroke="#22d3ee"
            strokeWidth={3.5}
            opacity={1}
          >
            <animate attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite" />
          </rect>
        </>
      )}
      {isHighlighted && !isActive && (
        <rect
          x={pos.x - 4}
          y={pos.y - 4}
          width={pos.w + 8}
          height={pos.h + 8}
          rx={10}
          ry={10}
          fill="none"
          stroke="#22d3ee"
          strokeWidth={2.5}
          opacity={0.6}
        />
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
      {/* Tool usage badges below the node */}
      {toolUsage && Object.keys(toolUsage).length > 0 && (
        <g>
          {Object.entries(toolUsage).map(([toolName, count], i) => {
            const badgeY = pos.y + pos.h + 6 + i * 18;
            const label = `${toolName} x${count}`;
            return (
              <g key={toolName}>
                <rect
                  x={cx - label.length * 3.5 - 6}
                  y={badgeY}
                  width={label.length * 7 + 12}
                  height={16}
                  rx={8}
                  fill="#1e293b"
                  stroke="#334155"
                  strokeWidth={1}
                />
                <text
                  x={cx}
                  y={badgeY + 12}
                  textAnchor="middle"
                  fill="#fbbf24"
                  fontSize={10}
                  fontFamily="system-ui, -apple-system, sans-serif"
                >
                  {label}
                </text>
              </g>
            );
          })}
        </g>
      )}
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
  isActive,
  allPositions,
}: {
  edge: Edge;
  fromPos: NodePos;
  toPos: NodePos;
  allEdgesFromSame: number;
  edgeIndex: number;
  svgWidth: number;
  isActive: boolean;
  allPositions: Record<string, NodePos>;
}) {
  const fromCx = fromPos.x + fromPos.w / 2;
  const fromBottom = fromPos.y + fromPos.h;
  const toCx = toPos.x + toPos.w / 2;
  const toTop = toPos.y;

  const isBackEdge = toPos.layer <= fromPos.layer;

  // Check if the bezier curve from→to would cross any node's bounding box
  let crossesNode = false;
  if (!isBackEdge) {
    // Spread offset for multiple outgoing edges (compute early for bezier sampling)
    const preSpread = allEdgesFromSame > 1
      ? (edgeIndex - (allEdgesFromSame - 1) / 2) * 30
      : 0;
    const sampleFromX = fromCx + preSpread;
    const sampleToX = toCx;
    const sampleMidY = (fromBottom + toTop) / 2;

    for (const pos of Object.values(allPositions)) {
      if (pos.name === fromPos.name || pos.name === toPos.name) continue;
      // Check nodes in intermediate layers AND same-layer siblings
      const inPath = (pos.layer > fromPos.layer && pos.layer < toPos.layer) ||
        (pos.layer === fromPos.layer && pos.name !== fromPos.name) ||
        (pos.layer === toPos.layer && pos.name !== toPos.name);
      if (!inPath) continue;

      const margin = 12;
      const nodeLeft = pos.x - margin;
      const nodeRight = pos.x + pos.w + margin;
      const nodeTop = pos.y - margin;
      const nodeBottom = pos.y + pos.h + margin;

      // Sample the cubic bezier at many t values
      for (let t = 0.05; t <= 0.95; t += 0.05) {
        const it = 1 - t;
        // Cubic bezier: P0=(sampleFromX, fromBottom), P1=(sampleFromX, sampleMidY), P2=(sampleToX, sampleMidY), P3=(sampleToX, toTop)
        const px = it * it * it * sampleFromX + 3 * it * it * t * sampleFromX + 3 * it * t * t * sampleToX + t * t * t * sampleToX;
        const py = it * it * it * fromBottom + 3 * it * it * t * sampleMidY + 3 * it * t * t * sampleMidY + t * t * t * toTop;

        if (px >= nodeLeft && px <= nodeRight && py >= nodeTop && py <= nodeBottom) {
          crossesNode = true;
          break;
        }
      }
      if (crossesNode) break;
    }
  }

  let baseStrokeColor = '#475569';
  let dashArray = '';
  if (edge.style === 'error') {
    baseStrokeColor = '#ef4444';
    dashArray = '6 3';
  } else if (edge.style === 'decision') {
    baseStrokeColor = '#a78bfa';
    dashArray = '4 2';
  }

  // Active edge overrides color
  const strokeColor = isActive ? '#22d3ee' : baseStrokeColor;
  const strokeWidth = isActive ? 2.5 : 1.5;
  const markerSuffix = isActive ? 'active' : edge.style;

  // Spread offset for multiple outgoing edges
  const spread = allEdgesFromSame > 1
    ? (edgeIndex - (allEdgesFromSame - 1) / 2) * 30
    : 0;

  let pathD: string;
  let labelX: number;
  let labelY: number;
  let labelAnchor: 'start' | 'end' | 'middle' = 'start';

  if (isBackEdge || crossesNode) {
    // Route around via rectangular path with rounded corners.
    // Key insight: never go horizontal at a node's Y level — that crosses sibling nodes.
    // Instead: exit RIGHT from source → immediately turn UP/DOWN → horizontal in the gap
    // between layers (no nodes there) → vertical to routing margin → into target.
    const R = 14; // corner radius
    const routeX = svgWidth - 25;
    const fromRight = fromPos.x + fromPos.w;
    const fromMidY = fromPos.y + fromPos.h / 2;
    const toRight = toPos.x + toPos.w;
    const toMidY = toPos.y + toPos.h / 2;

    if (isBackEdge) {
      // Back-edge: source is below, target is above.
      // Path: source right → up above source layer (gap) → right to routeX → up to target level → left into target
      const channelX = fromRight + R + 2; // just right of source, then go vertical
      const gapY = fromPos.y - 25;        // gap above source layer, safe from all nodes
      pathD = [
        `M ${fromRight} ${fromMidY}`,
        // Right then UP (rounded corner)
        `L ${channelX - R} ${fromMidY}`,
        `Q ${channelX} ${fromMidY}, ${channelX} ${fromMidY - R}`,
        // Up to gap above source layer
        `L ${channelX} ${gapY + R}`,
        // Turn RIGHT in gap (rounded corner)
        `Q ${channelX} ${gapY}, ${channelX + R} ${gapY}`,
        // Horizontal to routeX in the gap (no nodes here)
        `L ${routeX - R} ${gapY}`,
        // Turn UP at routeX (rounded corner)
        `Q ${routeX} ${gapY}, ${routeX} ${gapY - R}`,
        // Up to target midY level
        `L ${routeX} ${toMidY + R}`,
        // Turn LEFT toward target (rounded corner)
        `Q ${routeX} ${toMidY}, ${routeX - R} ${toMidY}`,
        // Left into target right side
        `L ${toRight} ${toMidY}`,
      ].join(' ');
      labelX = routeX + 6;
      labelY = (gapY + toMidY) / 2;
    } else {
      // Forward edge crossing nodes: route right side
      // Path: source right → down below source layer (gap) → right to routeX → down to target level → left into target
      let maxRight = 0;
      for (const pos of Object.values(allPositions)) {
        if (pos.name === fromPos.name || pos.name === toPos.name) continue;
        if (pos.layer >= fromPos.layer && pos.layer <= toPos.layer) {
          maxRight = Math.max(maxRight, pos.x + pos.w);
        }
      }
      const rX = Math.max(maxRight, fromRight, toRight) + 50 + spread;
      const channelX = fromRight + R + 2;
      const gapY = fromPos.y + fromPos.h + 25; // gap below source layer
      pathD = [
        `M ${fromRight} ${fromMidY}`,
        // Right then DOWN (rounded corner)
        `L ${channelX - R} ${fromMidY}`,
        `Q ${channelX} ${fromMidY}, ${channelX} ${fromMidY + R}`,
        // Down to gap below source layer
        `L ${channelX} ${gapY - R}`,
        // Turn RIGHT in gap (rounded corner)
        `Q ${channelX} ${gapY}, ${channelX + R} ${gapY}`,
        // Horizontal to routeX in the gap
        `L ${rX - R} ${gapY}`,
        // Turn DOWN at routeX (rounded corner)
        `Q ${rX} ${gapY}, ${rX} ${gapY + R}`,
        // Down to target midY level
        `L ${rX} ${toMidY - R}`,
        // Turn LEFT toward target (rounded corner)
        `Q ${rX} ${toMidY}, ${rX - R} ${toMidY}`,
        // Left into target right side
        `L ${toRight} ${toMidY}`,
      ].join(' ');
      labelX = rX + 6;
      labelY = (gapY + toMidY) / 2;
    }
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
        strokeWidth={strokeWidth}
        strokeDasharray={dashArray}
        markerEnd={`url(#arrow-${markerSuffix})`}
      />
      {isActive && (
        <path
          d={pathD}
          fill="none"
          stroke="#22d3ee"
          strokeWidth={3.5}
          strokeDasharray={dashArray}
          opacity={0.4}
        >
          <animate attributeName="opacity" values="0.15;0.5;0.15" dur="1.5s" repeatCount="indefinite" />
        </path>
      )}
      {edge.label && (
        <>
          <rect
            x={labelAnchor === 'end' ? labelX - edge.label.length * 7.5 - 4 : labelX - 3}
            y={labelY - 12}
            width={edge.label.length * 7.5 + 6}
            height={17}
            rx={3}
            fill="#0f172a"
            opacity={0.9}
          />
          <text
            x={labelX}
            y={labelY}
            fill={strokeColor}
            fontSize={12}
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

export function FlowDiagram({ definition, activeState, previousState, flowStatus, toolUsageByState = {} }: {
  definition: FlowDefinitionData;
  activeState?: string;
  previousState?: string;
  flowStatus?: string;
  toolUsageByState?: Record<string, Record<string, number>>;
}) {
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
          <marker id="arrow-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#22d3ee" />
          </marker>
        </defs>

        {/* Edges (rendered first = behind nodes) */}
        {edges.map((edge, i) => {
          const fromPos = positions[edge.from];
          const toPos = positions[edge.to];
          if (!fromPos || !toPos) return null;
          const sourceEdges = edgesBySource[edge.from] || [];
          const edgeIndex = sourceEdges.indexOf(edge);
          // Highlight edge connecting previousState → activeState (only while running)
          const edgeIsActive = flowStatus === 'running' && !!(previousState && activeState
            && edge.from === previousState && edge.to === activeState);
          return (
            <EdgeLine
              key={`${edge.from}-${edge.to}-${edge.label}-${i}`}
              edge={edge}
              fromPos={fromPos}
              toPos={toPos}
              allEdgesFromSame={sourceEdges.length}
              edgeIndex={edgeIndex}
              svgWidth={width}
              isActive={edgeIsActive}
              allPositions={positions}
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
              isActive={flowStatus === 'running' && stateName === activeState}
              isHighlighted={flowStatus !== 'running' && stateName === activeState}
              toolUsage={toolUsageByState[stateName]}
            />
          );
        })}
      </svg>
    </div>
  );
}
