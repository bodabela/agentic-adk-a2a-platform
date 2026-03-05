import { useMemo } from 'react';

/* ── Types ─────────────────────────────────────────────── */

interface TaskEvent {
  event_type: string;
  timestamp: string;
  data: unknown;
}

interface DiagramNode {
  name: string;
  type: 'orchestrator' | 'agent' | 'user';
}

interface DiagramEdge {
  from: string;
  to: string;
  index: number;
  label: string;
  type: 'forward' | 'return';
}

interface NodePos {
  x: number;
  y: number;
  w: number;
  h: number;
}

/* ── Style constants ───────────────────────────────────── */

const NODE_W = 160;
const NODE_H = 52;
const TOOL_BADGE_H = 18;
const TOOL_BADGE_GAP = 3;
const H_GAP = 60;
const V_GAP = 70;
const PADDING = 40;

const NODE_COLORS: Record<string, string> = {
  orchestrator: '#8b5cf6',
  agent: '#3b82f6',
  user: '#f59e0b',
};

/* ── Data extraction from events ───────────────────────── */

function extractGraph(events: TaskEvent[]) {
  const nodesMap = new Map<string, DiagramNode>();
  const edges: DiagramEdge[] = [];
  let activeAgent = '';
  let lastAskUserAgent = '';
  let completed = false;
  // Track last transfer target so we can detect implicit returns
  let lastTransferTarget = '';
  let expectingReturn = false;

  for (const ev of events) {
    const d = ev.data as Record<string, unknown>;
    const agent = (d.agent as string) || (d.author as string) || '';

    if (agent && !nodesMap.has(agent)) {
      const type = agent === 'orchestrator' ? 'orchestrator' : 'agent';
      nodesMap.set(agent, { name: agent, type });
    }

    // Detect implicit return: agent activity switches back without explicit transfer
    if (agent && ['streaming_text', 'tool_call', 'agent_response', 'thinking'].includes(ev.event_type)) {
      if (expectingReturn && agent !== lastTransferTarget && agent !== activeAgent && lastTransferTarget) {
        // Control returned implicitly (LoopAgent re-ran orchestrator)
        edges.push({
          from: lastTransferTarget, to: agent,
          index: edges.length + 1, label: 'return', type: 'return',
        });
        expectingReturn = false;
      }
      activeAgent = agent;
    }

    if (ev.event_type === 'tool_call') {
      const toolName = d.tool_name as string;
      const toolArgs = (d.tool_args as Record<string, unknown>) || {};

      if (toolName === 'transfer_to_agent' && agent) {
        const target = toolArgs.agent_name as string;
        if (target) {
          if (!nodesMap.has(target)) {
            const type = target === 'orchestrator' ? 'orchestrator' : 'agent';
            nodesMap.set(target, { name: target, type });
          }
          edges.push({ from: agent, to: target, index: edges.length + 1, label: 'transfer', type: 'forward' });
          lastTransferTarget = target;
          expectingReturn = true;
        }
      }

      if (toolName === 'ask_user' && agent) {
        lastAskUserAgent = agent;
        if (!nodesMap.has('user')) {
          nodesMap.set('user', { name: 'user', type: 'user' });
        }
        edges.push({ from: agent, to: 'user', index: edges.length + 1, label: 'ask', type: 'forward' });
        lastTransferTarget = 'user';
        expectingReturn = true;
      }

      if (toolName === 'exit_loop') {
        completed = true;
      }
    }

    if (ev.event_type === 'user_response') {
      if (!nodesMap.has('user')) {
        nodesMap.set('user', { name: 'user', type: 'user' });
      }
      const returnTo = lastAskUserAgent || 'user_agent';
      edges.push({ from: 'user', to: returnTo, index: edges.length + 1, label: 'response', type: 'forward' });
      lastTransferTarget = returnTo;
      expectingReturn = true;
      activeAgent = 'user';
    }
  }

  // Count tool usage per agent (exclude orchestration tools)
  const toolUsage: Record<string, Record<string, number>> = {};
  const ORCHESTRATION_TOOLS = new Set(['transfer_to_agent', 'exit_loop', 'ask_user']);
  for (const ev of events) {
    if (ev.event_type !== 'tool_call') continue;
    const d = ev.data as Record<string, unknown>;
    const agent = (d.agent as string) || (d.author as string) || '';
    const toolName = d.tool_name as string;
    if (!agent || !toolName || ORCHESTRATION_TOOLS.has(toolName)) continue;
    if (!toolUsage[agent]) toolUsage[agent] = {};
    toolUsage[agent][toolName] = (toolUsage[agent][toolName] || 0) + 1;
  }

  return {
    nodes: Array.from(nodesMap.values()),
    edges,
    activeAgent,
    completed,
    toolUsage,
  };
}

