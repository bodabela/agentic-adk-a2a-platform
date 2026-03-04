"""Utilities for managing A2A agent connections in local development."""

import subprocess
import asyncio
from dataclasses import dataclass


@dataclass
class AgentProcess:
    name: str
    port: int
    process: subprocess.Popen | None = None


class A2AProcessManager:
    """Manages A2A server processes for local development."""

    def __init__(self):
        self._processes: dict[str, AgentProcess] = {}
        self._base_port = 8001

    async def start_agent(self, module_name: str, module_dir: str) -> str:
        """Start an agent module as an A2A server and return its URL."""
        port = self._base_port + len(self._processes)

        process = subprocess.Popen(
            [
                "uvicorn",
                f"modules.{module_name}.agent.serve_a2a:a2a_app",
                "--host", "0.0.0.0",
                "--port", str(port),
            ],
            cwd=str(module_dir),
        )

        url = f"http://localhost:{port}"
        self._processes[module_name] = AgentProcess(
            name=module_name, port=port, process=process,
        )

        await asyncio.sleep(2)
        return url

    async def stop_all(self) -> None:
        for ap in self._processes.values():
            if ap.process:
                ap.process.terminate()
        self._processes.clear()

    def get_url(self, module_name: str) -> str | None:
        ap = self._processes.get(module_name)
        if ap:
            return f"http://localhost:{ap.port}"
        return None
