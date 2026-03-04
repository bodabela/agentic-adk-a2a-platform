"""Entry point to expose coder_agent as an A2A server."""

from pathlib import Path
from modules.coder_agent.agent.agent import root_agent

# Note: This is used as:
#   uvicorn modules.coder_agent.agent.serve_a2a:app --port 8001
# from the project root directory.

try:
    from google.adk.a2a.executor import A2AExecutor

    executor = A2AExecutor(
        agent=root_agent,
        agent_card=str(Path(__file__).parent / "agent_card.json"),
    )
    app = executor.get_app()
except ImportError:
    # Fallback: create a simple FastAPI app for testing
    from fastapi import FastAPI

    app = FastAPI(title="coder_agent A2A Server")

    @app.get("/.well-known/agent.json")
    async def agent_card():
        import json
        card_path = Path(__file__).parent / "agent_card.json"
        return json.loads(card_path.read_text())

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "coder_agent"}
