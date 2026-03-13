# Getting Started

## Prerequisites

- **Docker + Docker Compose** (recommended) — or:
- Python 3.12+ and Node.js + pnpm (for local dev without Docker)
- At least one API key (Google / Anthropic / OpenAI)

## 1. Environment Variables

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

# Langfuse (optional — LLM observability)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

The `APP_PROJECT` variable selects which project directory to load from `projects/`.

## 2a. Run with Docker (recommended)

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

## 2b. Run locally (without Docker)

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

## 3. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| Langfuse | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

## 4. Observability Setup (optional)

The observability stack (Grafana, Tempo, Prometheus, Langfuse) starts automatically with Docker Compose.

**Langfuse** requires one-time setup:
1. Open http://localhost:3001 and create an account (first user = admin)
2. Create an Organization and Project
3. Go to Settings > API Keys > Create new API keys
4. Add the keys to your `.env`:
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
5. Restart the backend: `docker compose restart backend`

**Grafana** is pre-configured with Tempo (traces) and Prometheus (metrics) datasources and a built-in Agent Platform dashboard.

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
| `GET /api/agents/{name}` | Get agent detail |
| `POST /api/agents/` | Create agent |
| `PUT /api/agents/{name}` | Update agent |
| `DELETE /api/agents/{name}` | Delete agent |
| `GET /api/root-agents/` | List root agent definitions |
| `GET /api/llm/providers` | Available LLM providers and models |
| `GET /api/tools/` | List all MCP and builtin tools |
| `GET /api/interactions/pending` | Pending human interactions |
| `POST /api/interactions/respond` | Respond to an interaction |
| `GET /api/sessions/` | List active sessions |
| `GET /health` | Health check |

## Testing

```bash
make test           # Run tests
make test-cov       # Coverage report
make lint           # Code quality check (ruff + tsc)
make lint-fix       # Auto-fix linting issues
```
