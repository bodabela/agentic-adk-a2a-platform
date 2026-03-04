"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env into os.environ so third-party libs (Google ADK, etc.) can access API keys
load_dotenv()

from src.config import Settings
from src.api import health, tasks, flows, events, llm, agents
from src.events.bus import EventBus
from src.cost.tracker import CostTracker
from src.llm.config import load_llm_config
from src.orchestrator.agent_registry import AgentRegistry
from src.common.logging import setup_logging

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.debug)

    # Startup: initialize shared resources
    app.state.settings = settings
    app.state.llm_config = load_llm_config(settings.llm_config_path)
    app.state.event_bus = EventBus()
    app.state.cost_tracker = CostTracker(app.state.event_bus, llm_config=app.state.llm_config)
    app.state.agent_registry = AgentRegistry(settings.modules_dir)
    await app.state.agent_registry.discover_agents()
    yield
    # Shutdown
    await app.state.event_bus.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(flows.router, prefix="/api/flows", tags=["flows"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
