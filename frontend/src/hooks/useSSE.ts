import { useEffect, useRef, useCallback } from 'react';
import { useTaskStore } from '../stores/taskStore';
import { useFlowStore } from '../stores/flowStore';
import { useCostStore } from '../stores/costStore';

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const addTaskEvent = useTaskStore((s) => s.addEvent);
  const updateTaskStatus = useTaskStore((s) => s.updateTaskStatus);
  const updateFlowState = useFlowStore((s) => s.updateFlowState);
  const addInteraction = useFlowStore((s) => s.addInteraction);
  const addCostEvent = useCostStore((s) => s.addCostEvent);

  const connect = useCallback(() => {
    if (eventSourceRef.current) return;

    const es = new EventSource('/api/events/stream');

    es.onopen = () => console.log('[SSE] Connected');

    es.addEventListener('task_event', (e) => {
      const data = JSON.parse(e.data);
      addTaskEvent(data.task_id, {
        event_type: data.event_type,
        timestamp: new Date().toISOString(),
        data,
      });
    });

    es.addEventListener('task_completed', (e) => {
      const data = JSON.parse(e.data);
      updateTaskStatus(data.task_id, 'completed');
    });

    es.addEventListener('task_failed', (e) => {
      const data = JSON.parse(e.data);
      updateTaskStatus(data.task_id, 'failed', data.error);
    });

    es.addEventListener('flow_started', (e) => {
      const data = JSON.parse(e.data);
      updateFlowState(data.flow_id, {
        flowId: data.flow_id,
        flowName: data.flow_name,
        currentState: '',
        status: 'running',
        states: {},
      });
    });

    es.addEventListener('flow_state_entered', (e) => {
      const data = JSON.parse(e.data);
      updateFlowState(data.flow_id, { currentState: data.state });
    });

    es.addEventListener('flow_input_required', (e) => {
      const data = JSON.parse(e.data);
      addInteraction({
        interaction_id: data.interaction_id,
        flow_id: data.flow_id,
        interaction_type: data.interaction_type,
        prompt: data.prompt,
        options: data.options,
      });
    });

    es.addEventListener('flow_completed', (e) => {
      const data = JSON.parse(e.data);
      updateFlowState(data.flow_id, { status: 'completed' });
    });

    es.addEventListener('cost_event', (e) => {
      const data = JSON.parse(e.data);
      addCostEvent({
        task_id: data.task_id,
        module: data.module,
        agent: data.agent,
        operation_type: data.operation_type,
        cost_usd: data.llm?.total_cost_usd || 0,
        timestamp: data.timestamp,
      });
    });

    es.onerror = () => {
      console.log('[SSE] Error, reconnecting in 3s...');
      es.close();
      eventSourceRef.current = null;
      setTimeout(connect, 3000);
    };

    eventSourceRef.current = es;
  }, [addTaskEvent, updateTaskStatus, updateFlowState, addInteraction, addCostEvent]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [connect]);
}
