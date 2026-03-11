"""Flow Engine - event-driven reactive state machine executor."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
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
    from src.agents.factory import AgentFactory
    from src.agents.session_manager import SessionManager


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
        agent_factory: AgentFactory | None = None,
        session_manager: SessionManager | None = None,
        interaction_broker: Any | None = None,
        channel: str = "web_ui",
    ):
        self.event_bus = event_bus
        self.cost_tracker = cost_tracker
        self.state_store = state_store or InMemoryStateStore()
        self.llm_config = llm_config
        self.runtime_provider = runtime_provider
        self.runtime_model = runtime_model
        self.agent_factory = agent_factory
        self.session_manager = session_manager
        self._interaction_broker = interaction_broker
        self._channel = channel
        self._pending_interactions: dict[str, asyncio.Future] = {}

    async def validate_agent_requirements(self, flow: ParsedFlow) -> list[str]:
        """Pre-flight check: return issues for agent_task nodes with unavailable agents.

        Called before execute_flow() to catch missing agents early.
        """
        issues: list[str] = []
        for state_name, node in flow.nodes.items():
            if not isinstance(node, AgentTaskNode):
                continue
            resolved = await self._resolve_agent_for_task(node)
            if resolved is None:
                skill_info = f"skill='{node.required_skill}'" if node.required_skill else f"agent='{node.agent}'"
                issues.append(f"State '{state_name}': no agent available for {skill_info}")
        return issues

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

        # Pre-flight: verify all agent_task nodes can be satisfied
        preflight_issues = await self.validate_agent_requirements(flow)
        if preflight_issues:
            logger.warning("[Flow] Pre-flight validation issues: %s", preflight_issues)
            await self.event_bus.emit(
                "flow_validation_warning",
                {"flow_id": flow_id, "issues": preflight_issues},
            )

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
                resolved_output = context.resolve_dict(node.output)
                await self.event_bus.emit(
                    "flow_completed",
                    {
                        "flow_id": flow_id,
                        "status": node.status,
                        "output": resolved_output,
                    },
                )

                # Send final result to the flow's channel
                if self._interaction_broker and self._channel:
                    result_text = str(resolved_output.get("result", resolved_output))
                    if result_text:
                        await self._interaction_broker.notify_channel(
                            channel=self._channel,
                            message=result_text,
                            context_id=flow_id,
                            metadata={"task_id": flow_id, "status": "completed", "notification_type": "result"},
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

    def _resolve_agent_model(self, agent_name: str) -> str:
        """Resolve the effective model for an agent: runtime override or definition."""
        if self.runtime_model:
            return self.runtime_model
        if self.agent_factory and self.agent_factory.has_agent(agent_name):
            defn = self.agent_factory.definitions.get(agent_name)
            if defn:
                return defn.model
        return ""

    async def _resolve_agent_for_task(self, node: AgentTaskNode) -> str | None:
        """Resolve which agent to call for a given AgentTaskNode.

        Priority:
          1. Explicit ``agent`` name — check definition exists, fallback if missing
          2. ``required_skill`` + ``required_capabilities`` — capability scan
          3. None if nothing matched
        """
        factory = self.agent_factory

        if node.agent:
            if factory and factory.has_agent(node.agent):
                return node.agent
            # Agent definition missing — use fallback if defined
            if node.fallback_agent and factory and factory.has_agent(node.fallback_agent):
                logger.warning(
                    "[Negotiation] Agent '%s' not found, switching to fallback '%s'",
                    node.agent, node.fallback_agent,
                )
                return node.fallback_agent
            # Return original name to let call fail with a clear error
            return node.agent

        if node.required_skill and factory:
            # Scan definitions for matching capability
            for name, defn in factory.definitions.items():
                if node.required_skill in defn.capabilities:
                    if node.required_capabilities:
                        if all(c in defn.capabilities for c in node.required_capabilities):
                            logger.info("[Negotiation] Skill '%s' resolved to '%s'", node.required_skill, name)
                            return name
                    else:
                        logger.info("[Negotiation] Skill '%s' resolved to '%s'", node.required_skill, name)
                        return name

        return None

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

        resolved_agent = await self._resolve_agent_for_task(node)
        if resolved_agent is None:
            skill_info = f"skill='{node.required_skill}'" if node.required_skill else f"agent='{node.agent}'"
            await self.event_bus.emit(
                "flow_agent_unavailable",
                {"flow_id": flow_id, "state": state_name, "agent": node.agent, "required_skill": node.required_skill},
            )
            raise RuntimeError(f"No agent available for {skill_info} in state '{state_name}'")

        negotiation_mode = "explicit" if node.agent == resolved_agent else (
            "fallback" if node.fallback_agent == resolved_agent else "skill_match"
        )
        if negotiation_mode != "explicit":
            await self.event_bus.emit(
                "flow_agent_negotiated",
                {
                    "flow_id": flow_id,
                    "state": state_name,
                    "requested_agent": node.agent,
                    "resolved_agent": resolved_agent,
                    "required_skill": node.required_skill,
                    "negotiation": negotiation_mode,
                },
            )

        resolved_input = context.resolve_dict(node.input)
        agent_model = self._resolve_agent_model(resolved_agent)

        await self.event_bus.emit(
            "flow_agent_task_started",
            {
                "flow_id": flow_id,
                "state": state_name,
                "agent": resolved_agent,
                "model": agent_model,
                "input": resolved_input,
            },
        )

        # Invoke the agent in-process via ADK Runner
        output = await self._call_agent_in_process(resolved_agent, resolved_input, flow_id, agent_model)

        # Scan workspace for generated files and include contents
        workspace_files = await self._scan_workspace()
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
                "agent": resolved_agent,
                "model": agent_model,
                "output_summary": str(output.get("result", ""))[:3000] if isinstance(output, dict) else str(output)[:3000],
                "workspace_files": [f["path"] for f in workspace_files] if workspace_files else [],
            },
        )

        return node.on_complete

    def _build_prompt(self, task_input: dict[str, Any]) -> str:
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

    async def _call_agent_in_process(
        self,
        agent_name: str,
        task_input: dict[str, Any],
        flow_id: str,
        agent_model: str = "",
    ) -> dict[str, Any]:
        """Call an agent in-process using ADK Runner (replaces A2A HTTP calls)."""
        import time
        from google.adk.runners import Runner
        from google.adk.agents.run_config import RunConfig, StreamingMode
        from google.genai import types

        if not self.agent_factory:
            raise RuntimeError("AgentFactory not configured on FlowEngine")

        agent = self.agent_factory.create_agent(
            agent_name,
            model_override=agent_model or self.runtime_model or None,
            task_id=flow_id,
            pending_interactions=self._pending_interactions,
            event_bus=self.event_bus,
            context_type="flow",
            interaction_broker=getattr(self, "_interaction_broker", None),
            channel=getattr(self, "_channel", "web_ui"),
        )

        # Get or create session for this flow + agent combination
        _user_id = "user"
        _app_name = f"flow_{flow_id}"
        if self.session_manager:
            session_service, session_id = await self.session_manager.get_or_create(
                f"{flow_id}_{agent_name}", app_name=_app_name, user_id=_user_id,
            )
        else:
            from google.adk.sessions import InMemorySessionService
            session_service = InMemorySessionService()
            session = await session_service.create_session(
                app_name=_app_name, user_id=_user_id,
            )
            session_id = session.id

        runner = Runner(
            agent=agent,
            app_name=_app_name,
            session_service=session_service,
        )

        prompt_text = self._build_prompt(task_input)
        logger.info("[InProcess] %s prompt:\n%s", agent_name, prompt_text[:500])

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=prompt_text)],
        )

        default_provider = self.runtime_provider or "google"
        last_event_time = time.monotonic()
        response_parts: list[str] = []
        _pending_tool_call = ""
        _tool_call_time = 0.0

        async for event in runner.run_async(
            user_id=_user_id,
            session_id=session_id,
            new_message=user_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            author = getattr(event, "author", None) or ""
            content = getattr(event, "content", None)
            is_partial = getattr(event, "partial", False)

            # Record cost from usage_metadata on non-partial events
            usage = getattr(event, "usage_metadata", None)
            if usage and not is_partial:
                now = time.monotonic()
                latency = int((now - last_event_time) * 1000)
                last_event_time = now
                input_tokens = usage.prompt_token_count or 0
                output_tokens = usage.candidates_token_count or 0
                model_version = getattr(event, "model_version", None) or agent_model
                try:
                    await self.cost_tracker.record_llm_call(
                        task_id=flow_id,
                        module=agent_name,
                        agent=author or agent_name,
                        model=model_version,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency,
                        provider=default_provider,
                    )
                except Exception as cost_err:
                    logger.warning("[Cost] Failed to record agent cost: %s", cost_err)

            if not content or not getattr(content, "parts", None):
                continue

            # Partial text — stream token chunks
            if is_partial:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        if hasattr(part, "function_call") and part.function_call:
                            continue
                        is_thought = getattr(part, "thought", False)
                        await self.event_bus.emit("flow_agent_streaming_text", {
                            "flow_id": flow_id,
                            "agent": agent_name,
                            "model": agent_model,
                            "text": part.text,
                            "author": author,
                            "is_thought": bool(is_thought),
                        })
                        await asyncio.sleep(0)
                continue

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    is_thought = getattr(part, "thought", False)
                    if is_thought or not event.is_final_response():
                        await self.event_bus.emit("flow_agent_thinking", {
                            "flow_id": flow_id,
                            "agent": agent_name,
                            "model": agent_model,
                            "text": part.text,
                            "author": author,
                            "is_thought": bool(is_thought),
                        })
                    else:
                        response_parts.append(part.text)
                    await asyncio.sleep(0)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    _pending_tool_call = fc.name
                    _tool_call_time = asyncio.get_event_loop().time()
                    tool_evt: dict = {
                        "flow_id": flow_id,
                        "agent": agent_name,
                        "model": agent_model,
                        "tool_name": fc.name,
                        "tool_args": dict(fc.args) if fc.args else {},
                        "author": author,
                    }
                    # Enrich transfer_to_ calls with full session context
                    if fc.name and fc.name.startswith("transfer_to_"):
                        try:
                            sess = await session_service.get_session(
                                app_name=_app_name,
                                user_id=_user_id,
                                session_id=session_id,
                            )
                            transfer_ctx: dict = {}
                            if sess:
                                if sess.state:
                                    transfer_ctx["state"] = {
                                        k: (v[:3000] if isinstance(v, str) and len(v) > 3000 else v)
                                        for k, v in sess.state.items()
                                    }
                                if hasattr(sess, "events") and sess.events:
                                    history = []
                                    for ev in sess.events:
                                        ev_content = getattr(ev, "content", None)
                                        ev_author = getattr(ev, "author", None) or ""
                                        if not ev_content or not getattr(ev_content, "parts", None):
                                            continue
                                        for p in ev_content.parts:
                                            if hasattr(p, "text") and p.text:
                                                text = p.text[:2000] if len(p.text) > 2000 else p.text
                                                history.append({"author": ev_author, "text": text})
                                            elif hasattr(p, "function_call") and p.function_call:
                                                history.append({
                                                    "author": ev_author,
                                                    "tool_call": p.function_call.name,
                                                    "args": dict(p.function_call.args) if p.function_call.args else {},
                                                })
                                            elif hasattr(p, "function_response") and p.function_response:
                                                fr_resp = p.function_response.response
                                                if hasattr(fr_resp, "model_dump"):
                                                    fr_resp = fr_resp.model_dump()
                                                elif not isinstance(fr_resp, (dict, list, str, int, float, bool, type(None))):
                                                    fr_resp = str(fr_resp)
                                                resp_str = str(fr_resp)
                                                history.append({
                                                    "author": ev_author,
                                                    "tool_result": p.function_response.name,
                                                    "response": resp_str[:1000] if len(resp_str) > 1000 else resp_str,
                                                })
                                    if history:
                                        transfer_ctx["history"] = history
                            if transfer_ctx:
                                tool_evt["transfer_context"] = transfer_ctx
                        except Exception:
                            pass
                    await self.event_bus.emit("flow_agent_tool_use", tool_evt)
                    await asyncio.sleep(0)
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    tool_name = fr.name or _pending_tool_call
                    tool_latency = int((asyncio.get_event_loop().time() - _tool_call_time) * 1000) if _tool_call_time else 0
                    _pending_tool_call = ""
                    _tool_call_time = 0.0
                    resp_data = fr.response
                    if hasattr(resp_data, "model_dump"):
                        resp_data = resp_data.model_dump()
                    elif not isinstance(resp_data, (dict, list, str, int, float, bool, type(None))):
                        resp_data = str(resp_data)
                    await self.event_bus.emit("flow_agent_tool_result", {
                        "flow_id": flow_id,
                        "agent": agent_name,
                        "model": agent_model,
                        "tool_name": tool_name,
                        "tool_response": resp_data,
                        "author": author,
                    })
                    await asyncio.sleep(0)
                    try:
                        await self.cost_tracker.record_tool_invocation(
                            task_id=flow_id,
                            module=agent_name,
                            agent=author or agent_name,
                            tool_id=tool_name,
                            tool_source="mcp",
                            latency_ms=tool_latency,
                        )
                    except Exception:
                        pass

        result_text = "\n".join(response_parts)
        output: dict[str, Any] = {
            "result": result_text,
            "task_id": flow_id,
            "status": "completed",
        }

        agent_questions = FlowEngine._extract_agent_questions(result_text)
        if agent_questions:
            output["agent_questions"] = agent_questions

        logger.info("[InProcess] %s completed: %s", agent_name, result_text[:500])
        return output

    @staticmethod
    def _extract_agent_questions(text: str) -> list[dict[str, Any]] | None:
        """Extract structured questions from agent response text."""
        import re
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
            logger.warning("Failed to parse agent_questions JSON: %s", match.group()[:200])
        return None

    async def _scan_workspace(self) -> list[dict[str, str]]:
        """Scan the shared workspace and return file paths + contents."""
        if not self.agent_factory:
            return []

        workspace = self.agent_factory._workspace_dir
        if not workspace.exists():
            return []

        files = await asyncio.to_thread(self._scan_workspace_sync, workspace)
        logger.info("[Workspace] found %d files in %s", len(files), workspace)
        return files

    @staticmethod
    def _scan_workspace_sync(workspace: Path) -> list[dict[str, str]]:
        """Blocking workspace scan — runs in a thread pool."""
        _EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
        _MAX_FILE_SIZE = 100_000  # 100 KB

        files: list[dict[str, str]] = []
        for file_path in sorted(workspace.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(workspace)
            if any(part in _EXCLUDED_DIRS for part in rel.parts):
                continue
            rel_path = str(rel)
            try:
                size = file_path.stat().st_size
                if size > _MAX_FILE_SIZE:
                    files.append({"path": rel_path, "content": f"[file too large: {size} bytes]"})
                    continue
                content = file_path.read_text(encoding="utf-8")
                files.append({"path": rel_path, "content": content})
            except (UnicodeDecodeError, OSError):
                files.append({"path": rel_path, "content": "[binary file]"})
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
        resolved_prompt = context.resolve(node.prompt) if node.prompt else ""

        # Resolve multi_question questions
        resolved_questions: list[dict[str, Any]] | None = None
        if node.interaction_type == "multi_question":
            raw_questions = node.questions
            if isinstance(raw_questions, str):
                raw_questions = context.resolve(raw_questions)
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

        timeout = node.timeout_seconds

        # --- Broker path: channel-aware dispatch (WhatsApp, Teams, etc.) ---
        if self._interaction_broker:
            logger.info(
                "[Flow] Human interaction via broker, channel=%s, type=%s, questions=%s",
                self._channel, node.interaction_type,
                len(resolved_questions) if resolved_questions else 0,
            )
            try:
                interaction_id = await self._interaction_broker.create_interaction(
                    context_id=flow_id,
                    context_type="flow",
                    interaction_type=node.interaction_type,
                    prompt=str(resolved_prompt),
                    options=node.options,
                    questions=resolved_questions,
                    channel=self._channel,
                    metadata={"state": state_name},
                )
                logger.info(
                    "[Flow] Broker interaction created: id=%s, channel=%s",
                    interaction_id, self._channel,
                )
            except Exception as e:
                logger.error("[Flow] Broker create_interaction FAILED: %s", e, exc_info=True)
                raise

            # For non-web_ui channels: emit a lightweight status event
            # so the web UI shows that the question was sent externally,
            # but NOT the full flow_input_required (which would show the form).
            if self._channel != "web_ui":
                await self.event_bus.emit("flow_input_required", {
                    "flow_id": flow_id,
                    "state": state_name,
                    "interaction_id": interaction_id,
                    "interaction_type": node.interaction_type,
                    "prompt": str(resolved_prompt),
                    "options": node.options,
                    "channel": self._channel,
                    "external": True,
                })
                logger.info("[Flow] Interaction dispatched to %s (external)", self._channel)

            try:
                response_str = await self._interaction_broker.wait_for_response(
                    interaction_id, timeout=timeout,
                )
                logger.info("[Flow] Broker response received: %s", str(response_str)[:200])
                # Parse JSON back for structured responses (multi_question)
                try:
                    response = json.loads(response_str)
                except (json.JSONDecodeError, TypeError):
                    response = response_str
            except asyncio.TimeoutError:
                if node.on_timeout:
                    return node.on_timeout
                raise

        # --- Legacy path: direct event bus emit (web UI only) ---
        else:
            interaction_id = str(uuid.uuid4())
            event_payload: dict[str, Any] = {
                "flow_id": flow_id,
                "state": state_name,
                "interaction_id": interaction_id,
                "interaction_type": node.interaction_type,
                "prompt": str(resolved_prompt),
                "options": node.options,
            }
            if resolved_questions:
                event_payload["questions"] = resolved_questions

            await self.event_bus.emit("flow_input_required", event_payload)

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending_interactions[interaction_id] = future

            try:
                response = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                if node.on_timeout:
                    return node.on_timeout
                raise
            finally:
                self._pending_interactions.pop(interaction_id, None)

        state_output: dict[str, Any] = {"response": response}
        if resolved_questions:
            state_output["questions"] = resolved_questions
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
        # Broker path: delegate to broker (notifies wait_for_response)
        if self._interaction_broker:
            return await self._interaction_broker.submit_response(
                interaction_id=interaction_id,
                response=response,
                responder="flow_api",
            )

        # Legacy path: resolve the asyncio.Future directly
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
