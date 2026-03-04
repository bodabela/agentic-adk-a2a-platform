import { TaskInput } from './TaskInput';
import { TaskTimeline } from './TaskTimeline';
import { AgentPanel } from './AgentPanel';

export function TaskPanel() {
  return (
    <div style={{ display: 'flex', gap: '1.5rem' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Submit Task
          </h2>
          <TaskInput />
        </div>
        <div>
          <h2 style={{ color: '#e2e8f0', fontSize: '1.25rem', marginBottom: '1rem' }}>
            Task History
          </h2>
          <TaskTimeline />
        </div>
      </div>
      <div style={{ width: 260, flexShrink: 0 }}>
        <AgentPanel />
      </div>
    </div>
  );
}
