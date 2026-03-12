# Agentic ADK/A2A Platform

A modular, multi-agent AI platform built on [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit). Agents are declaratively defined via YAML, equipped with MCP (Model Context Protocol) tools, and support multi-channel interaction (Web UI, Teams, WhatsApp).

## Architecture

```
Frontend (React + TypeScript)
  │  SSE + REST
  ▼
Backend (FastAPI)
  ├── Agent Factory ──── Instantiates ADK agents from YAML definitions
  ├── Root Agent ─────── Orchestration (loop strategy, sub-agent coordination)
  ├── Flow Engine ────── YAML-based state machine (branching, retry, human interaction)
  ├── Interaction Broker  Multi-channel user interaction (WebUI / Teams / WhatsApp)
  ├── Cost Tracker ───── Real-time LLM cost tracking
  └── Event Bus ──────── Async pub/sub + SSE stream to frontend
```

**Two execution modes:**
- **Task** — free-form user request, orchestrated by a root agent across sub-agents
- **Flow** — structured YAML workflow with a state machine

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, Uvicorn |
| AI/Agent | Google ADK, MCP protocol |
| LLM Providers | Google Gemini, Anthropic Claude, OpenAI GPT |
| Frontend | React 19, TypeScript, Vite, Zustand |
| Infra | Docker, Docker Compose |

## Project Structure

```
├── projects/                  # Project definitions (multi-project support)
│   └── personal_assistant/    # Example project
│       ├── agents/            #   Agent definitions (YAML + prompt markdown)
│       ├── root_agents/       #   Root orchestrator definitions
│       └── flows/             #   Flow definitions (YAML state machines)
├── config/                    # Shared config
│   └── llm_providers.yaml    #   LLM provider configuration and pricing
├── backend/                   # FastAPI backend
│   └── src/
│       ├── config.py          #   App settings (project selection, paths)
│       ├── routers/           #   REST API endpoints
│       ├── shared/agents/     #   Factory, loader, schema, session manager
│       ├── flow_engine/       #   State machine executor + DSL parser
│       ├── interactions/      #   Broker + channel adapters (Web, Teams, WhatsApp)
│       ├── cost/              #   Cost tracking
│       └── events/            #   Event bus
├── frontend/                  # React frontend
├── docs/                      # Documentation
├── workspace/                 # Shared workspace for MCP tools
├── docker-compose.yaml        # Base Docker Compose
├── docker-compose.override.yaml  # Dev overrides (hot reload, source mounts)
├── docker-compose.prod.yaml   # Production overrides (static frontend)
├── run.cmd                    # One-click production start (Windows)
├── run-dev.cmd                # One-click dev start (Windows, hot reload)
└── Makefile                   # Make targets for dev/test/docker
```

## Getting Started

### Prerequisites

- **Docker + Docker Compose** (recommended) — or:
- Python 3.12+ and Node.js + pnpm (for local dev without Docker)
- At least one API key (Google / Anthropic / OpenAI)

### 1. Environment Variables

```bash
cp .env.example .env
# Edit .env and add your API keys
```

`.env.example` contents:

```env
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key
APP_DEBUG=true
APP_PROJECT=personal_assistant
```

The `APP_PROJECT` variable selects which project directory to load from `projects/`.

### 2a. Run with Docker (recommended)

**Production mode** (static frontend build):

```bash
# Windows:
run.cmd

# Linux / macOS / Make:
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d
```

**Dev mode** (hot reload for backend + frontend):

```bash
# Windows:
run-dev.cmd

# Linux / macOS / Make:
make docker-up
# or:
docker compose up --build -d
```

Dev mode mounts `backend/src/` and `frontend/src/` into the containers, so code changes trigger automatic restarts (uvicorn `--reload`) and HMR (Vite).

### 2b. Run locally (without Docker)

```bash
# Install dependencies
make install
# or:
cd backend && pip install -e ".[dev]"
cd frontend && pnpm install

# Start backend (terminal 1)
make dev-backend    # http://localhost:8000

# Start frontend (terminal 2)
make dev-frontend   # http://localhost:5173
```

### 3. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| SSE Stream | http://localhost:8000/api/events/stream |

## Multi-Project Support

The platform supports multiple independent projects. Each project lives under `projects/<name>/` and contains its own agents, root agents, and flows.

```
projects/
├── personal_assistant/    # Default project
│   ├── agents/
│   │   ├── calendar_agent/
│   │   │   ├── agent.yaml
│   │   │   ├── prompts/system_prompt.md
│   │   │   └── tools/mcp_server.py
│   │   ├── email_agent/
│   │   └── ...
│   ├── root_agents/
│   │   └── personal_assistant.root.yaml
│   └── flows/
│       ├── meeting_prep.flow.yaml
│       └── schedule_meeting.flow.yaml
└── another_project/       # Add more projects here
    ├── agents/
    ├── root_agents/
    └── flows/
```

**Switching projects:**

```bash
# Via .env:
APP_PROJECT=another_project

# Via environment variable:
set APP_PROJECT=another_project   # Windows
export APP_PROJECT=another_project  # Linux/macOS

# Docker Compose picks it up automatically via ${APP_PROJECT:-personal_assistant}
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/tasks` | Start a task |
| `GET /api/tasks/{id}` | Get task status |
| `POST /api/flows/start` | Start a flow |
| `GET /api/flows/active` | List active flows |
| `GET /api/events/stream` | SSE real-time events |
| `GET /api/agents/` | List agent definitions |
| `GET /api/agents/{name}` | Get agent detail (YAML + prompt + definition) |
| `POST /api/agents/` | Create agent |
| `PUT /api/agents/{name}` | Update agent |
| `DELETE /api/agents/{name}` | Delete agent |
| `GET /api/root-agents/` | List root agent definitions |
| `GET /api/llm/providers` | Available LLM providers and models |
| `GET /api/tools/` | List all MCP and builtin tools |
| `GET /api/interactions/pending` | Pending human interactions |
| `POST /api/interactions/respond` | Respond to an interaction |
| `GET /health` | Health check |

## Testing

```bash
make test           # Run tests
make test-cov       # Coverage report
make lint           # Code quality check (ruff + tsc)
make lint-fix       # Auto-fix linting issues
```

## Documentation

Detailed docs (in Hungarian) are in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Full technical architecture |
| [User Guide](docs/user-guide.md) | End-user guide for the web UI |
| [MCP Setup](docs/mcp-setup.md) | MCP tool configuration reference |
| [Channel Setup](docs/channel-setup.md) | Teams & WhatsApp integration |
| [Cost Tracking](docs/cost-tracking.md) | LLM cost tracking internals |
| [A2A Integration](docs/a2a-integration.md) | Google A2A protocol usage |
