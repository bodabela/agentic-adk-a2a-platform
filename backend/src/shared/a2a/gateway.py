"""A2A Gateway — exposes agents, root agents and flows as standard A2A endpoints.

Uses the Google ADK built-in A2aAgentExecutor + AgentCardBuilder together with
the a2a-sdk DefaultRequestHandler and A2AStarletteApplication so that every
exposed entity gets a fully standards-compliant A2A server (JSON-RPC + SSE,
agent card at /.well-known/agent-card.json).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
from google.adk.runners import Runner
from starlette.applications import Starlette

from src.shared.agents.factory import AgentFactory
from src.shared.agents.root_factory import RootAgentManager
from src.shared.agents.session_manager import SessionManager
from src.shared.logging import get_logger

logger = get_logger("a2a.gateway")


@dataclass
class ExposedEndpoint:
    """One exposed A2A endpoint."""

    kind: str           # "agent" | "root_agent" | "flow"
    name: str
    card: AgentCard
    starlette_app: Starlette
    definition: Any     # AgentDefinition | RootAgentDefinition | FlowDefinition


class A2AGateway:
    """Registry of all exposed A2A endpoints.

    During ``initialize()`` the gateway scans agent / root-agent / flow
    definitions for ``expose: true`` and builds the full A2A serving stack
    for each one:

        A2AStarletteApplication
            └─ DefaultRequestHandler
                └─ A2aAgentExecutor
                    └─ Runner (lazy factory)
                        └─ ADK Agent / LoopAgent
    """

    def __init__(
        self,
        *,
        agent_factory: AgentFactory,
        root_agent_manager: RootAgentManager,
        session_manager: SessionManager,
        cost_tracker: Any,
        event_bus: Any,
        llm_config: Any,
        base_url: str,
        flows_dir: Path | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._root_manager = root_agent_manager
        self._session_manager = session_manager
        self._cost_tracker = cost_tracker
        self._event_bus = event_bus
        self._llm_config = llm_config
        self._base_url = base_url.rstrip("/")
        self._flows_dir = flows_dir
        self._endpoints: dict[str, ExposedEndpoint] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Scan all definitions and register exposed endpoints."""

        # Agents
        for name, defn in self._agent_factory.definitions.items():
            if defn.expose:
                try:
                    await self._register_agent(name, defn)
                except Exception as exc:
                    logger.error("a2a_register_agent_failed", agent=name, error=str(exc))

        # Root agents
        for name, defn in self._root_manager.definitions.items():
            if defn.expose:
                try:
                    await self._register_root_agent(name, defn)
                except Exception as exc:
                    logger.error("a2a_register_root_agent_failed", root_agent=name, error=str(exc))

        # Flows
        if self._flows_dir and self._flows_dir.exists():
            await self._register_flows()

        logger.info(
            "a2a_gateway_initialized",
            exposed_count=len(self._endpoints),
            endpoints=list(self._endpoints.keys()),
        )

    @property
    def endpoints(self) -> dict[str, ExposedEndpoint]:
        return dict(self._endpoints)

    def get_catalog(self) -> list[dict]:
        """Return a list of all exposed endpoints with their cards."""
        result = []
        for key, ep in self._endpoints.items():
            mount = self._mount_path(ep.kind, ep.name)
            result.append({
                "kind": ep.kind,
                "name": ep.name,
                "card_url": f"{mount}/.well-known/agent-card.json",
                "rpc_url": f"{mount}/",
                "card": ep.card.model_dump(exclude_none=True, by_alias=True),
            })
        return result

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    async def _register_agent(self, name: str, defn: Any) -> None:
        mount_path = self._mount_path("agent", name)
        rpc_url = f"{self._base_url}{mount_path}/"

        # Build agent card from a temporary ADK Agent instance
        temp_agent = self._agent_factory.create_agent(name)
        card = await AgentCardBuilder(
            agent=temp_agent,
            rpc_url=rpc_url,
            agent_version=defn.version,
            capabilities=AgentCapabilities(streaming=True),
        ).build()

        # Lazy runner factory — creates a fresh Runner per A2A request
        factory = self._agent_factory
        session_mgr = self._session_manager

        async def runner_factory() -> Runner:
            adk_agent = factory.create_agent(name, channel="a2a")
            service, _ = await session_mgr.get_or_create(
                f"a2a_{name}", app_name="a2a_gateway",
            )
            return Runner(
                agent=adk_agent,
                app_name="a2a_gateway",
                session_service=service,
            )

        starlette_app = self._build_a2a_app(card, runner_factory)
        self._endpoints[f"agent:{name}"] = ExposedEndpoint(
            kind="agent", name=name, card=card,
            starlette_app=starlette_app, definition=defn,
        )
        logger.info("a2a_agent_registered", agent=name, rpc_url=rpc_url)

    # ------------------------------------------------------------------
    # Root-agent registration
    # ------------------------------------------------------------------

    async def _register_root_agent(self, name: str, defn: Any) -> None:
        mount_path = self._mount_path("root_agent", name)
        rpc_url = f"{self._base_url}{mount_path}/"

        default_model = self._llm_config.defaults.model
        event_bus = self._event_bus

        # Build agent card
        temp_agent = self._root_manager.create_root_agent(
            name, model_override=default_model, event_bus=event_bus,
        )
        card = await AgentCardBuilder(
            agent=temp_agent,
            rpc_url=rpc_url,
            agent_version=defn.version,
            capabilities=AgentCapabilities(streaming=True),
        ).build()

        root_mgr = self._root_manager
        session_mgr = self._session_manager

        async def runner_factory() -> Runner:
            root_agent = root_mgr.create_root_agent(
                name, model_override=default_model, event_bus=event_bus,
                channel="a2a",
            )
            service, _ = await session_mgr.get_or_create(
                f"a2a_root_{name}", app_name="a2a_gateway",
            )
            return Runner(
                agent=root_agent,
                app_name="a2a_gateway",
                session_service=service,
            )

        starlette_app = self._build_a2a_app(card, runner_factory)
        self._endpoints[f"root_agent:{name}"] = ExposedEndpoint(
            kind="root_agent", name=name, card=card,
            starlette_app=starlette_app, definition=defn,
        )
        logger.info("a2a_root_agent_registered", root_agent=name, rpc_url=rpc_url)

    # ------------------------------------------------------------------
    # Flow registration
    # ------------------------------------------------------------------

    async def _register_flows(self) -> None:
        """Scan flows directory and register those with expose: true."""
        from src.features.flows.engine.dsl.parser import FlowParser

        parser = FlowParser()
        for flow_file in self._flows_dir.glob("*.flow.yaml"):
            try:
                parsed = parser.parse_file(flow_file)
                if not parsed.definition.expose:
                    continue
                await self._register_flow(
                    parsed.definition.name, parsed.definition, flow_file, parsed,
                )
            except Exception as exc:
                logger.error(
                    "a2a_register_flow_failed",
                    flow_file=str(flow_file), error=str(exc),
                )

    async def _register_flow(
        self, name: str, defn: Any, flow_path: Path, parsed_flow: Any,
    ) -> None:
        from src.shared.a2a.flow_wrapper import FlowWrapperAgent

        mount_path = self._mount_path("flow", name)
        rpc_url = f"{self._base_url}{mount_path}/"

        wrapper = FlowWrapperAgent(
            flow_name=name,
            flow_definition=defn,
            flow_path=flow_path,
            agent_factory=self._agent_factory,
            session_manager=self._session_manager,
            cost_tracker=self._cost_tracker,
            event_bus=self._event_bus,
            llm_config=self._llm_config,
        )
        adk_agent = wrapper.build_agent()

        card = await AgentCardBuilder(
            agent=adk_agent,
            rpc_url=rpc_url,
            agent_version=defn.version,
            capabilities=AgentCapabilities(streaming=True),
        ).build()

        session_mgr = self._session_manager

        async def runner_factory() -> Runner:
            agent = wrapper.build_agent()
            service, _ = await session_mgr.get_or_create(
                f"a2a_flow_{name}", app_name="a2a_gateway",
            )
            return Runner(
                agent=agent,
                app_name="a2a_gateway",
                session_service=service,
            )

        starlette_app = self._build_a2a_app(card, runner_factory)
        self._endpoints[f"flow:{name}"] = ExposedEndpoint(
            kind="flow", name=name, card=card,
            starlette_app=starlette_app, definition=defn,
        )
        logger.info("a2a_flow_registered", flow=name, rpc_url=rpc_url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mount_path(kind: str, name: str) -> str:
        """Return the URL mount path for an endpoint.

        agent      → /a2a/agents/{name}
        root_agent → /a2a/root-agents/{name}
        flow       → /a2a/flows/{name}
        """
        kind_slug = {
            "agent": "agents",
            "root_agent": "root-agents",
            "flow": "flows",
        }[kind]
        return f"/a2a/{kind_slug}/{name}"

    @staticmethod
    def _build_a2a_app(card: AgentCard, runner_factory) -> Starlette:
        """Assemble the full a2a-sdk serving stack and return a mountable app."""
        executor = A2aAgentExecutor(runner=runner_factory)
        handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        )
        a2a_app = A2AStarletteApplication(
            agent_card=card,
            http_handler=handler,
        )
        return a2a_app.build()
