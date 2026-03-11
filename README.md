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
├── agents/            # Agent definitions (YAML + prompt markdown)
├── root_agents/       # Root orchestrator definitions
├── flows/             # Flow definitions (YAML)
├── config/            # LLM provider configuration and pricing
├── backend/           # FastAPI backend
│   └── src/
│       ├── agents/        # Factory, loader, session manager
│       ├── api/           # REST endpoints
│       ├── flow_engine/   # State machine executor + DSL parser
│       ├── interactions/  # Broker + channel adapters
│       ├── cost/          # Cost tracking
│       └── events/        # Event bus
├── frontend/          # React frontend
└── docs/              # Documentation
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js + pnpm
- At least one API key (Google / Anthropic / OpenAI)

### 1. Environment Variables

```bash
cp .env.example .env
# Fill in the required API keys
```

### 2. Install Dependencies

```bash
make install
```

### 3. Run (dev)

```bash
# In two separate terminals:
make dev-backend    # Backend: http://localhost:8000
make dev-frontend   # Frontend: http://localhost:5173
```

### Run with Docker

```bash
make docker-up      # Backend :8000, Frontend :3000
make docker-down    # Stop containers
make docker-logs    # Follow logs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/tasks` | Start a task |
| `GET /api/tasks/{id}` | Get task status |
| `POST /api/flows/start` | Start a flow |
| `GET /api/events/stream` | SSE real-time events |
| `GET /api/agents/` | List agent definitions |
| `GET /api/llm/providers` | Available LLM providers |
| `GET /health` | Health check |

## Testing

```bash
make test           # Run tests
make test-cov       # Coverage report
make lint           # Code quality check
```
