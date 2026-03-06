"""Agent Registry - discovers and manages available agent modules."""

import asyncio
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

import httpx
import yaml

logger = logging.getLogger("agent_registry")

SUPPORTED_PROTOCOL_VERSION = "0.3"


@dataclass
class AgentModuleInfo:
    name: str
    version: str
    description: str
    agent_card_path: Path
    module_yaml: dict
    a2a_url: str | None = None
    capabilities: list[str] = field(default_factory=list)
    a2a_capabilities: dict = field(default_factory=dict)
    skills: list[dict] = field(default_factory=list)
    protocol_version: str = SUPPORTED_PROTOCOL_VERSION
    is_live: bool = False
    workspace_dir: Path | None = None


class AgentRegistry:
    def __init__(self, modules_dir: str):
        self.modules_dir = Path(modules_dir)
        self._agents: dict[str, AgentModuleInfo] = {}
        self._refresh_task: asyncio.Task | None = None

    async def discover_agents(self) -> None:
        """Scan modules directory and register all available agents."""
        if not self.modules_dir.exists():
            return

        for module_dir in self.modules_dir.iterdir():
            if not module_dir.is_dir():
                continue

            module_yaml_path = module_dir / "module.yaml"
            agent_card_path = module_dir / "agent" / "agent_card.json"

            if module_yaml_path.exists():
                with open(module_yaml_path) as f:
                    manifest = yaml.safe_load(f)

                module_info = manifest.get("module", {})
                agent_info = manifest.get("agent", {})
                name = module_info.get("name", module_dir.name)

                # Build A2A URL from module.yaml a2a config
                a2a_config = manifest.get("a2a", {})
                a2a_host = a2a_config.get("host", "127.0.0.1")
                a2a_port = a2a_config.get("port")

                a2a_url = None
                if a2a_port:
                    a2a_url = f"http://{a2a_host}:{a2a_port}"
                elif agent_card_path.exists():
                    # Backward compat: fall back to agent_card.json URL
                    card = json.loads(agent_card_path.read_text())
                    a2a_url = card.get("url")

                # Try to fetch live agent card via HTTP
                a2a_capabilities: dict = {}
                skills: list[dict] = []
                protocol_version = SUPPORTED_PROTOCOL_VERSION
                is_live = False
                if a2a_url:
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            resp = await client.get(f"{a2a_url}/.well-known/agent.json")
                            resp.raise_for_status()
                            live_card = resp.json()
                            a2a_capabilities = live_card.get("capabilities", {})
                            skills = live_card.get("skills", [])
                            protocol_version = live_card.get("protocolVersion", SUPPORTED_PROTOCOL_VERSION)
                            is_live = True
                            logger.info(
                                "Agent '%s' discovered live at %s (capabilities: %s, skills: %s)",
                                name, a2a_url, a2a_capabilities, [s.get("id") for s in skills],
                            )
                    except Exception as e:
                        logger.warning(
                            "Agent '%s' not reachable at %s: %s (using local card)",
                            name, a2a_url, e,
                        )
                        if agent_card_path.exists():
                            card = json.loads(agent_card_path.read_text())
                            a2a_capabilities = card.get("capabilities", {})
                            skills = card.get("skills", [])
                            protocol_version = card.get("protocolVersion", SUPPORTED_PROTOCOL_VERSION)

                # Resolve workspace directory
                workspace_cfg = manifest.get("tools", {}).get("mcp", {}).get("workspace")
                if workspace_cfg:
                    workspace_dir = (module_dir / workspace_cfg).resolve()
                else:
                    workspace_dir = self.modules_dir.parent / "workspace"

                self._agents[name] = AgentModuleInfo(
                    name=name,
                    version=module_info.get("version", "0.0.0"),
                    description=module_info.get("description", ""),
                    agent_card_path=agent_card_path,
                    module_yaml=manifest,
                    a2a_url=a2a_url,
                    capabilities=agent_info.get("capabilities", []),
                    a2a_capabilities=a2a_capabilities,
                    skills=skills,
                    protocol_version=protocol_version,
                    is_live=is_live,
                    workspace_dir=workspace_dir,
                )

    async def health_check(self, name: str) -> bool:
        """Check if a registered agent is healthy (reachable)."""
        agent = self._agents.get(name)
        if not agent or not agent.a2a_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{agent.a2a_url}/health")
                resp.raise_for_status()
                agent.is_live = True
                return True
        except Exception:
            agent.is_live = False
            return False

    async def refresh_agent(self, name: str) -> bool:
        """Re-fetch the live agent card for a single agent. Returns True if live."""
        agent = self._agents.get(name)
        if not agent or not agent.a2a_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{agent.a2a_url}/.well-known/agent.json")
                resp.raise_for_status()
                live_card = resp.json()
                agent.a2a_capabilities = live_card.get("capabilities", {})
                agent.skills = live_card.get("skills", [])
                agent.protocol_version = live_card.get("protocolVersion", SUPPORTED_PROTOCOL_VERSION)
                agent.is_live = True
                return True
        except Exception:
            agent.is_live = False
            return False

    def find_agent_by_skill(self, skill_id: str) -> AgentModuleInfo | None:
        """Return the first live agent that has the given skill_id.

        Falls back to offline agents if no live match is found.
        """
        offline_match: AgentModuleInfo | None = None
        for agent in self._agents.values():
            has_skill = any(s.get("id") == skill_id for s in agent.skills)
            if not has_skill:
                continue
            if agent.is_live:
                return agent
            if offline_match is None:
                offline_match = agent
        return offline_match

    def find_best_agent(
        self,
        required_skill: str | None = None,
        required_capabilities: list[str] | None = None,
    ) -> AgentModuleInfo | None:
        """Capability-based agent selection: skill + capabilities match.

        Live agents are preferred over offline ones.
        """
        candidates = list(self._agents.values())

        if required_skill:
            candidates = [
                a for a in candidates
                if any(s.get("id") == required_skill for s in a.skills)
            ]

        if required_capabilities:
            candidates = [
                a for a in candidates
                if all(cap in a.capabilities for cap in required_capabilities)
            ]

        live = [a for a in candidates if a.is_live]
        return live[0] if live else (candidates[0] if candidates else None)

    def is_protocol_compatible(self, name: str) -> bool:
        """Check if an agent's protocol version matches ours."""
        agent = self._agents.get(name)
        if not agent:
            return False
        compatible = agent.protocol_version == SUPPORTED_PROTOCOL_VERSION
        if not compatible:
            logger.warning(
                "[Negotiation] Protocol version mismatch for '%s': agent=%s, ours=%s",
                name, agent.protocol_version, SUPPORTED_PROTOCOL_VERSION,
            )
        return compatible

    def get_agent(self, name: str) -> AgentModuleInfo | None:
        return self._agents.get(name)

    def list_agents(self) -> list[AgentModuleInfo]:
        return list(self._agents.values())

    def set_a2a_url(self, name: str, url: str) -> None:
        if name in self._agents:
            self._agents[name].a2a_url = url

    def start_refresh_loop(self, interval_seconds: int = 30) -> None:
        """Start a background task that periodically refreshes all agent cards."""
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(
            self._registry_refresh_loop(interval_seconds),
            name="agent_registry_refresh",
        )
        logger.info("Agent registry refresh loop started (interval=%ds)", interval_seconds)

    def stop_refresh_loop(self) -> None:
        """Cancel the background refresh task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            logger.info("Agent registry refresh loop stopped")

    async def _registry_refresh_loop(self, interval_seconds: int) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            for agent in list(self._agents.values()):
                try:
                    was_live = agent.is_live
                    now_live = await self.refresh_agent(agent.name)
                    if was_live != now_live:
                        logger.info(
                            "[Registry] Agent '%s' status changed: %s → %s",
                            agent.name,
                            "live" if was_live else "offline",
                            "live" if now_live else "offline",
                        )
                except Exception as e:
                    logger.warning("[Registry] Refresh failed for '%s': %s", agent.name, e)
