"""Flow Engine - event-driven reactive state machine executor."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

logger = logging.getLogger("flow_engine")

from src.cost.tracker import CostTracker
from src.events.bus import EventBus
from src.flow_engine.context import FlowContext
from src.flow_engine.dsl.parser import ParsedFlow
from src.flow_engine.dsl.schema import (
    AgentTaskNode,
    ConditionalNode,
    HumanInteractionNode,
    LLMDecisionNode,
    ParallelNode,
    TerminalNode,
    TriggerFlowNode,
    WaitForEventNode,
)
from src.flow_engine.parallel import ParallelExecutor
from src.flow_engine.retry_manager import RetryLimitExceeded, RetryManager
from src.flow_engine.state_store import (
    FlowExecutionState,
    FlowStatus,
    InMemoryStateStore,
)

if TYPE_CHECKING:
    from src.llm.config import LLMProvidersConfig
    from src.orchestrator.agent_registry import AgentRegistry


class FlowEngine:
    """Executes a parsed flow definition as a reactive state machine."""

    def __init__(
        self,
        event_bus: EventBus,
        cost_tracker: CostTracker,
        state_store: InMemoryStateStore | None = None,
        llm_config: LLMProvidersConfig | None = None,
        runtime_provider: str | None = None,
        runtime_model: str | None = None,
        agent_registry: AgentRegistry | None = None,
    ):
        self.event_bus = event_bus
        self.cost_tracker = cost_tracker
        self.state_store = state_store or InMemoryStateStore()
        self.llm_config = llm_config
        self.runtime_provider = runtime_provider
        self.runtime_model = runtime_model
        self.agent_registry = agent_registry
        self._pending_interactions: dict[str, asyncio.Future] = {}

    async def execute_flow(
        self,
        flow: ParsedFlow,
        trigger_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a flow from start to completion."""
        flow_id = str(uuid.uuid4())
        context = FlowContext(trigger_input=trigger_input)
        retry_mgr = RetryManager(flow.config)
        parallel_exec = ParallelExecutor(flow.config.max_parallel_branches)

        exec_state = FlowExecutionState(
            flow_id=flow_id,
            flow_name=flow.name,
            status=FlowStatus.RUNNING,
            current_state=flow.get_initial_state(),
            started_at=datetime.now(),
        )
        await self.state_store.save(exec_state)
        await self.event_bus.emit(
            "flow_started", {
                "flow_id": flow_id,
                "flow_name": flow.name,
                "provider": self.runtime_provider or flow.config.provider or "",
                "model": self.runtime_model or flow.config.get_effective_model() or "",
            }
        )

        current_state = flow.get_initial_state()

        while current_state:
            node = flow.get_node(current_state)
            if node is None:
                raise ValueError(f"State '{current_state}' not found in flow")

            exec_state.current_state = current_state
            await self.state_store.save(exec_state)
            await self.event_bus.emit(
                "flow_state_entered",
                {
                    "flow_id": flow_id,
                    "state": current_state,
                    "node_type": node.type,
                },
            )

            try:
                next_state = await self._execute_node(
                    node,
                    current_state,
                    context,
                    flow,
                    retry_mgr,
                    parallel_exec,
                    flow_id,
                )
            except RetryLimitExceeded as e:
                await self.event_bus.emit(
                    "flow_retry_exceeded",
                    {"flow_id": flow_id, "loop": e.loop_name},
                )
                if hasattr(node, "on_error") and node.on_error:
                    next_state = node.on_error
                else:
                    exec_state.status = FlowStatus.FAILED
                    exec_state.error = str(e)
                    await self.state_store.save(exec_state)
                    break
            except Exception as e:
                context.flow_vars["_last_error"] = str(e)
                if hasattr(node, "on_error") and node.on_error:
                    next_state = node.on_error
                else:
                    exec_state.status = FlowStatus.FAILED
                    exec_state.error = str(e)
                    await self.state_store.save(exec_state)
                    break

            # Apply side effects (flow variable assignments)
            if hasattr(node, "side_effect") and node.side_effect:
                for key, value_template in node.side_effect.set.items():
                    resolved = context.resolve(value_template)
                    context.set_flow_var(key, resolved)

            # Check for terminal state
            if isinstance(node, TerminalNode):
                exec_state.status = FlowStatus.COMPLETED
                exec_state.completed_at = datetime.now()
                await self.state_store.save(exec_state)
                await self.event_bus.emit(
                    "flow_completed",
                    {
                        "flow_id": flow_id,
                        "status": node.status,
                        "output": context.resolve_dict(node.output),
                    },
                )
                break

            current_state = next_state

        return {
            "flow_id": flow_id,
            "status": exec_state.status.value,
            "context": {
                "states": context.states,
                "flow_vars": context.flow_vars,
                "cost": context.cost_report,
            },
        }

    async def _execute_node(
        self,
        node,
        state_name: str,
        context: FlowContext,
        flow: ParsedFlow,
        retry_mgr: RetryManager,
        parallel_exec: ParallelExecutor,
        flow_id: str,
    ) -> str | None:
        """Execute a single node and return the next state name."""

        if isinstance(node, AgentTaskNode):
            return await self._handle_agent_task(
                node, state_name, context, retry_mgr, flow_id
            )
        elif isinstance(node, LLMDecisionNode):
            return await self._handle_llm_decision(
                node, state_name, context, flow, flow_id
            )
        elif isinstance(node, HumanInteractionNode):
            return await self._handle_human_interaction(
                node, state_name, context, flow_id
            )
        elif isinstance(node, ParallelNode):
            return await self._handle_parallel(
                node, state_name, context, parallel_exec, flow_id
            )
        elif isinstance(node, ConditionalNode):
            return await self._handle_conditional(node, context)
        elif isinstance(node, WaitForEventNode):
            return await self._handle_wait_for_event(node, flow_id)
        elif isinstance(node, TriggerFlowNode):
            return await self._handle_trigger_flow(node, context, flow_id)
        elif isinstance(node, TerminalNode):
            return None
        else:
            raise ValueError(f"Unknown node type: {type(node)}")

    def _resolve_provider_model(
        self, node: LLMDecisionNode, flow: ParsedFlow
    ) -> tuple[str, str]:
        """Resolve provider and model using the priority chain:
        node-level -> runtime override -> flow config -> system defaults.
        """
        from src.llm.config import LLMProvidersConfig

        defaults = (
            self.llm_config.defaults
            if self.llm_config
            else LLMProvidersConfig().defaults
        )

        provider = (
            node.provider
            or self.runtime_provider
            or flow.config.provider
            or defaults.provider
        )
        model = (
            node.model
            or self.runtime_model
            or flow.config.get_effective_model()
            or defaults.model
        )
        return provider, model

    async def _handle_agent_task(
        self,
        node: AgentTaskNode,
        state_name: str,
        context: FlowContext,
        retry_mgr: RetryManager,
        flow_id: str,
    ) -> str:
        """Delegate task to an agent module via A2A."""
        if node.retry_loop:
            retry_mgr.check_and_increment(context, node.retry_loop)

        resolved_input = context.resolve_dict(node.input)

        await self.event_bus.emit(
            "flow_agent_task_started",
            {
                "flow_id": flow_id,
                "state": state_name,
                "agent": node.agent,
                "input": resolved_input,
            },
        )

        # Invoke the agent via A2A JSON-RPC
        output = await self._call_agent_a2a(node.agent, resolved_input, flow_id)

        # Record cost from agent usage data (estimated tokens from A2A response)
        usage = output.pop("_usage", None)
        if usage:
            try:
                await self.cost_tracker.record_llm_call(
                    task_id=flow_id,
                    module=node.agent,
                    agent=node.agent,
                    model=usage.get("model", "unknown"),
                    input_tokens=usage.get("input_tokens_est", 0),
                    output_tokens=usage.get("output_tokens_est", 0),
                    latency_ms=usage.get("latency_ms", 0),
                    provider=usage.get("provider", "google"),
                )
            except Exception as cost_err:
                logger.warning("[Cost] Failed to record agent cost: %s", cost_err)

        # Scan workspace for generated files and include contents
        workspace_files = self._scan_workspace(node.agent)
        if workspace_files:
            output["source_files"] = workspace_files

        # Store output and set it as current for side_effect resolution
        context.flow_vars["_current_output"] = output
        context.set_state_output(state_name, output)

        await self.event_bus.emit(
            "flow_agent_task_completed",
            {
                "flow_id": flow_id,
                "state": state_name,
                "agent": node.agent,
                "output_summary": str(output.get("result", ""))[:3000] if isinstance(output, dict) else str(output)[:3000],
                "workspace_files": [f["path"] for f in workspace_files] if workspace_files else [],
            },
        )

        return node.on_complete

    def _build_a2a_prompt(self, task_input: dict[str, Any]) -> str:
        """Build the prompt text from task input, formatting Q&A pairs if present."""
        prompt_parts = []
        q_text_map: dict[str, str] = {}
        raw_questions = task_input.get("user_feedback_questions")
        if isinstance(raw_questions, list):
            for q in raw_questions:
                if isinstance(q, dict):
                    q_text_map[q.get("id", "")] = q.get("text", "")

        for k, v in task_input.items():
            if not v:
                continue
            if k == "user_feedback_questions":
                continue
            if k == "user_feedback" and isinstance(v, dict):
                lines = ["user_feedback:"]
                for q_id, answer in v.items():
                    q_text = q_text_map.get(q_id, q_id)
                    lines.append(f"  - {q_text} -> {answer}")
                prompt_parts.append("\n".join(lines))
            else:
                prompt_parts.append(f"{k}: {v}")
        return "\n".join(prompt_parts) or str(task_input)

    @staticmethod
    def _parse_a2a_result(data: dict, task_id: str) -> dict[str, Any]:
        """Parse JSON-RPC result dict into a standard output dict."""
        result = data.get("result", {})
        artifacts = result.get("artifacts", [])
        texts = []
        for artifact in artifacts:
            for part in artifact.get("parts", []):
                if part.get("type") == "text":
                    texts.append(part["text"])

        result_text = "\n".join(texts) if texts else str(result)
        output: dict[str, Any] = {
            "result": result_text,
            "task_id": task_id,
            "status": result.get("status", {}).get("state", "unknown"),
        }

        agent_questions = FlowEngine._extract_agent_questions(result_text)
        if agent_questions:
            output["agent_questions"] = agent_questions

        # Extract usage data for cost tracking
        usage = result.get("usage")
        if usage:
            output["_usage"] = usage

        return output

    async def _call_agent_a2a(
        self,
        agent_name: str,
        task_input: dict[str, Any],
        flow_id: str,
    ) -> dict[str, Any]:
        """Call an agent via A2A, always using SSE streaming with sync fallback."""
        import httpx

        # Resolve agent URL from registry
        a2a_url: str | None = None
        if self.agent_registry:
            agent_info = self.agent_registry.get_agent(agent_name)
            if agent_info:
                a2a_url = agent_info.a2a_url
                # Refresh live card if agent wasn't reachable at discovery time
                if not agent_info.is_live:
                    await self.agent_registry.refresh_agent(agent_name)

        if not a2a_url:
            logger.warning("[A2A] Agent '%s' not found in registry", agent_name)
            return {"result": f"Agent '{agent_name}' not found in registry", **task_input}

        logger.info("[A2A] Calling %s at %s (streaming=always)", agent_name, a2a_url)

        task_id = flow_id
        prompt_text = self._build_a2a_prompt(task_input)
        logger.info("[A2A] %s prompt:\n%s", agent_name, prompt_text[:500])

        params: dict[str, Any] = {
            "id": task_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": prompt_text}],
            },
        }
        # Pass runtime model to the agent so it uses the UI-selected model
        if self.runtime_model:
            params["model"] = self.runtime_model

        payload = {
            "jsonrpc": "2.0",
            "id": f"flow-{flow_id}",
            "method": "tasks/sendSubscribe",
            "params": params,
        }

        try:
            return await self._call_agent_a2a_streaming(
                agent_name, a2a_url, payload, task_id, flow_id,
            )
        except Exception as e:
            if "ConnectError" in type(e).__name__:
                logger.error("[A2A] %s not reachable at %s", agent_name, a2a_url)
                return {"result": f"Agent '{agent_name}' is not reachable at {a2a_url}", **task_input}
            logger.error("[A2A] %s streaming call failed, trying sync fallback: %s", agent_name, e)
            # Fall back to sync if streaming fails for any reason
            try:
                payload["method"] = "tasks/send"
                return await self._call_agent_a2a_sync(
                    agent_name, a2a_url, payload, task_id,
                )
            except Exception as sync_e:
                logger.error("[A2A] %s sync fallback also failed: %s", agent_name, sync_e)
                return {"result": f"A2A call to '{agent_name}' failed: {e}", **task_input}

    async def _call_agent_a2a_streaming(
        self,
        agent_name: str,
        a2a_url: str,
        payload: dict,
        task_id: str,
        flow_id: str,
    ) -> dict[str, Any]:
        """Consume SSE stream from agent's /tasks/sendSubscribe endpoint."""
        import httpx

        stream_url = f"{a2a_url}/tasks/sendSubscribe"
        logger.info("[A2A-SSE] Streaming from %s", stream_url)

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            async with client.stream("POST", stream_url, json=payload) as resp:
                resp.raise_for_status()

                event_type = ""
                data_lines: list[str] = []
                _pending_tool_call = ""
                _tool_call_time = 0.0

                async for raw_line in resp.aiter_lines():
                    line = raw_line.rstrip("\r\n") if isinstance(raw_line, str) else raw_line.decode().rstrip("\r\n")

                    if line.startswith("event:"):
                        event_type = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:"):].strip())
                    elif line == "":
                        # End of SSE event block
                        if event_type and data_lines:
                            data_str = "\n".join(data_lines)
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                data = {"raw": data_str}

                            if event_type == "streaming_text":
                                await self.event_bus.emit("flow_agent_streaming_text", {
                                    "flow_id": flow_id,
                                    "agent": agent_name,
                                    "text": data.get("text", ""),
                                    "author": data.get("author", ""),
                                    "is_thought": data.get("is_thought", False),
                                })
                                await asyncio.sleep(0)
                            elif event_type == "thinking":
                                await self.event_bus.emit("flow_agent_thinking", {
                                    "flow_id": flow_id,
                                    "agent": agent_name,
                                    "text": data.get("text", ""),
                                    "author": data.get("author", ""),
                                    "is_thought": data.get("is_thought", False),
                                })
                                await asyncio.sleep(0)
                            elif event_type == "tool_call":
                                _pending_tool_call = data.get("tool_name", "")
                                _tool_call_time = asyncio.get_event_loop().time()
                                await self.event_bus.emit("flow_agent_tool_use", {
                                    "flow_id": flow_id,
                                    "agent": agent_name,
                                    "tool_name": _pending_tool_call,
                                    "tool_args": data.get("tool_args", {}),
                                    "author": data.get("author", ""),
                                })
                                await asyncio.sleep(0)  # flush to frontend
                            elif event_type == "tool_result":
                                tool_name = data.get("tool_name", "") or _pending_tool_call
                                tool_latency = int((asyncio.get_event_loop().time() - _tool_call_time) * 1000) if _tool_call_time else 0
                                _pending_tool_call = ""
                                _tool_call_time = 0.0
                                await self.event_bus.emit("flow_agent_tool_result", {
                                    "flow_id": flow_id,
                                    "agent": agent_name,
                                    "tool_name": tool_name,
                                    "tool_response": data.get("tool_response", ""),
                                    "author": data.get("author", ""),
                                })
                                await asyncio.sleep(0)  # flush to frontend
                                # Record tool invocation cost event
                                try:
                                    await self.cost_tracker.record_tool_invocation(
                                        task_id=flow_id,
                                        module=agent_name,
                                        agent=data.get("author", "") or agent_name,
                                        tool_id=tool_name,
                                        tool_source="mcp",
                                        latency_ms=tool_latency,
                                    )
                                except Exception:
                                    pass
                            elif event_type == "final":
                                output = self._parse_a2a_result(data, task_id)
                                logger.info("[A2A-SSE] %s final: %s", agent_name, str(output)[:500])
                                return output

                        event_type = ""
                        data_lines = []

        logger.warning("[A2A-SSE] %s stream ended without final event", agent_name)
        return {"result": f"Agent '{agent_name}' stream ended unexpectedly", "task_id": task_id, "status": "failed"}

    async def _call_agent_a2a_sync(
        self,
        agent_name: str,
        a2a_url: str,
        payload: dict,
        task_id: str,
    ) -> dict[str, Any]:
        """Non-streaming POST to agent's / endpoint (fallback)."""
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(a2a_url, json=payload)
            logger.info("[A2A] %s response status=%s", agent_name, resp.status_code)
            logger.debug("[A2A] %s raw response: %s", agent_name, resp.text[:2000])
            resp.raise_for_status()
            data = resp.json()

        output = self._parse_a2a_result(data, task_id)
        logger.info("[A2A] %s output: %s", agent_name, str(output)[:500])
        return output

    @staticmethod
    def _extract_agent_questions(text: str) -> list[dict[str, Any]] | None:
        """Extract structured questions from agent response text.

        Looks for a JSON block containing {"agent_questions": [...]}.
        """
        import re

        # Find JSON block with agent_questions key
        pattern = r'\{[^{}]*"agent_questions"\s*:\s*\[.*?\]\s*\}'
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group())
            questions = parsed.get("agent_questions", [])
            if isinstance(questions, list) and len(questions) > 0:
                return questions
        except json.JSONDecodeError:
            logger.warning("[A2A] Failed to parse agent_questions JSON: %s", match.group()[:200])
        return None

    def _scan_workspace(self, agent_name: str) -> list[dict[str, str]]:
        """Scan the agent's workspace and return file paths + contents."""
        from pathlib import Path

        files: list[dict[str, str]] = []
        if not self.agent_registry:
            return files

        agent_info = self.agent_registry.get_agent(agent_name)
        if not agent_info or not agent_info.workspace_dir:
            return files

        workspace = agent_info.workspace_dir
        if not workspace.exists():
            return files

        for file_path in sorted(workspace.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = str(file_path.relative_to(workspace))
            try:
                content = file_path.read_text(encoding="utf-8")
                files.append({"path": rel_path, "content": content})
            except (UnicodeDecodeError, OSError):
                files.append({"path": rel_path, "content": "[binary file]"})

        logger.info("[Workspace] %s: found %d files in %s", agent_name, len(files), workspace)
        return files

    async def _handle_llm_decision(
        self,
        node: LLMDecisionNode,
        state_name: str,
        context: FlowContext,
        flow: ParsedFlow,
        flow_id: str,
    ) -> str:
        """Execute an LLM decision point."""
        resolved_context = [
            context.resolve(c) if isinstance(c, str) else c for c in node.context
        ]

        available_transitions = list(node.transitions.keys())
        prompt = (
            f"Based on the following context, make a decision.\n\n"
            f"Context:\n{resolved_context}\n\n"
            f"Decision prompt:\n{node.decision_prompt}\n\n"
            f"You MUST respond with exactly one of these choices: {available_transitions}\n"
            f'Respond with JSON: {{"decision": "<choice>", "reason": "<brief explanation>"}}\n'
            f'If decision is "ask_user", also include "questions": [{{"id": "q1", "text": "...", "question_type": "free_text"}}]\n'
            f"Respond with only the JSON, nothing else."
        )

        provider, model = self._resolve_provider_model(node, flow)
        from src.llm.provider import call_llm

        # Call the LLM if config with a valid API key is available
        if self.llm_config and self.llm_config.get_api_key(provider):

            response = await call_llm(
                config=self.llm_config,
                provider=provider,
                model=model,
                prompt=prompt,
            )
            raw_text = response.text.strip()
            logger.info("[LLM Decision] raw response: %s", raw_text[:500])

            # Strip markdown code block wrappers (```json ... ```)
            clean_text = raw_text
            if clean_text.startswith("```"):
                lines = clean_text.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                clean_text = "\n".join(lines).strip()

            # Parse JSON response: {"decision": "...", "reason": "..."}
            decision_output: dict[str, str] = {}
            try:
                decision_output = json.loads(clean_text)
                decision = decision_output.get("decision", "").strip()
            except json.JSONDecodeError:
                # Fallback: treat raw text as decision name
                decision = raw_text
                decision_output = {"decision": decision, "reason": ""}
                logger.warning("[LLM Decision] Not JSON, raw text: %s", raw_text)

            await self.cost_tracker.record_llm_call(
                task_id=flow_id,
                module="flow_engine",
                agent="llm_decision",
                model=model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
                provider=provider,
            )
        else:
            # Fallback: pick the first transition as placeholder
            decision = available_transitions[0] if available_transitions else None
            decision_output = {"decision": decision or "", "reason": ""}

        if not decision or decision not in node.transitions:
            # Try partial match (LLM may return extra whitespace/text)
            matched = None
            if decision:
                for t in available_transitions:
                    if t in decision:
                        matched = t
                        break
            if matched:
                decision = matched
            else:
                raise ValueError(
                    f"LLM decision '{decision}' not in transitions: {available_transitions}"
                )

        reason = decision_output.get("reason", "").strip()
        questions = decision_output.get("questions", [])

        state_output: dict[str, Any] = {
            "decision": decision,
            "reason": reason,
        }
        if questions:
            state_output["questions"] = questions

        context.set_state_output(state_name, state_output)

        await self.event_bus.emit(
            "flow_llm_decision",
            {
                "flow_id": flow_id,
                "state": state_name,
                "decision": decision,
                "reason": reason,
                "provider": provider,
                "model": model,
                "next_state": node.transitions[decision],
            },
        )

        return node.transitions[decision]

    async def _handle_human_interaction(
        self,
        node: HumanInteractionNode,
        state_name: str,
        context: FlowContext,
        flow_id: str,
    ) -> str:
        """Pause the flow and wait for user input."""
        interaction_id = str(uuid.uuid4())
        resolved_prompt = context.resolve(node.prompt) if node.prompt else ""

        # Build event payload
        event_payload: dict[str, Any] = {
            "flow_id": flow_id,
            "state": state_name,
            "interaction_id": interaction_id,
            "interaction_type": node.interaction_type,
            "prompt": str(resolved_prompt),
            "options": node.options,
        }

        # For multi_question: resolve questions (may be a template string or a list)
        if node.interaction_type == "multi_question":
            raw_questions = node.questions
            # If it's a template string, resolve it first to get the list
            if isinstance(raw_questions, str):
                raw_questions = context.resolve(raw_questions)
            # Fallback: pull agent_questions from generate_code output
            if not raw_questions or raw_questions == "":
                gen_output = context.states.get("generate_code", {}).get("output", {})
                if isinstance(gen_output, dict):
                    raw_questions = gen_output.get("agent_questions", [])
            if isinstance(raw_questions, list) and len(raw_questions) > 0:
                resolved_questions = []
                for q in raw_questions:
                    q_dict = q.model_dump() if hasattr(q, "model_dump") else dict(q)
                    q_dict["text"] = str(context.resolve(q_dict.get("text", "")))
                    resolved_questions.append(q_dict)
                event_payload["questions"] = resolved_questions

        await self.event_bus.emit("flow_input_required", event_payload)

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_interactions[interaction_id] = future

        timeout = node.timeout_seconds
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            if node.on_timeout:
                return node.on_timeout
            raise
        finally:
            self._pending_interactions.pop(interaction_id, None)

        state_output: dict[str, Any] = {"response": response}
        # Preserve resolved questions so downstream can map answers to question texts
        if "questions" in event_payload:
            state_output["questions"] = event_payload["questions"]
        context.set_state_output(state_name, state_output)

        await self.event_bus.emit(
            "flow_user_response",
            {
                "flow_id": flow_id,
                "state": state_name,
                "response": str(response)[:1000],
            },
        )

        if node.transitions and isinstance(response, dict) and "id" in response:
            return node.transitions.get(response["id"], node.on_response)
        return node.on_response

    async def submit_interaction_response(
        self, interaction_id: str, response: Any
    ) -> bool:
        """Called by the API when a user submits a response."""
        future = self._pending_interactions.get(interaction_id)
        if future and not future.done():
            future.set_result(response)
            return True
        return False

    async def _handle_parallel(
        self,
        node: ParallelNode,
        state_name: str,
        context: FlowContext,
        parallel_exec: ParallelExecutor,
        flow_id: str,
    ) -> str:
        """Execute parallel branches and collect results."""

        async def branch_executor(name: str, defn: dict) -> dict:
            await self.event_bus.emit(
                "flow_parallel_branch_started",
                {"flow_id": flow_id, "branch": name},
            )
            # TODO: Invoke the actual agent for each branch
            return {"result": f"Branch {name} output"}

        results = await parallel_exec.execute_branches(
            branches={k: v.model_dump() for k, v in node.branches.items()},
            executor_fn=branch_executor,
            join_strategy=node.join,
        )

        context.set_state_output(state_name, {"branches": results})
        return node.on_complete

    async def _handle_conditional(
        self,
        node: ConditionalNode,
        context: FlowContext,
    ) -> str:
        """Evaluate a condition and branch."""
        condition_value = context.resolve(node.condition)
        if condition_value:
            return node.if_true
        return node.if_false

    async def _handle_wait_for_event(
        self,
        node: WaitForEventNode,
        flow_id: str,
    ) -> str:
        """Wait for an external event."""
        await self.event_bus.emit(
            "flow_waiting_event",
            {"flow_id": flow_id, "event_type": node.event_type},
        )
        # TODO: Implement actual event waiting via the event bus
        # For now, simulate immediate event arrival
        return node.on_event

    async def _handle_trigger_flow(
        self,
        node: TriggerFlowNode,
        context: FlowContext,
        flow_id: str,
    ) -> str:
        """Trigger a sub-flow (composition)."""
        # TODO: Load and execute the sub-flow
        await self.event_bus.emit(
            "flow_trigger_subflow",
            {"flow_id": flow_id, "sub_flow": node.flow_name},
        )
        return node.on_complete
