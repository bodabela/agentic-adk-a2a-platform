"""Filesystem loader / CRUD for agent and root-agent YAML definitions."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from src.shared.agents.schema import AgentDefinition, RootAgentDefinition
from src.shared.logging import get_logger

logger = get_logger("agents.loader")


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

def _parse_agent_yaml(yaml_path: Path) -> AgentDefinition | None:
    """Parse a single agent.yaml file into an AgentDefinition."""
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        agent_block = raw.get("agent")
        if not agent_block:
            logger.warning("agent_yaml_missing_block", path=str(yaml_path))
            return None
        return AgentDefinition(**agent_block)
    except Exception as exc:
        logger.error("agent_yaml_parse_error", path=str(yaml_path), error=str(exc))
        return None


def load_agent_definitions(agents_dir: Path) -> dict[str, AgentDefinition]:
    """Scan agents_dir for */agent.yaml and return parsed definitions keyed by name."""
    result: dict[str, AgentDefinition] = {}
    if not agents_dir.is_dir():
        logger.warning("agents_dir_not_found", path=str(agents_dir))
        return result

    for agent_yaml in sorted(agents_dir.glob("*/agent.yaml")):
        defn = _parse_agent_yaml(agent_yaml)
        if defn:
            result[defn.name] = defn
            logger.info("agent_loaded", name=defn.name, model=defn.model)

    return result


def resolve_instruction(defn: AgentDefinition, agents_dir: Path) -> str:
    """Resolve the instruction field: if it looks like a file path, read it."""
    instr = defn.instruction
    if not instr:
        return f"You are the {defn.name} agent."

    # Heuristic: treat as file path if it ends with .md or contains /
    if instr.endswith(".md") or "/" in instr:
        agent_subdir = agents_dir / defn.name
        instr_path = agent_subdir / instr
        if instr_path.is_file():
            return instr_path.read_text(encoding="utf-8")
        logger.warning("instruction_file_not_found", path=str(instr_path), agent=defn.name)
        return f"You are the {defn.name} agent."

    return instr


def save_agent_definition(
    agents_dir: Path,
    name: str,
    yaml_content: str,
    prompt_content: str | None = None,
) -> AgentDefinition:
    """Write agent.yaml (and optionally system_prompt.md) to disk. Returns parsed definition."""
    agent_subdir = agents_dir / name
    agent_subdir.mkdir(parents=True, exist_ok=True)

    yaml_path = agent_subdir / "agent.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    if prompt_content is not None:
        prompts_dir = agent_subdir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "system_prompt.md").write_text(prompt_content, encoding="utf-8")

    defn = _parse_agent_yaml(yaml_path)
    if not defn:
        raise ValueError(f"Failed to parse saved agent.yaml for '{name}'")
    return defn


def delete_agent_definition(agents_dir: Path, name: str) -> None:
    """Remove an agent definition directory."""
    agent_subdir = agents_dir / name
    if agent_subdir.is_dir():
        shutil.rmtree(agent_subdir)
        logger.info("agent_deleted", name=name)


def get_agent_detail(agents_dir: Path, name: str) -> dict | None:
    """Return raw YAML + prompt content for a single agent."""
    agent_subdir = agents_dir / name
    yaml_path = agent_subdir / "agent.yaml"
    if not yaml_path.is_file():
        return None

    result: dict = {"yaml_content": yaml_path.read_text(encoding="utf-8")}
    prompt_path = agent_subdir / "prompts" / "system_prompt.md"
    if prompt_path.is_file():
        result["prompt_content"] = prompt_path.read_text(encoding="utf-8")
    else:
        result["prompt_content"] = ""
    return result


# ---------------------------------------------------------------------------
# Root-agent definitions
# ---------------------------------------------------------------------------

def _parse_root_agent_yaml(yaml_path: Path) -> RootAgentDefinition | None:
    """Parse a *.root.yaml file."""
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        block = raw.get("root_agent")
        if not block:
            logger.warning("root_agent_yaml_missing_block", path=str(yaml_path))
            return None
        return RootAgentDefinition(**block)
    except Exception as exc:
        logger.error("root_agent_yaml_parse_error", path=str(yaml_path), error=str(exc))
        return None


def load_root_agent_definitions(root_agents_dir: Path) -> dict[str, RootAgentDefinition]:
    """Scan root_agents_dir for *.root.yaml files."""
    result: dict[str, RootAgentDefinition] = {}
    if not root_agents_dir.is_dir():
        logger.warning("root_agents_dir_not_found", path=str(root_agents_dir))
        return result

    for yaml_path in sorted(root_agents_dir.glob("*.root.yaml")):
        defn = _parse_root_agent_yaml(yaml_path)
        if defn:
            result[defn.name] = defn
            logger.info("root_agent_loaded", name=defn.name)

    return result


def save_root_agent_definition(
    root_agents_dir: Path,
    name: str,
    yaml_content: str,
) -> RootAgentDefinition:
    """Write a root-agent YAML file to disk."""
    root_agents_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = root_agents_dir / f"{name}.root.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    defn = _parse_root_agent_yaml(yaml_path)
    if not defn:
        raise ValueError(f"Failed to parse saved root-agent YAML for '{name}'")
    return defn


def delete_root_agent_definition(root_agents_dir: Path, name: str) -> None:
    """Remove a root-agent YAML file."""
    yaml_path = root_agents_dir / f"{name}.root.yaml"
    if yaml_path.is_file():
        yaml_path.unlink()
        logger.info("root_agent_deleted", name=name)


def get_root_agent_detail(root_agents_dir: Path, name: str) -> dict | None:
    """Return raw YAML content for a root-agent definition."""
    yaml_path = root_agents_dir / f"{name}.root.yaml"
    if not yaml_path.is_file():
        return None
    return {"yaml_content": yaml_path.read_text(encoding="utf-8")}
