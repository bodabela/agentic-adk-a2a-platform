import { useEffect, useRef, useCallback } from 'react';
import { useTaskStore } from '../stores/taskStore';
import { useFlowStore } from '../stores/flowStore';
import { useCostStore } from '../stores/costStore';

const FLOW_EVENTS = [
  'flow_started',
  'flow_state_entered',
  'flow_agent_task_started',
  'flow_agent_task_completed',
  'flow_agent_thinking',
  'flow_agent_tool_use',
  'flow_agent_tool_result',
  'flow_agent_streaming_text',
  'flow_llm_decision',
  'flow_input_required',
  'flow_user_response',
  'flow_completed',
  'flow_retry_exceeded',
];

export function useSSE() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const addTaskEvent = useTaskStore((s) => s.addEvent);
  const appendTaskStreamingText = useTaskStore((s) => s.appendStreamingText);
  const updateTaskStatus = useTaskStore((s) => s.updateTaskStatus);
  const addTaskInteraction = useTaskStore((s) => s.addInteraction);
  const updateFlowState = useFlowStore((s) => s.updateFlowState);
  const addFlowEvent = useFlowStore((s) => s.addFlowEvent);
  const appendFlowStreamingText = useFlowStore((s) => s.appendFlowStreamingText);
  const addInteraction = useFlowStore((s) => s.addInteraction);
  const addCostEvent = useCostStore((s) => s.addCostEvent);

  const connect = useCallback(() => {
    if (eventSourceRef.current) return;

    const es = new EventSource('/api/events/stream');

    es.onopen = () => console.log('[SSE] Connected');

    es.addEventListener('task_event', (e) => {
      const data = JSON.parse(e.data);
      if (data.event_type === 'streaming_text') {
        appendTaskStreamingText(
          data.task_id,
          data.text || '',
          data.agent || data.author || '',
          !!data.is_thought,
        );
      } else {
        addTaskEvent(data.task_id, {
          event_type: data.event_type,
          timestamp: new Date().toISOString(),
          data,
        });
      }
    });

    es.addEventListener('task_completed', (e) => {
      const data = JSON.parse(e.data);
      updateTaskStatus(data.task_id, 'completed');
    });

    es.addEventListener('task_failed', (e) => {
      const data = JSON.parse(e.data);
      updateTaskStatus(data.task_id, 'failed', data.error);
    });

    es.addEventListener('task_input_required', (e) => {
      const data = JSON.parse(e.data);
      addTaskInteraction({
        interaction_id: data.interaction_id,
        task_id: data.task_id,
        interaction_type: data.interaction_type,
        prompt: data.prompt,
        options: data.options,
      });
    });

    es.addEventListener('task_user_response', (e) => {
      const data = JSON.parse(e.data);
      addTaskEvent(data.task_id, {
        event_type: 'user_response',
        timestamp: new Date().toISOString(),
        data,
      });
    });

    // --- Flow events: update state + collect into timeline ---
    for (const eventName of FLOW_EVENTS) {
      es.addEventListener(eventName, (e) => {
        const data = JSON.parse(e.data);
        const flowId = data.flow_id;
        if (!flowId) return;

        // Streaming text uses append (typewriter effect)
        if (eventName === 'flow_agent_streaming_text') {
          appendFlowStreamingText(
            flowId,
            data.text || '',
            data.agent || data.author || '',
            !!data.is_thought,
          );
          return;
        }

        // Always add to event timeline
        addFlowEvent(flowId, {
          event_type: eventName,
          timestamp: new Date().toISOString(),
          data,
        });

        // State-specific updates
        switch (eventName) {
          case 'flow_started':
            updateFlowState(flowId, {
              flowId,
              flowName: data.flow_name,
              currentState: '',
              status: 'running',
              provider: data.provider as string,
              model: data.model as string,
              states: {},
              events: [],
            });
            break;
          case 'flow_state_entered':
            updateFlowState(flowId, { currentState: data.state });
            break;
          case 'flow_input_required':
            addInteraction({
              interaction_id: data.interaction_id,
              flow_id: flowId,
              interaction_type: data.interaction_type,
              prompt: data.prompt,
              options: data.options,
              questions: data.questions,
            });
            break;
          case 'flow_completed':
            updateFlowState(flowId, { status: 'completed', output: data.output });
            break;
        }
      });
    }

    es.addEventListener('cost_event', (e) => {
      const data = JSON.parse(e.data);
      const costUsd = (data.llm?.total_cost_usd || 0) + (data.tool?.invocation_cost_usd || 0);
      addCostEvent({
        event_id: data.event_id || '',
        task_id: data.task_id,
        timestamp: data.timestamp,
        module: data.module,
        agent: data.agent,
        operation_type: data.operation_type,
        llm: data.llm ? {
          provider: data.llm.provider,
          model: data.llm.model,
          input_tokens: data.llm.input_tokens || 0,
          output_tokens: data.llm.output_tokens || 0,
          cached_tokens: data.llm.cached_tokens || 0,
          thinking_tokens: data.llm.thinking_tokens || 0,
          cost_per_input_token: data.llm.cost_per_input_token || 0,
          cost_per_output_token: data.llm.cost_per_output_token || 0,
          total_cost_usd: data.llm.total_cost_usd || 0,
          latency_ms: data.llm.latency_ms || 0,
        } : null,
        tool: data.tool ? {
          tool_id: data.tool.tool_id,
          tool_source: data.tool.tool_source,
          invocation_cost_usd: data.tool.invocation_cost_usd || 0,
          latency_ms: data.tool.latency_ms || 0,
        } : null,
        cost_usd: costUsd,
        cumulative_task_cost_usd: data.cumulative_task_cost_usd || 0,
      });
    });

    es.onerror = () => {
      console.log('[SSE] Error, reconnecting in 3s...');
      es.close();
      eventSourceRef.current = null;
      setTimeout(connect, 3000);
    };

    eventSourceRef.current = es;
  }, [addTaskEvent, appendTaskStreamingText, updateTaskStatus, addTaskInteraction, updateFlowState, addFlowEvent, appendFlowStreamingText, addInteraction, addCostEvent]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [connect]);
}