/* ── Tree layout computation ───────────────────────────── */

function computeLayout(
  nodes: DiagramNode[],
  edges: DiagramEdge[],
  toolUsage: Record<string, Record<string, number>>,
): { positions: Record<string, NodePos>; width: number; height: number } {
  if (nodes.length === 0) return { positions: {}, width: 0, height: 0 };

  const nodeNames = new Set(nodes.map((n) => n.name));

  // Build unique directed adjacency from forward edges only (returns don't define tree structure)
  const children = new Map<string, string[]>();
  const seen = new Set<string>();
  for (const edge of edges) {
    if (edge.type === 'return') continue;
    const key = `${edge.from}->${edge.to}`;
    if (!seen.has(key) && nodeNames.has(edge.from) && nodeNames.has(edge.to)) {
      seen.add(key);
      if (!children.has(edge.from)) children.set(edge.from, []);
      children.get(edge.from)!.push(edge.to);
    }
  }

  // Find root: orchestrator, or first node
  const root = nodes.find((n) => n.type === 'orchestrator')?.name || nodes[0].name;

  // BFS to assign layers (depth)
  const layerOf: Record<string, number> = {};
  const queue: string[] = [root];
  layerOf[root] = 0;
  while (queue.length > 0) {
    const cur = queue.shift()!;
    for (const child of children.get(cur) || []) {
      if (layerOf[child] === undefined) {
        layerOf[child] = layerOf[cur] + 1;
        queue.push(child);
      }
    }
  }

  // Assign unvisited nodes to max layer + 1
  const maxLayer = Math.max(0, ...Object.values(layerOf));
  for (const node of nodes) {
    if (layerOf[node.name] === undefined) {
      layerOf[node.name] = maxLayer + 1;
    }
  }

  // Group by layer
  const layers: Record<number, DiagramNode[]> = {};
  for (const node of nodes) {
    const l = layerOf[node.name];
    if (!layers[l]) layers[l] = [];
    layers[l].push(node);
  }

  const totalLayers = Math.max(...Object.keys(layers).map(Number)) + 1;

  // Compute max tool badges per layer for height calculation
  const layerToolExtra: number[] = [];
  for (let l = 0; l < totalLayers; l++) {
    let maxBadges = 0;
    for (const node of layers[l] || []) {
      const tools = toolUsage[node.name];
      const count = tools ? Object.keys(tools).length : 0;
      if (count > maxBadges) maxBadges = count;
    }
    layerToolExtra.push(maxBadges > 0 ? maxBadges * (TOOL_BADGE_H + TOOL_BADGE_GAP) + 4 : 0);
  }

  // Compute widest layer
  let maxLayerWidth = 0;
  for (let l = 0; l < totalLayers; l++) {
    const count = (layers[l] || []).length;
    const w = count * NODE_W + (count - 1) * H_GAP;
    if (w > maxLayerWidth) maxLayerWidth = w;
  }

  const totalWidth = maxLayerWidth + PADDING * 2;
  const positions: Record<string, NodePos> = {};

  let yOffset = PADDING;
  for (let l = 0; l < totalLayers; l++) {
    const nodesInLayer = layers[l] || [];
    const layerWidth = nodesInLayer.length * NODE_W + (nodesInLayer.length - 1) * H_GAP;
    let x = (totalWidth - layerWidth) / 2;

    for (const node of nodesInLayer) {
      positions[node.name] = { x, y: yOffset, w: NODE_W, h: NODE_H };
      x += NODE_W + H_GAP;
    }
    yOffset += NODE_H + layerToolExtra[l] + V_GAP;
  }

  const totalHeight = yOffset - V_GAP + PADDING;

  return { positions, width: totalWidth, height: totalHeight };
}

