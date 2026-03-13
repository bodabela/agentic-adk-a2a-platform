"""Virtual environment manager for per-project and per-agent dependency isolation.

Convention-based: if a ``requirements.txt`` exists in the agent directory or the
project directory, a dedicated venv is created (or reused) and dependencies are
installed into it using **uv** (fast Python package installer).

Hierarchy (most specific wins):
  1. ``projects/{project}/agents/{agent}/requirements.txt`` -> per-agent venv
  2. ``projects/{project}/requirements.txt`` -> per-project shared venv

When both exist the agent-level venv inherits the project-level deps first, then
installs agent-specific deps on top.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from src.shared.logging import get_logger

logger = get_logger("agents.venv_manager")


class VenvManager:
    """Manages isolated virtual environments for agent MCP tool servers.

    Parameters
    ----------
    venvs_root:
        Base directory for all managed venvs (e.g. ``backend/.venvs``).
    project_dir:
        Root of the active project (e.g. ``projects/personal_assistant``).
    """

    def __init__(self, venvs_root: Path, project_dir: Path) -> None:
        self._venvs_root = venvs_root
        self._project_dir = project_dir
        # Cache: agent_name -> resolved python executable path
        self._python_cache: dict[str, Path] = {}

    # -- public API ---------------------------------------------------------

    def setup_all(self, agents_dir: Path) -> None:
        """Scan agents_dir and create/update venvs where requirements.txt exists."""
        project_reqs = self._project_dir / "requirements.txt"
        has_project_reqs = project_reqs.is_file()

        if has_project_reqs:
            self._ensure_venv("_project", [project_reqs])
            logger.info("project_venv_ready", project=self._project_dir.name)

        if not agents_dir.is_dir():
            return

        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            agent_reqs = agent_dir / "requirements.txt"
            if agent_reqs.is_file():
                req_files = []
                if has_project_reqs:
                    req_files.append(project_reqs)
                req_files.append(agent_reqs)
                self._ensure_venv(agent_dir.name, req_files)
                logger.info("agent_venv_ready", agent=agent_dir.name)
            elif has_project_reqs:
                # Agent has no own deps but project does -> use project venv
                self._python_cache[agent_dir.name] = self._venv_python("_project")

    def get_python(self, agent_name: str) -> str:
        """Return the Python executable path for an agent.

        Falls back to ``sys.executable`` (the backend interpreter) when no
        dedicated venv exists for the agent.
        """
        if agent_name in self._python_cache:
            python = self._python_cache[agent_name]
            if python.is_file():
                return str(python)
            logger.warning("cached_python_missing", agent=agent_name, path=str(python))

        return sys.executable

    # -- internals ----------------------------------------------------------

    def _venv_dir(self, name: str) -> Path:
        """Return the venv directory for a given name (agent or _project)."""
        return self._venvs_root / self._project_dir.name / name

    def _venv_python(self, name: str) -> Path:
        """Return the python executable inside a venv."""
        venv = self._venv_dir(name)
        # Cross-platform: Windows uses Scripts/python.exe, Unix uses bin/python
        candidates = [
            venv / "Scripts" / "python.exe",
            venv / "bin" / "python",
        ]
        for c in candidates:
            if c.is_file():
                return c
        # Return the Unix-style path as default (will be created by uv)
        return venv / "bin" / "python"

    def _requirements_hash(self, req_files: list[Path]) -> str:
        """Compute a hash of requirement file contents for cache invalidation."""
        h = hashlib.sha256()
        for f in req_files:
            h.update(f.read_bytes())
        return h.hexdigest()[:16]

    def _ensure_venv(self, name: str, req_files: list[Path]) -> None:
        """Create or update a venv if requirements have changed."""
        venv_dir = self._venv_dir(name)
        hash_file = venv_dir / ".requirements_hash"
        current_hash = self._requirements_hash(req_files)

        # Check if venv exists and is up-to-date
        if hash_file.is_file() and hash_file.read_text().strip() == current_hash:
            python = self._venv_python(name)
            if python.is_file():
                self._python_cache[name] = python
                logger.debug("venv_up_to_date", name=name)
                return

        # Create or recreate venv
        venv_dir.mkdir(parents=True, exist_ok=True)

        if not self._has_uv():
            logger.warning(
                "uv_not_found",
                message="uv is not installed — falling back to venv + pip. Install uv for faster builds.",
            )
            self._create_venv_stdlib(name, req_files)
        else:
            self._create_venv_uv(name, req_files)

        # Write hash for cache invalidation
        hash_file.write_text(current_hash)
        self._python_cache[name] = self._venv_python(name)

    def _has_uv(self) -> bool:
        """Check if uv is available on PATH."""
        try:
            subprocess.run(
                ["uv", "--version"],
                capture_output=True, timeout=10,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _create_venv_uv(self, name: str, req_files: list[Path]) -> None:
        """Create venv and install deps using uv (fast path)."""
        venv_dir = self._venv_dir(name)

        # uv venv <path> --python <version>
        logger.info("uv_venv_create", name=name, path=str(venv_dir))
        result = subprocess.run(
            ["uv", "venv", str(venv_dir), "--python", f"{sys.version_info.major}.{sys.version_info.minor}"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("uv_venv_create_failed", name=name, stderr=result.stderr)
            raise RuntimeError(f"uv venv creation failed for '{name}': {result.stderr}")

        # uv pip install -r <requirements> --python <venv-python>
        python = self._venv_python(name)
        for req_file in req_files:
            logger.info("uv_pip_install", name=name, requirements=str(req_file))
            result = subprocess.run(
                ["uv", "pip", "install", "-r", str(req_file), "--python", str(python)],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                logger.error("uv_pip_install_failed", name=name, stderr=result.stderr)
                raise RuntimeError(f"uv pip install failed for '{name}': {result.stderr}")

        # Also install mcp + fastmcp into the venv (required for MCP servers)
        logger.info("uv_pip_install_mcp", name=name)
        result = subprocess.run(
            ["uv", "pip", "install", "mcp>=1.8.0", "--python", str(python)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("uv_pip_install_mcp_warning", name=name, stderr=result.stderr)

    def _create_venv_stdlib(self, name: str, req_files: list[Path]) -> None:
        """Fallback: create venv using stdlib venv + pip."""
        import venv
        venv_dir = self._venv_dir(name)

        logger.info("stdlib_venv_create", name=name, path=str(venv_dir))
        venv.create(str(venv_dir), with_pip=True, clear=True)

        python = self._venv_python(name)
        for req_file in req_files:
            logger.info("pip_install", name=name, requirements=str(req_file))
            result = subprocess.run(
                [str(python), "-m", "pip", "install", "-r", str(req_file), "--quiet"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                logger.error("pip_install_failed", name=name, stderr=result.stderr)
                raise RuntimeError(f"pip install failed for '{name}': {result.stderr}")

        # Also install mcp + fastmcp
        result = subprocess.run(
            [str(python), "-m", "pip", "install", "mcp>=1.8.0", "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("pip_install_mcp_warning", name=name, stderr=result.stderr)
