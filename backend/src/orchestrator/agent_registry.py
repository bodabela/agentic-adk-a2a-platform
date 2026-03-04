"""Agent Registry - discovers and manages available agent modules."""

import json
from pathlib import Path
from dataclasses import dataclass, field

import yaml


@dataclass
class AgentModuleInfo:
    name: str
    version: str
    description: str
    agent_card_path: Path
    module_yaml: dict
    a2a_url: str | None = None
    capabilities: list[str] = field(default_factory=list)


class AgentRegistry:
    def __init__(self, modules_dir: str):
        self.modules_dir = Path(modules_dir)
        self._agents: dict[str, AgentModuleInfo] = {}

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

                self._agents[name] = AgentModuleInfo(
                    name=name,
                    version=module_info.get("version", "0.0.0"),
                    description=module_info.get("description", ""),
                    agent_card_path=agent_card_path,
                    module_yaml=manifest,
                    capabilities=agent_info.get("capabilities", []),
                )

    def get_agent(self, name: str) -> AgentModuleInfo | None:
        return self._agents.get(name)

    def list_agents(self) -> list[AgentModuleInfo]:
        return list(self._agents.values())

    def set_a2a_url(self, name: str, url: str) -> None:
        if name in self._agents:
            self._agents[name].a2a_url = url
