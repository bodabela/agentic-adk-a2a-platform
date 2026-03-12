"""FastAPI application entry point."""

import asyncio
import importlib
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env into os.environ so third-party libs (Google ADK, etc.) can access API keys
load_dotenv()

from src.config import Settings
from src.routers import health, tasks, flows, events, llm, agents, root_agents, interactions as interactions_api, tools as tools_api, sessions
from src.shared.events.bus import EventBus
from src.shared.cost.tracker import CostTracker
from src.shared.llm.config import load_llm_config
from src.shared.agents.factory import AgentFactory
from src.shared.agents.root_factory import RootAgentManager
from src.shared.agents.session_manager import SessionManager
from src.shared.interactions.store import InteractionStore
from src.shared.interactions.broker import InteractionBroker
from src.shared.interactions.channels.web_ui import WebUIChannel
from src.shared.logging import setup_logging

settings = Settings()

_log = logging.getLogger("startup")


def _prewarm_mcp_deps() -> None:
    """Import MCP server dependencies so bytecode / FS cache is warm."""
    for mod in ("mcp.server.fastmcp", "pathlib", "argparse"):
        try:
            importlib.import_module(mod)
        except Exception:
            pass
    _log.info("MCP dependencies pre-warmed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.debug)

    # Startup: initialize shared resources
    app.state.settings = settings
    app.state.llm_config = load_llm_config(settings.llm_config_path)
    app.state.event_bus = EventBus()
    app.state.cost_tracker = CostTracker(app.state.event_bus, llm_config=app.state.llm_config)

    _log.info("Active project: %s", settings.project)

    # Declarative agent infrastructure
    from pathlib import Path
    agents_dir = Path(settings.agents_dir).resolve()
    workspace_dir = Path(settings.workspace_dir).resolve()
    root_agents_dir = Path(settings.root_agents_dir).resolve()

    agent_factory = AgentFactory(
        agents_dir=agents_dir,
        workspace_dir=workspace_dir,
        event_bus=app.state.event_bus,
        llm_config=app.state.llm_config,
    )
    agent_factory.load_definitions()
    app.state.agent_factory = agent_factory

    db_url = f"sqlite+aiosqlite:///{settings.adk_sessions_db}"
    session_manager = SessionManager(db_url=db_url)
    app.state.session_manager = session_manager

    # Interaction broker with channel adapters
    interaction_store = InteractionStore(db_path=settings.interactions_db)
    interaction_broker = InteractionBroker(store=interaction_store)

    # Always register WebUI channel
    web_ui_channel = WebUIChannel(event_bus=app.state.event_bus)
    interaction_broker.register_channel(web_ui_channel)

    # Teams channel (if configured)
    if settings.teams_enabled:
        from src.shared.interactions.channels.teams import TeamsChannel
        teams_channel = TeamsChannel(
            app_id=settings.teams_app_id,
            app_password=settings.teams_app_password,
            service_url=settings.teams_service_url,
            default_conversation_id=settings.teams_default_conversation_id,
            broker=interaction_broker,
        )
        interaction_broker.register_channel(teams_channel)
        await teams_channel.setup_routes(app)

    # WhatsApp channel (if configured)
    if settings.whatsapp_enabled:
        from src.shared.interactions.channels.whatsapp import WhatsAppChannel
        whatsapp_channel = WhatsAppChannel(
            account_sid=settings.whatsapp_account_sid,
            auth_token=settings.whatsapp_auth_token,
            from_number=settings.whatsapp_from_number,
            allowed_numbers=settings.whatsapp_allowed_numbers,
            broker=interaction_broker,
        )
        interaction_broker.register_channel(whatsapp_channel)

    app.state.interaction_broker = interaction_broker

    root_agent_manager = RootAgentManager(
        agent_factory=agent_factory,
        root_agents_dir=root_agents_dir,
    )
    root_agent_manager.load_definitions()
    app.state.root_agent_manager = root_agent_manager

    # Pre-warm MCP server dependencies into filesystem / bytecode cache
    await asyncio.to_thread(_prewarm_mcp_deps)

    yield
    # Shutdown
    await session_manager.close()
    interaction_store.close()
    await app.state.event_bus.shutdown()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Agentic platform for orchestrating AI agents built on Google ADK. "
        "Supports declarative agent definitions, YAML-based flow execution, "
        "multi-channel human-in-the-loop interactions (Web UI, Teams, WhatsApp), "
        "real-time SSE event streaming, and LLM cost tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        # ── Client API ─────────────────────────────────────
        {
            "name": "Client: Health",
            "description": "Service health checks and readiness probes.",
        },
        {
            "name": "Client: Tasks",
            "description": "Submit tasks to root agents and track execution status and cost.",
        },
        {
            "name": "Client: Flows",
            "description": "List and start YAML-based workflow executions.",
        },
        {
            "name": "Client: Events",
            "description": "Server-Sent Events (SSE) stream for real-time platform updates.",
        },
        {
            "name": "Client: Interactions",
            "description": "Submit responses to pending human-in-the-loop interactions and list available channels.",
        },
        {
            "name": "Client: Channels",
            "description": "Channel-specific webhooks (WhatsApp via Twilio).",
        },
        # ── Admin API ──────────────────────────────────────
        {
            "name": "Admin: Flows",
            "description": "CRUD operations for flow definitions — view, create, update, delete YAML definitions and monitor active flows.",
        },
        {
            "name": "Admin: LLM",
            "description": "LLM provider and model configuration.",
        },
        {
            "name": "Admin: Agents",
            "description": "CRUD operations for declarative agent definitions with YAML config and prompt templates.",
        },
        {
            "name": "Admin: Root Agents",
            "description": "Root agent definition CRUD and instance lifecycle management.",
        },
        {
            "name": "Admin: Interactions",
            "description": "Audit trail — list all interactions across statuses.",
        },
        {
            "name": "Admin: Tools",
            "description": "Tool discovery — list all MCP and built-in tools with full parameter schemas.",
        },
        {
            "name": "Admin: Sessions",
            "description": "ADK session lifecycle — list, stop, and delete sessions.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tasks.router, prefix="/api/tasks")
app.include_router(flows.router, prefix="/api/flows")
app.include_router(events.router, prefix="/api/events")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(agents.router, prefix="/api/agents")
app.include_router(root_agents.router, prefix="/api/root-agents")
app.include_router(interactions_api.router, prefix="/api/interactions")
app.include_router(interactions_api._whatsapp_router, prefix="/api")
app.include_router(tools_api.router, prefix="/api/tools")
app.include_router(sessions.router, prefix="/api/sessions")
