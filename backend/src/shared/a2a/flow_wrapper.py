"""Wraps a Flow definition as an ADK Agent so it can be served via A2A.

The wrapper creates a simple LLM agent whose single tool (``run_flow``)
triggers the flow engine and returns the terminal-state output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google.adk.agents import Agent

from src.shared.logging import get_logger

logger = get_logger("a2a.flow_wrapper")


class FlowWrapperAgent:
    """Builds an ADK Agent that exposes a flow as a callable tool."""

    def __init__(
        self,
        *,
        flow_name: str,
        flow_definition: Any,
        flow_path: Path,
        agent_factory: Any,
        session_manager: Any,
        cost_tracker: Any,
        event_bus: Any,
        llm_config: Any,
    ) -> None:
        self._flow_name = flow_name
        self._flow_def = flow_definition
        self._flow_path = flow_path
        self._agent_factory = agent_factory
        self._session_manager = session_manager
        self._cost_tracker = cost_tracker
        self._event_bus = event_bus
        self._llm_config = llm_config

    def build_agent(self) -> Agent:
        """Return an ADK Agent backed by the flow engine."""

        # Capture references for the closure
        flow_path = self._flow_path
        agent_factory = self._agent_factory
        session_manager = self._session_manager
        cost_tracker = self._cost_tracker
        event_bus = self._event_bus
        llm_config = self._llm_config

        async def run_flow(trigger_input: str) -> str:
            """Execute the flow with the given trigger input.

            Args:
                trigger_input: A JSON string containing the flow trigger
                    variables.  The keys must match the flow's input_schema.

            Returns:
                A JSON string with the terminal-state output of the flow.
            """
            from src.features.flows.engine.dsl.parser import FlowParser
            from src.features.flows.engine.engine import FlowEngine

            parsed = FlowParser().parse_file(flow_path)

            engine = FlowEngine(
                event_bus=event_bus,
                cost_tracker=cost_tracker,
                llm_config=llm_config,
                agent_factory=agent_factory,
                session_manager=session_manager,
            )

            try:
                input_data = json.loads(trigger_input)
            except (json.JSONDecodeError, TypeError):
                input_data = {"request": trigger_input}

            result = await engine.execute_flow(parsed, input_data)
            return json.dumps(result, ensure_ascii=False, default=str)

        # Build an input-schema hint for the instruction
        schema_hint = ""
        if self._flow_def.trigger and self._flow_def.trigger.input_schema:
            schema_hint = (
                f"\n\nExpected trigger input schema:\n"
                f"```json\n{json.dumps(self._flow_def.trigger.input_schema, indent=2)}\n```"
            )

        instruction = (
            f"You are a flow executor for the '{self._flow_name}' flow.\n"
            f"Description: {self._flow_def.description}\n\n"
            f"When you receive a request, extract the relevant trigger input "
            f"from the user's message and call the run_flow tool with a JSON "
            f"string containing the trigger variables.  Return the flow result "
            f"to the user."
            f"{schema_hint}"
        )

        return Agent(
            name=self._flow_name,
            description=self._flow_def.description or f"Executes the {self._flow_name} flow",
            instruction=instruction,
            model="gemini-2.5-flash",
            tools=[run_flow],
        )
