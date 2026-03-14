/**
 * SimpleMarkdown — lightweight inline markdown renderer.
 *
 * Supports: **bold**, *italic*, `code`, [links](url), \n line breaks.
 * No external dependencies.
 */

import { useMemo } from 'react';

interface SimpleMarkdownProps {
  text: string;
  style?: React.CSSProperties;
}

/**
 * Parse a markdown string into an array of React nodes.
 *
 * Supported syntax:
 *   **bold**  or  __bold__
 *   *italic*  or  _italic_
 *   `inline code`
 *   [link text](url)
 *   \n → <br />
 */
function parseMarkdown(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Pattern order matters: bold before italic to avoid conflicts
  const pattern = /(\*\*(.+?)\*\*|__(.+?)__|`(.+?)`|\*(.+?)\*|_(.+?)_|\[(.+?)\]\((.+?)\)|\n)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    // Push text before this match
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[2] || match[3]) {
      // **bold** or __bold__
      nodes.push(<strong key={key++}>{match[2] || match[3]}</strong>);
    } else if (match[4]) {
      // `code`
      nodes.push(
        <code key={key++} style={{
          background: 'rgba(255,255,255,0.1)',
          padding: '0.1em 0.35em',
          borderRadius: 3,
          fontSize: '0.9em',
        }}>
          {match[4]}
        </code>
      );
    } else if (match[5] || match[6]) {
      // *italic* or _italic_
      nodes.push(<em key={key++}>{match[5] || match[6]}</em>);
    } else if (match[7] && match[8]) {
      // [text](url)
      nodes.push(
        <a key={key++} href={match[8]} target="_blank" rel="noopener noreferrer"
          style={{ color: 'inherit', textDecoration: 'underline' }}>
          {match[7]}
        </a>
      );
    } else if (match[0] === '\n') {
      nodes.push(<br key={key++} />);
    }

    lastIndex = match.index + match[0].length;
  }

  // Push remaining text
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

export function SimpleMarkdown({ text, style }: SimpleMarkdownProps) {
  const nodes = useMemo(() => parseMarkdown(text), [text]);
  return <span style={style}>{nodes}</span>;
}
