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
            "flow_started", {"flow_id": flow_id, "flow_name": flow.name}
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
                "input_summary": str(resolved_input)[:200],
            },
        )

        # Invoke the agent via A2A JSON-RPC
        output = await self._call_agent_a2a(node.agent, resolved_input, flow_id)

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
                "output_summary": str(output.get("result", ""))[:500] if isinstance(output, dict) else str(output)[:500],
                "workspace_files": [f["path"] for f in workspace_files] if workspace_files else [],
            },
        )

        return node.on_complete

    async def _call_agent_a2a(
        self,
        agent_name: str,
        task_input: dict[str, Any],
        flow_id: str,
    ) -> dict[str, Any]:
        """Call an agent via A2A JSON-RPC protocol."""
        import httpx

        # Resolve agent URL from registry
        a2a_url: str | None = None
        if self.agent_registry:
            agent_info = self.agent_registry.get_agent(agent_name)
            if agent_info:
                a2a_url = agent_info.a2a_url

        if not a2a_url:
            logger.warning("[A2A] Agent '%s' not found in registry", agent_name)
            return {"result": f"Agent '{agent_name}' not found in registry", **task_input}

        logger.info("[A2A] Calling %s at %s", agent_name, a2a_url)

        # Build A2A JSON-RPC request
        task_id = str(uuid.uuid4())
        prompt_parts = [f"{k}: {v}" for k, v in task_input.items() if v]
        prompt_text = "\n".join(prompt_parts) or str(task_input)

        payload = {
            "jsonrpc": "2.0",
            "id": f"flow-{flow_id}",
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": prompt_text}],
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(a2a_url, json=payload)
                logger.info("[A2A] %s response status=%s", agent_name, resp.status_code)
                logger.debug("[A2A] %s raw response: %s", agent_name, resp.text[:2000])
                resp.raise_for_status()
                data = resp.json()

            # Parse A2A JSON-RPC response
            result = data.get("result", {})
            artifacts = result.get("artifacts", [])

            # Extract text from artifact parts
            texts = []
            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        texts.append(part["text"])

            output = {
                "result": "\n".join(texts) if texts else str(result),
                "task_id": task_id,
                "status": result.get("status", {}).get("state", "unknown"),
            }
            logger.info("[A2A] %s output: %s", agent_name, str(output)[:500])
            return output
        except httpx.ConnectError:
            logger.error("[A2A] %s not reachable at %s", agent_name, a2a_url)
            return {"result": f"Agent '{agent_name}' is not reachable at {a2a_url}", **task_input}
        except Exception as e:
            logger.error("[A2A] %s call failed: %s", agent_name, e)
            return {"result": f"A2A call to '{agent_name}' failed: {e}", **task_input}

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
            f'Respond with JSON: {{"decision": "<choice>", "reason": "<brief explanation or question for the user>"}}\n'
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

        context.set_state_output(state_name, {
            "decision": decision,
            "reason": reason,
        })

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

        await self.event_bus.emit(
            "flow_input_required",
            {
                "flow_id": flow_id,
                "state": state_name,
                "interaction_id": interaction_id,
                "interaction_type": node.interaction_type,
                "prompt": str(resolved_prompt),
                "options": node.options,
            },
        )

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

        context.set_state_output(state_name, {"response": response})

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
