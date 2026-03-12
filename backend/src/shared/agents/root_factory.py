"""RootAgentManager — creates and manages root-agent (orchestrator) instances from YAML."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools.exit_loop_tool import exit_loop
from google.genai import types as genai_types

from src.shared.agents.factory import AgentFactory
from src.shared.agents.loader import load_root_agent_definitions
from src.shared.agents.schema import RootAgentDefinition
from src.shared.logging import get_logger

logger = get_logger("agents.root_factory")


class RootAgentInstance:
    """Tracks a live root-agent instance."""

    def __init__(self, instance_id: str, definition_name: str):
        self.instance_id = instance_id
        self.definition_name = definition_name
        self.status: str = "idle"           # idle | running | stopped
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.task_ids: list[str] = []

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "definition_name": self.definition_name,
            "status": self.status,
            "started_at": self.started_at,
            "task_ids": self.task_ids,
        }


class RootAgentManager:
    """Manages root-agent definitions and running instances.

    Definitions are loaded from YAML files on disk.
    Instances are logical handles that can create LoopAgent objects for task execution.
    """

    def __init__(
        self,
        agent_factory: AgentFactory,
        root_agents_dir: Path,
    ):
        self._factory = agent_factory
        self._root_agents_dir = root_agents_dir
        self._root_defs: dict[str, RootAgentDefinition] = {}
        self._instances: dict[str, RootAgentInstance] = {}

    # -- lifecycle ----------------------------------------------------------

    def load_definitions(self) -> None:
        self._root_defs = load_root_agent_definitions(self._root_agents_dir)
        logger.info("root_definitions_loaded", count=len(self._root_defs))

    def reload(self) -> None:
        self.load_definitions()

    @property
    def definitions(self) -> dict[str, RootAgentDefinition]:
        return dict(self._root_defs)

    # -- instance management ------------------------------------------------

    def start_instance(self, definition_name: str) -> RootAgentInstance:
        """Create a new logical instance from a definition."""
        if definition_name not in self._root_defs:
            available = ", ".join(sorted(self._root_defs.keys()))
            raise KeyError(
                f"Root-agent definition '{definition_name}' not found. Available: {available}"
            )
        instance_id = str(uuid.uuid4())
        inst = RootAgentInstance(instance_id, definition_name)
        self._instances[instance_id] = inst
        logger.info("instance_started", instance_id=instance_id, definition=definition_name)
        return inst

    def stop_instance(self, instance_id: str) -> None:
        inst = self._instances.pop(instance_id, None)
        if inst:
            inst.status = "stopped"
            logger.info("instance_stopped", instance_id=instance_id)

    def get_instance(self, instance_id: str) -> RootAgentInstance | None:
        return self._instances.get(instance_id)

    def list_instances(self) -> list[dict]:
        return [inst.to_dict() for inst in self._instances.values()]

    # -- agent creation -----------------------------------------------------

    def create_root_agent(
        self,
        definition_name: str,
        *,
        model_override: str | None = None,
        task_id: str | None = None,
        pending_interactions: dict | None = None,
        event_bus: Any | None = None,
        instance_id: str | None = None,
        interaction_broker: Any | None = None,
        channel: str = "web_ui",
    ) -> LoopAgent:
        """Build a LoopAgent from a root-agent definition.

        This creates fresh ADK Agent instances for the orchestrator and all
        sub-agents declared in the definition.
        """
        defn = self._root_defs.get(definition_name)
        if not defn:
            available = ", ".join(sorted(self._root_defs.keys()))
            raise KeyError(
                f"Root-agent definition '{definition_name}' not found. Available: {available}"
            )

        # Track task on instance
        if instance_id and instance_id in self._instances:
            inst = self._instances[instance_id]
            inst.status = "running"
            if task_id:
                inst.task_ids.append(task_id)

        # Create sub-agents (two-pass: create first, then inject peer awareness)
        sub_agents: list[Agent] = []
        for agent_name in defn.sub_agents:
            if not self._factory.has_agent(agent_name):
                logger.warning("sub_agent_not_found", name=agent_name, root=defn.name)
                continue
            agent = self._factory.create_agent(
                agent_name,
                model_override=model_override,
                task_id=task_id,
                pending_interactions=pending_interactions,
                event_bus=event_bus,
                interaction_broker=interaction_broker,
                channel=channel,
            )
            sub_agents.append(agent)

        # Inject peer context: each agent learns about its siblings
        if len(sub_agents) > 1:
            for agent in sub_agents:
                peers = [a for a in sub_agents if a.name != agent.name]
                agent.instruction = self._factory._inject_peer_context(
                    agent.instruction, peers,
                )

        if not sub_agents:
            raise ValueError(f"No sub-agents could be created for root-agent '{defn.name}'")

        # Build orchestrator instruction
        instruction = self._build_instruction(defn, sub_agents)
        model = model_override or defn.model

        # Generate content config
        gen_config = None
        if defn.generate_content_config.thinking:
            gen_config = genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(include_thoughts=True),
            )

        orchestrator = Agent(
            model=model,
            name="orchestrator",
            description="Orchestrates task execution by delegating to specialized agents.",
            instruction=instruction,
            sub_agents=sub_agents,
            tools=[exit_loop],
            generate_content_config=gen_config,
        )

        return LoopAgent(
            name=defn.name,
            sub_agents=[orchestrator],
            max_iterations=defn.orchestration.max_iterations,
        )

    def _build_instruction(self, defn: RootAgentDefinition, sub_agents: list[Agent]) -> str:
        """Build the orchestrator instruction, merging definition template with agent info."""
        agents_desc = "\n".join(f"- {a.name}: {a.description}" for a in sub_agents)
        output_keys_desc = "\n".join(f"- {a.name}_output" for a in sub_agents)

        if defn.instruction:
            # Allow the definition to use template placeholders
            return (
                defn.instruction
                .replace("{{ agents_desc }}", agents_desc)
                .replace("{{ output_keys_desc }}", output_keys_desc)
            )

        # Default instruction (same logic as the old RootAgentFactory)
        return (
            "You are the orchestrator agent that coordinates task execution.\n\n"
            f"Available agents you can transfer to:\n{agents_desc}\n\n"
            "After an agent completes, its response is saved to session state under these keys:\n"
            f"{output_keys_desc}\n"
            "Check these in the conversation history to see what agents have responded.\n\n"
            "WORKFLOW:\n"
            "1. Analyze the user's request and the current state.\n"
            "2. If no agent has responded yet, transfer to the appropriate specialized agent.\n"
            "3. If an agent responded with questions or needs clarification, "
            "transfer to user_agent to ask the human user.\n"
            "4. If user_agent returned the user's answer, transfer back to the "
            "specialized agent with the user's answer included in context.\n"
            "5. If the task is fully completed with a satisfactory result, "
            "present the final result and then call exit_loop to finish.\n"
            "6. Repeat until the task is done.\n\n"
            "IMPORTANT:\n"
            "- Each turn you can do ONE action: transfer to an agent OR call exit_loop.\n"
            "- Always review agent outputs before deciding the next step.\n"
            "- If the task is ambiguous from the start, transfer to user_agent first."
        )
