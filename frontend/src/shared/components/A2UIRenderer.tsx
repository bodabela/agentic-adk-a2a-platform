/**
 * A2UI Renderer — renders A2UI declarative JSON payloads as interactive UI.
 *
 * Interprets the A2UI v0.8 message format (beginRendering, surfaceUpdate,
 * dataModelUpdate) and renders components (Card, Column, Row, Text, Button,
 * TextField, Image, Divider, List) as React elements.
 *
 * Styling philosophy: inherit as much as possible from the host environment.
 * Only structural layout (flex, gap) and minimal skin (border-radius, padding)
 * are set inline.  Colors, fonts, and sizes come from CSS inheritance and
 * the small set of CSS custom properties listed below.
 *
 * Custom properties the host can set (all optional, sensible defaults):
 *   --a2ui-primary          accent / primary button color
 *   --a2ui-radius           border-radius for cards, buttons, inputs
 *   --a2ui-card-bg          card background (default: transparent)
 *   --a2ui-card-border      card border color (default: currentColor @ 20%)
 *   --a2ui-input-bg         input field background (default: transparent)
 *   --a2ui-input-border     input field border color (default: currentColor @ 25%)
 *   --a2ui-divider          divider color (default: currentColor @ 20%)
 *   --a2ui-muted            muted text (labels, secondary) (default: inherit @ 60%)
 *   --a2ui-btn-secondary-bg secondary button bg (default: transparent)
 *   --a2ui-btn-secondary-border secondary button border (default: currentColor @ 30%)
 */

