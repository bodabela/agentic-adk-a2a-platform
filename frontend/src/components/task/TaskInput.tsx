import { useState } from 'react';
import { useTaskStore } from '../../stores/taskStore';

export function TaskInput() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const submitTask = useTaskStore((s) => s.submitTask);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    setLoading(true);
    try {
      await submitTask(input.trim());
      setInput('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Describe a task for the agent..."
        disabled={loading}
        style={{
          flex: 1,
          padding: '0.625rem 1rem',
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 6,
          color: '#e2e8f0',
          fontSize: '0.875rem',
          outline: 'none',
        }}
      />
      <button
        type="submit"
        disabled={loading || !input.trim()}
        style={{
          padding: '0.625rem 1.5rem',
          background: '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          cursor: loading ? 'wait' : 'pointer',
          opacity: loading || !input.trim() ? 0.5 : 1,
          fontSize: '0.875rem',
        }}
      >
        {loading ? 'Sending...' : 'Submit'}
      </button>
    </form>
  );
}