/* ── SVG node renderer ─────────────────────────────────── */

function DiagramNodeShape({ node, pos, isActive, isCompleted, taskStatus, tools }: {
  node: DiagramNode;
  pos: NodePos;
  isActive: boolean;
  isCompleted: boolean;
  taskStatus: string;
  tools?: Record<string, number>;
}) {
  const color = NODE_COLORS[node.type] || '#64748b';
  const cx = pos.x + pos.w / 2;
  const cy = pos.y + pos.h / 2;
  const showPulse = isActive && taskStatus !== 'completed' && taskStatus !== 'failed';

  const displayName = node.name === 'user' ? 'User' : node.name;
  const typeLabel = node.type === 'orchestrator' ? 'orchestrator'
    : node.type === 'user' ? 'human'
    : 'agent';

  const toolEntries = tools ? Object.entries(tools) : [];

  return (
    <g>
      {showPulse && (
        <>
          <rect
            x={pos.x - 6} y={pos.y - 6}
            width={pos.w + 12} height={pos.h + 12}
            rx={12} ry={12}
            fill="none" stroke="#22d3ee" strokeWidth={2.5} opacity={0.3}
          >
            <animate attributeName="opacity" values="0.1;0.5;0.1" dur="1.5s" repeatCount="indefinite" />
          </rect>
          <rect
            x={pos.x - 3} y={pos.y - 3}
            width={pos.w + 6} height={pos.h + 6}
            rx={10} ry={10}
            fill="none" stroke="#22d3ee" strokeWidth={2.5} opacity={0.8}
          >
            <animate attributeName="opacity" values="0.4;1;0.4" dur="1.5s" repeatCount="indefinite" />
          </rect>
        </>
      )}

      <rect
        x={pos.x} y={pos.y} width={pos.w} height={pos.h}
        rx={node.type === 'user' ? 16 : 6} ry={node.type === 'user' ? 16 : 6}
        fill={showPulse ? color + '30' : color + '18'}
        stroke={showPulse ? '#22d3ee' : color}
        strokeWidth={showPulse ? 2.5 : 2}
      >
        {showPulse && (
          <animate attributeName="fill" values={`${color}20;${color}40;${color}20`} dur="1.5s" repeatCount="indefinite" />
        )}
      </rect>

      <text
        x={cx} y={cy - 6}
        textAnchor="middle" fill="#e2e8f0" fontSize={13} fontWeight="600"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {displayName}
      </text>
      <text
        x={cx} y={cy + 12}
        textAnchor="middle" fill={color} fontSize={11}
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {typeLabel}
      </text>

      {isCompleted && (
        <text
          x={pos.x + pos.w - 8} y={pos.y + 14}
          textAnchor="middle" fill="#22c55e" fontSize={14}
        >
          ✓
        </text>
      )}

      {/* Tool usage badges below node */}
      {toolEntries.map(([toolName, count], i) => {
        const badgeY = pos.y + pos.h + 4 + i * (TOOL_BADGE_H + TOOL_BADGE_GAP);
        const label = `${toolName} ×${count}`;
        const badgeW = Math.min(pos.w, Math.max(80, label.length * 7 + 16));
        const badgeX = cx - badgeW / 2;
        return (
          <g key={toolName}>
            <rect
              x={badgeX} y={badgeY}
              width={badgeW} height={TOOL_BADGE_H}
              rx={4} ry={4}
              fill="#f59e0b18" stroke="#f59e0b" strokeWidth={0.8}
            />
            <text
              x={cx} y={badgeY + TOOL_BADGE_H / 2 + 3.5}
              textAnchor="middle" fill="#f59e0b" fontSize={10}
              fontFamily="system-ui, -apple-system, sans-serif"
            >
              {label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

/* ── SVG edge renderer ─────────────────────────────────── */

function DiagramEdgeLine({ edge, fromPos, toPos, isLatest, taskStatus, pairIndex, pairCount }: {
  edge: DiagramEdge;
  fromPos: NodePos;
  toPos: NodePos;
  isLatest: boolean;
  taskStatus: string;
  pairIndex: number;   // 0-based index among edges sharing this node pair
  pairCount: number;   // total edges between this node pair
}) {
  const isReturn = edge.type === 'return';

  const fromCx = fromPos.x + fromPos.w / 2;
  const fromCy = fromPos.y + fromPos.h / 2;
  const toCx = toPos.x + toPos.w / 2;
  const toCy = toPos.y + toPos.h / 2;

  // Spread: each edge in a pair gets a unique offset so endpoints never coincide
  const SPREAD = 22;
  const spreadOffset = pairCount > 1
    ? (pairIndex - (pairCount - 1) / 2) * SPREAD
    : 0;

  const dx = toCx - fromCx;
  const dy = toCy - fromCy;
  const isVertical = Math.abs(dy) > Math.abs(dx);

  // Connection points: spread along the node border so each arrow
  // starts/ends at a distinct point (not all converging to center)
  let startX: number, startY: number, endX: number, endY: number;

  if (isVertical) {
    // Vertical: arrows exit/enter top/bottom edges, spread along X
    if (dy > 0) {
      startX = fromCx + spreadOffset; startY = fromPos.y + fromPos.h;
      endX = toCx + spreadOffset;     endY = toPos.y;
    } else {
      startX = fromCx + spreadOffset; startY = fromPos.y;
      endX = toCx + spreadOffset;     endY = toPos.y + toPos.h;
    }
  } else {
    // Horizontal: arrows exit/enter left/right edges, spread along Y
    if (dx > 0) {
      startX = fromPos.x + fromPos.w; startY = fromCy + spreadOffset;
      endX = toPos.x;                 endY = toCy + spreadOffset;
    } else {
      startX = fromPos.x;             startY = fromCy + spreadOffset;
      endX = toPos.x + toPos.w;       endY = toCy + spreadOffset;
    }
  }

  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;

  // Curve: each edge gets a proportional bulge perpendicular to the line
  const baseCurve = pairCount > 1 ? spreadOffset * 1.5 : 0;
  let pathD: string;
  if (isVertical) {
    pathD = `M ${startX} ${startY} C ${startX + baseCurve} ${midY}, ${endX + baseCurve} ${midY}, ${endX} ${endY}`;
  } else {
    pathD = `M ${startX} ${startY} C ${midX} ${startY + baseCurve}, ${midX} ${endY + baseCurve}, ${endX} ${endY}`;
  }

  const showAnimation = isLatest && taskStatus !== 'completed' && taskStatus !== 'failed';

  const strokeColor = showAnimation ? '#22d3ee' : '#475569';
  const markerType = showAnimation ? 'active' : 'normal';
  const strokeWidth = isLatest ? 2 : 1.5;

  // Badge: sits on the curve midpoint, shifted with the curve so badges never overlap
  const curveShift = pairCount > 1 ? baseCurve * 0.5 : 0;
  const badgeX = midX + (isVertical ? curveShift : 0);
  const badgeY = midY + (isVertical ? 0 : curveShift);
  const badgeText = `${edge.index}`;

  return (
    <g>
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={isReturn ? '6 3' : undefined}
        markerEnd={`url(#task-arrow-${markerType})`}
      />
      {showAnimation && (
        <path
          d={pathD}
          fill="none"
          stroke={strokeColor}
          strokeWidth={2}
          strokeDasharray={isReturn ? '6 3' : undefined}
          opacity={0.6}
        >
          <animate attributeName="opacity" values="0.3;0.8;0.3" dur="1.5s" repeatCount="indefinite" />
        </path>
      )}

      {/* Index badge */}
      <circle cx={badgeX} cy={badgeY} r={10} fill="#0f172a" stroke={strokeColor} strokeWidth={1} />
      <text
        x={badgeX} y={badgeY + 4}
        textAnchor="middle" fill={strokeColor} fontSize={10} fontWeight="600"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {badgeText}
      </text>
    </g>
  );
}

/* ── Main component ────────────────────────────────────── */

export function TaskAgentDiagram({ events, status }: {
  events: TaskEvent[];
  status: string;
}) {
  const { nodes, edges, activeAgent, completed, toolUsage } = useMemo(
    () => extractGraph(events),
    [events],
  );

  const { positions, width, height } = useMemo(
    () => computeLayout(nodes, edges, toolUsage),
    [nodes, edges, toolUsage],
  );

  // Pre-compute pair groupings for edge spread
  const edgePairInfo = useMemo(() => {
    const pairMap = new Map<string, number[]>();
    edges.forEach((edge, i) => {
      const key = [edge.from, edge.to].sort().join('::');
      if (!pairMap.has(key)) pairMap.set(key, []);
      pairMap.get(key)!.push(i);
    });
    return edges.map((edge, i) => {
      const key = [edge.from, edge.to].sort().join('::');
      const group = pairMap.get(key)!;
      return { pairIndex: group.indexOf(i), pairCount: group.length };
    });
  }, [edges]);

  if (nodes.length === 0) return null;

  return (
    <div style={{
      overflow: 'auto',
      background: '#020617',
      borderRadius: 8,
      border: '1px solid #1e293b',
    }}>
      <div style={{
        padding: '0.5rem 1rem',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.95rem' }}>
          Agent Flow
        </span>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {edges.length > 0 && (
            <span style={{ color: '#64748b', fontSize: '0.8rem' }}>
              {edges.length} interaction{edges.length !== 1 ? 's' : ''}
            </span>
          )}
          {completed && (
            <span style={{
              color: '#22c55e', fontSize: '0.75rem',
              background: '#052e16', padding: '2px 8px', borderRadius: 4,
            }}>
              completed
            </span>
          )}
        </div>
      </div>

      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: 'block', minWidth: width, minHeight: Math.max(height, 80) }}
      >
        <defs>
          <marker id="task-arrow-normal" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#475569" />
          </marker>
          <marker id="task-arrow-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#22d3ee" />
          </marker>
        </defs>

        {/* Edges (behind nodes) */}
        {edges.map((edge, i) => {
          const fromPos = positions[edge.from];
          const toPos = positions[edge.to];
          if (!fromPos || !toPos) return null;
          const { pairIndex, pairCount } = edgePairInfo[i];
          return (
            <DiagramEdgeLine
              key={`${edge.from}-${edge.to}-${edge.index}`}
              edge={edge}
              fromPos={fromPos}
              toPos={toPos}
              isLatest={i === edges.length - 1}
              taskStatus={status}
              pairIndex={pairIndex}
              pairCount={pairCount}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = positions[node.name];
          if (!pos) return null;
          return (
            <DiagramNodeShape
              key={node.name}
              node={node}
              pos={pos}
              isActive={node.name === activeAgent}
              isCompleted={completed && node.name === 'orchestrator'}
              taskStatus={status}
              tools={toolUsage[node.name]}
            />
          );
        })}
      </svg>
    </div>
  );
}
