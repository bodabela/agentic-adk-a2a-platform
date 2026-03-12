/**
 * Shared badge components for agent capabilities and tools.
 *
 * These must be used consistently everywhere agents are displayed:
 *  - AgentPanel (Tasks page sidebar)
 *  - AgentsPage (overview & list cards)
 *  - Any future component that shows agent capabilities/tools
 *
 * Color scheme:
 *   Capabilities → blue   (#1e3a5f / #60a5fa)
 *   Tools        → green  (#14532d / #4ade80)
 */

import type { CSSProperties } from 'react';

// ── Styles ──────────────────────────────────────────────────────────────

const baseBadge: CSSProperties = {
  fontSize: '0.8rem',
  padding: '0.15rem 0.45rem',
  borderRadius: 4,
  fontFamily: 'inherit',
};

const capabilityStyle: CSSProperties = {
  ...baseBadge,
  background: '#1e3a5f',
  color: '#60a5fa',
};

const toolStyle: CSSProperties = {
  ...baseBadge,
  background: '#14532d',
  color: '#4ade80',
};

// ── Components ──────────────────────────────────────────────────────────

export function CapabilityBadge({ name }: { name: string }) {
  return <span style={capabilityStyle}>{name}</span>;
}

export function ToolBadge({ name }: { name: string }) {
  return <span style={toolStyle}>{name}</span>;
}

/** Render a row of capability badges. */
export function CapabilityBadges({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
      {items.map((cap) => (
        <CapabilityBadge key={cap} name={cap} />
      ))}
    </div>
  );
}

/** Render a row of tool badges. */
export function ToolBadges({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
      {items.map((tool) => (
        <ToolBadge key={tool} name={tool} />
      ))}
    </div>
  );
}