import { useState, useMemo, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────────── */

interface A2UIMessage {
  beginRendering?: {
    surfaceId: string;
    root: string;
    styles?: { primaryColor?: string; font?: string };
  };
  surfaceUpdate?: {
    surfaceId: string;
    components: A2UIComponentDef[];
  };
  dataModelUpdate?: {
    surfaceId: string;
    path: string;
    contents: A2UIDataEntry[];
  };
}

interface A2UIComponentDef {
  id: string;
  weight?: number;
  component: Record<string, unknown>;
}

interface A2UIDataEntry {
  key: string;
  valueString?: string;
  valueNumber?: number;
  valueBool?: boolean;
  valueMap?: A2UIDataEntry[];
}

interface A2UIAction {
  name: string;
  context?: { key: string; value: unknown }[];
}

/* ── Data model helpers ────────────────────────────────── */

function buildDataModel(entries: A2UIDataEntry[]): Record<string, unknown> {
  const model: Record<string, unknown> = {};
  for (const entry of entries) {
    if (entry.valueString !== undefined) {
      model[entry.key] = entry.valueString;
    } else if (entry.valueNumber !== undefined) {
      model[entry.key] = entry.valueNumber;
    } else if (entry.valueBool !== undefined) {
      model[entry.key] = entry.valueBool;
    } else if (entry.valueMap) {
      const sub = buildDataModel(entry.valueMap);
      model[entry.key] = sub;
    }
  }
  return model;
}

function resolveValue(
  ref: unknown,
  data: Record<string, unknown>,
  itemData?: Record<string, unknown>,
): string {
  if (!ref || typeof ref !== 'object') return String(ref ?? '');
  const obj = ref as Record<string, unknown>;
  if ('literalString' in obj) return String(obj.literalString);
  if ('path' in obj) {
    const path = String(obj.path);
    const key = path.replace(/^\//, '');
    if (itemData && key in itemData) return String(itemData[key] ?? '');
    return String(data[key] ?? '');
  }
  return '';
}

/* ── CSS custom property helpers ─────────────────────── */

const v = (name: string, fallback: string) => `var(${name}, ${fallback})`;

const PRIMARY = '--a2ui-primary';
const RADIUS = '--a2ui-radius';
const CARD_BG = '--a2ui-card-bg';
const CARD_BORDER = '--a2ui-card-border';
const INPUT_BG = '--a2ui-input-bg';
const INPUT_BORDER = '--a2ui-input-border';
const DIVIDER = '--a2ui-divider';
const MUTED = '--a2ui-muted';
const BTN_SEC_BG = '--a2ui-btn-secondary-bg';
const BTN_SEC_BORDER = '--a2ui-btn-secondary-border';

/* ── Component renderers ───────────────────────────────── */

function RenderComponent({
  id,
  components,
  data,
  styles,
  itemData,
  onAction,
  formState,
  onFormChange,
}: {
  id: string;
  components: Map<string, A2UIComponentDef>;
  data: Record<string, unknown>;
  styles: { primaryColor: string; font: string };
  itemData?: Record<string, unknown>;
  onAction: (action: A2UIAction, itemData?: Record<string, unknown>) => void;
  formState: Record<string, string>;
  onFormChange: (key: string, value: string) => void;
}) {
  const def = components.get(id);
  if (!def) return null;

  const comp = def.component;
  const type = Object.keys(comp)[0];
  const props = (comp[type] || {}) as Record<string, unknown>;

  const radius = v(RADIUS, '6px');

  switch (type) {
    case 'Column': {
      const childIds = getChildren(props, data);
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%' }}>
          {childIds.map((cid) => (
            <RenderComponent key={cid} id={cid} components={components} data={data}
              styles={styles} itemData={itemData} onAction={onAction}
              formState={formState} onFormChange={onFormChange} />
          ))}
        </div>
      );
    }

    case 'Row': {
      const childIds = getChildren(props, data);
      return (
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', width: '100%' }}>
          {childIds.map((cid) => {
            const childDef = components.get(cid);
            const weight = childDef?.weight || 1;
            return (
              <div key={cid} style={{ flex: weight }}>
                <RenderComponent id={cid} components={components} data={data}
                  styles={styles} itemData={itemData} onAction={onAction}
                  formState={formState} onFormChange={onFormChange} />
              </div>
            );
          })}
        </div>
      );
    }

    case 'Card': {
      const childId = props.child as string;
      return (
        <div style={{
          background: v(CARD_BG, 'transparent'),
          border: `1px solid ${v(CARD_BORDER, 'color-mix(in srgb, currentColor 20%, transparent)')}`,
          borderRadius: radius,
          padding: '1rem',
        }}>
          {childId && (
            <RenderComponent id={childId} components={components} data={data}
              styles={styles} itemData={itemData} onAction={onAction}
              formState={formState} onFormChange={onFormChange} />
          )}
        </div>
      );
    }

    case 'Text': {
      const text = resolveValue(props.text, data, itemData);
      const hint = props.usageHint as string;
      const isHeading = hint && hint.startsWith('h');
      const fontSize = hint === 'h1' ? '1.4em'
        : hint === 'h2' ? '1.2em'
        : hint === 'h3' ? '1.05em'
        : hint === 'h5' ? '0.85em'
        : undefined;
      const fontWeight = isHeading ? 600 : undefined;
      const color = isHeading ? undefined : v(MUTED, 'color-mix(in srgb, currentColor 80%, transparent)');
      return (
        <div style={{ fontSize, fontWeight, color, lineHeight: 1.5 }}>
          {text}
        </div>
      );
    }

    case 'Button': {
      const childId = props.child as string;
      const primary = props.primary as boolean;
      const action = props.action as A2UIAction | undefined;
      const primaryColor = v(PRIMARY, styles.primaryColor);
      return (
        <button
          onClick={() => action && onAction(action, itemData)}
          style={{
            padding: '0.5rem 1.25rem',
            background: primary ? primaryColor : v(BTN_SEC_BG, 'transparent'),
            color: primary ? '#fff' : 'inherit',
            border: primary ? 'none' : `1px solid ${v(BTN_SEC_BORDER, 'color-mix(in srgb, currentColor 30%, transparent)')}`,
            borderRadius: radius,
            cursor: 'pointer',
            fontSize: 'inherit',
            fontFamily: 'inherit',
            fontWeight: 500,
            width: '100%',
          }}
        >
          {childId ? (
            <RenderComponent id={childId} components={components} data={data}
              styles={styles} itemData={itemData} onAction={onAction}
              formState={formState} onFormChange={onFormChange} />
          ) : 'Click'}
        </button>
      );
    }

    case 'TextField': {
      const label = resolveValue(props.label, data, itemData);
      const placeholder = resolveValue(props.placeholder, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {label && (
            <label style={{ color: v(MUTED, 'color-mix(in srgb, currentColor 60%, transparent)'), fontSize: '0.85em' }}>
              {label}
            </label>
          )}
          <input
            type="text"
            placeholder={placeholder}
            value={formState[binding] ?? ''}
            onChange={(e) => onFormChange(binding, e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              background: v(INPUT_BG, 'transparent'),
              border: `1px solid ${v(INPUT_BORDER, 'color-mix(in srgb, currentColor 25%, transparent)')}`,
              borderRadius: radius,
              color: 'inherit',
              fontSize: 'inherit',
              fontFamily: 'inherit',
              outline: 'none',
            }}
          />
        </div>
      );
    }

    case 'NumberField': {
      const label = resolveValue(props.label, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {label && (
            <label style={{ color: v(MUTED, 'color-mix(in srgb, currentColor 60%, transparent)'), fontSize: '0.85em' }}>
              {label}
            </label>
          )}
          <input
            type="number"
            value={formState[binding] ?? ''}
            onChange={(e) => onFormChange(binding, e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              background: v(INPUT_BG, 'transparent'),
              border: `1px solid ${v(INPUT_BORDER, 'color-mix(in srgb, currentColor 25%, transparent)')}`,
              borderRadius: radius,
              color: 'inherit',
              fontSize: 'inherit',
              fontFamily: 'inherit',
              outline: 'none',
              width: 100,
            }}
          />
        </div>
      );
    }

    case 'Image': {
      const url = resolveValue(props.url, data, itemData);
      if (!url) return null;
      return (
        <img
          src={url}
          alt=""
          style={{ maxWidth: '100%', borderRadius: radius, maxHeight: 200, objectFit: 'cover' }}
        />
      );
    }

    case 'Divider':
      return (
        <hr style={{
          border: 'none',
          borderTop: `1px solid ${v(DIVIDER, 'color-mix(in srgb, currentColor 20%, transparent)')}`,
          margin: '0.5rem 0',
        }} />
      );

    case 'Checkbox': {
      const label = resolveValue(props.label, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      const checked = formState[binding] === 'true';
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={checked}
            onChange={() => onFormChange(binding, checked ? 'false' : 'true')}
            style={{ accentColor: v(PRIMARY, styles.primaryColor), width: '1.1em', height: '1.1em' }}
          />
          {label && <span>{label}</span>}
        </label>
      );
    }

    case 'RadioButton': {
      const label = resolveValue(props.label, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      const value = resolveValue(props.value, data, itemData);
      const checked = formState[binding] === value;
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input
            type="radio"
            name={binding}
            checked={checked}
            onChange={() => onFormChange(binding, value)}
            style={{ accentColor: v(PRIMARY, styles.primaryColor), width: '1.1em', height: '1.1em' }}
          />
          {label && <span>{label}</span>}
        </label>
      );
    }

    case 'Dropdown': {
      const label = resolveValue(props.label, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      const optionsBinding = String(props.optionsBinding || '').replace(/^\//, '');
      const items = optionsBinding && data[optionsBinding] && typeof data[optionsBinding] === 'object'
        ? Object.values(data[optionsBinding] as Record<string, Record<string, unknown>>)
        : [];
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {label && (
            <label style={{ color: v(MUTED, 'color-mix(in srgb, currentColor 60%, transparent)'), fontSize: '0.85em' }}>
              {label}
            </label>
          )}
          <select
            value={formState[binding] ?? ''}
            onChange={(e) => onFormChange(binding, e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              background: v(INPUT_BG, 'transparent'),
              border: `1px solid ${v(INPUT_BORDER, 'color-mix(in srgb, currentColor 25%, transparent)')}`,
              borderRadius: radius,
              color: 'inherit',
              fontSize: 'inherit',
              fontFamily: 'inherit',
            }}
          >
            <option value="">—</option>
            {items.map((item, idx) => {
              const val = String(item.value ?? item.label ?? '');
              const lbl = String(item.label ?? item.value ?? '');
              return <option key={idx} value={val}>{lbl}</option>;
            })}
          </select>
        </div>
      );
    }

    case 'List': {
      const children = props.children as Record<string, unknown>;
      if (!children) return null;

      const template = children.template as { componentId: string; dataBinding: string } | undefined;
      if (template) {
        const binding = template.dataBinding.replace(/^\//, '');
        const items = data[binding];
        if (!items || typeof items !== 'object') return null;

        const itemEntries = Object.values(items as Record<string, unknown>);
        const direction = (props.direction as string) === 'horizontal' ? 'row' : 'column';
        return (
          <div style={{ display: 'flex', flexDirection: direction, gap: '0.5rem' }}>
            {itemEntries.map((item, idx) => (
              <RenderComponent
                key={idx}
                id={template.componentId}
                components={components}
                data={data}
                styles={styles}
                itemData={item as Record<string, unknown>}
                onAction={onAction}
                formState={formState}
                onFormChange={onFormChange}
              />
            ))}
          </div>
        );
      }

      const explicitList = children.explicitList as string[];
      if (explicitList) {
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {explicitList.map((cid) => (
              <RenderComponent key={cid} id={cid} components={components} data={data}
                styles={styles} itemData={itemData} onAction={onAction}
                formState={formState} onFormChange={onFormChange} />
            ))}
          </div>
        );
      }

      return null;
    }

    case 'DateTimePicker': {
      const label = resolveValue(props.label, data, itemData);
      const binding = String(props.dataBinding || '').replace(/^\//, '');
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {label && (
            <label style={{ color: v(MUTED, 'color-mix(in srgb, currentColor 60%, transparent)'), fontSize: '0.85em' }}>
              {label}
            </label>
          )}
          <input
            type="datetime-local"
            value={formState[binding] ?? ''}
            onChange={(e) => onFormChange(binding, e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              background: v(INPUT_BG, 'transparent'),
              border: `1px solid ${v(INPUT_BORDER, 'color-mix(in srgb, currentColor 25%, transparent)')}`,
              borderRadius: radius,
              color: 'inherit',
              fontSize: 'inherit',
              fontFamily: 'inherit',
            }}
          />
        </div>
      );
    }

    default:
      return <div style={{ opacity: 0.5, fontSize: '0.8em' }}>[{type}]</div>;
  }
}

function getChildren(props: Record<string, unknown>, _data: Record<string, unknown>): string[] {
  const children = props.children as Record<string, unknown>;
  if (!children) return [];
  if (children.explicitList) return children.explicitList as string[];
  return [];
}

/* ── Main renderer ─────────────────────────────────────── */

export function A2UIRenderer({
  payload,
  onSubmit,
}: {
  payload: Record<string, unknown>[];
  onSubmit: (response: unknown) => void;
}) {
  const [formState, setFormState] = useState<Record<string, string>>({});

  const { rootId, components, data, styles } = useMemo(() => {
    let rootId = '';
    const components = new Map<string, A2UIComponentDef>();
    let data: Record<string, unknown> = {};
    let styles = { primaryColor: '#3b82f6', font: 'inherit' };

    for (const msg of payload as A2UIMessage[]) {
      if (msg.beginRendering) {
        rootId = msg.beginRendering.root;
        if (msg.beginRendering.styles) {
          styles = {
            primaryColor: msg.beginRendering.styles.primaryColor || styles.primaryColor,
            font: msg.beginRendering.styles.font || styles.font,
          };
        }
      }
      if (msg.surfaceUpdate) {
        for (const comp of msg.surfaceUpdate.components) {
          components.set(comp.id, comp);
        }
      }
      if (msg.dataModelUpdate) {
        data = { ...data, ...buildDataModel(msg.dataModelUpdate.contents) };
      }
    }

    return { rootId, components, data, styles };
  }, [payload]);

  const handleFormChange = useCallback((key: string, value: string) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleAction = useCallback((action: A2UIAction, itemData?: Record<string, unknown>) => {
    const response: Record<string, unknown> = { action: action.name };
    if (action.context) {
      for (const ctx of action.context) {
        const val = resolveValue(ctx.value, { ...data, ...formState }, itemData);
        response[ctx.key] = val || formState[ctx.key] || '';
      }
    }
    for (const [k, v] of Object.entries(formState)) {
      if (!(k in response)) response[k] = v;
    }
    onSubmit(response);
  }, [data, formState, onSubmit]);

  if (!rootId || components.size === 0) {
    return <div>Invalid A2UI payload</div>;
  }

  return (
    <div style={{ fontFamily: styles.font, color: 'inherit' }}>
      <RenderComponent
        id={rootId}
        components={components}
        data={data}
        styles={styles}
        onAction={handleAction}
        formState={formState}
        onFormChange={handleFormChange}
      />
    </div>
  );
}
