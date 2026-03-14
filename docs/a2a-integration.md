# A2A Gateway — Agent-to-Agent protokoll integráció

> A platform Google A2A (Agent-to-Agent) protokollon keresztül kiajánlja az ágenseket, root ágenseket és flow-kat szabványos, külső rendszerek számára elérhető szolgáltatásként.

---

## Protokoll verzió

**A2A Protocol v0.3** — JSON-RPC 2.0 + Server-Sent Events (SSE) alapú kommunikáció.

**Függőségek:**
- `google-adk>=1.26.0` — `A2aAgentExecutor`, `AgentCardBuilder`, `Runner`
- `a2a-sdk[http-server]>=0.3.24` — `A2AStarletteApplication`, `DefaultRequestHandler`, `InMemoryTaskStore`

---

## Architektúra áttekintés

```
Külső A2A kliens (vagy másik platform)
     │
     │  JSON-RPC 2.0 + SSE
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│                                                                 │
│  /.well-known/agents.json          Agent card URL-ek listája     │
│  /a2a/catalog                     Összes kiajánlott endpoint    │
│                                                                 │
│  /a2a/agents/{name}/              ┐                             │
│  /a2a/root-agents/{name}/         ├─ Per-endpoint Starlette app │
│  /a2a/flows/{name}/               ┘                             │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              A2AGateway service                      │       │
│  │                                                     │       │
│  │  A2AStarletteApplication                            │       │
│  │    └─ DefaultRequestHandler                         │       │
│  │         └─ A2aAgentExecutor                         │       │
│  │              └─ Runner (lazy factory, per-request)   │       │
│  │                   └─ Agent / LoopAgent / FlowWrapper │       │
│  └─────────────────────────────────────────────────────┘       │
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        Google ADK       MCP Tool Servers   LLM Providers
        Runner           (FastMCP)          (Google, Anthropic,
                         stdio│sse│http      OpenAI)
```

### Per-endpoint A2A stack

Minden kiajánlott végpont egy teljes A2A serving stack-et kap:

```
A2AStarletteApplication.build()     ← Starlette sub-app, mountolva a FastAPI-ba
  └─ DefaultRequestHandler          ← JSON-RPC protokoll kezelés
       └─ A2aAgentExecutor          ← Google ADK wrapper A2A-hoz
            └─ runner_factory()     ← Lazy, aszinkron Runner factory (per-request)
                 └─ Runner(agent)   ← ADK Agent/LoopAgent/FlowWrapperAgent
```

---

## Az `expose` flag

Minden definíció típusban (agent, root agent, flow) az `expose: true` YAML flag jelzi, hogy a platform kiajánlja A2A végpontként:

### Agent (`agent.yaml`)

```yaml
agent:
  name: "calendar_agent"
  description: "Calendar management agent"
  # ... egyéb mezők ...
  expose: true                    # ← A2A-n keresztül elérhető lesz
```

### Root Agent (`*.root.yaml`)

```yaml
root_agent:
  name: "personal_assistant"
  description: "Personal assistant orchestrator"
  # ... egyéb mezők ...
  expose: true                    # ← A2A-n keresztül elérhető lesz
```

### Flow (`*.flow.yaml`)

```yaml
flow:
  name: "meeting_prep"
  description: "Meeting preparation workflow"
  # ... egyéb mezők ...
  expose: true                    # ← A2A-n keresztül elérhető lesz
```

**Alapértelmezés:** `expose: false` — explicit bekapcsolás szükséges.

---

## Végpontok

### Platform-szintű

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `GET` | `/.well-known/agents.json` | Kiajánlott agent card URL-ek listája (discovery) |
| `GET` | `/a2a/catalog` | Összes kiajánlott endpoint listája a teljes agent card-okkal |

### Per-endpoint (automatikusan generált)

Minden `expose: true` definícióhoz a rendszer automatikusan létrehozza:

| Útvonal minta | Leírás |
|---------------|--------|
| `/a2a/agents/{name}/` | Ágens A2A endpoint (JSON-RPC) |
| `/a2a/root-agents/{name}/` | Root ágens A2A endpoint (JSON-RPC) |
| `/a2a/flows/{name}/` | Flow A2A endpoint (JSON-RPC) |

Minden per-endpoint Starlette alkalmazás a szabványos A2A útvonalakat szolgálja ki:

| Útvonal (relatív) | Leírás |
|--------------------|--------|
| `/.well-known/agent-card.json` | Az endpoint agent card-ja |
| `/` | JSON-RPC 2.0 endpoint (`tasks/send`, `tasks/sendSubscribe`) |

**Példa URL-ek** (alapértelmezett konfiguráció):

```
http://localhost:8000/a2a/agents/calendar_agent/.well-known/agent-card.json
http://localhost:8000/a2a/root-agents/personal_assistant/.well-known/agent-card.json
http://localhost:8000/a2a/flows/meeting_prep/.well-known/agent-card.json
http://localhost:8000/.well-known/agents.json
http://localhost:8000/a2a/catalog
```

---

## Agent Card generálás

Az agent card-okat a Google ADK `AgentCardBuilder` automatikusan generálja az ágens definícióból:

- **name** — a YAML `name` mezőből
- **description** — a YAML `description` mezőből
- **version** — a YAML `version` mezőből
- **url** — `{a2a_base_url}/a2a/{kind}/{name}/`
- **capabilities** — `streaming: true`
- **skills** — a YAML `capabilities` lista alapján generálva (agent/root agent), vagy a flow `trigger.input_schema` alapján (flow)
- **defaultInputModes / defaultOutputModes** — `["text/plain"]`

### Platform discovery endpoint

A `/.well-known/agents.json` a kiajánlott endpoint-ok agent card URL-jeinek listáját adja vissza:

```json
[
  "http://localhost:8000/a2a/agents/calendar_agent/.well-known/agent-card.json",
  "http://localhost:8000/a2a/agents/research_agent/.well-known/agent-card.json",
  "http://localhost:8000/a2a/root-agents/personal_assistant/.well-known/agent-card.json",
  "http://localhost:8000/a2a/flows/meeting_prep/.well-known/agent-card.json"
]
```

Egy külső rendszer egyetlen GET hívással megtudja, milyen agenteket fedezhet fel, majd egyesével lekérheti a tényleges card-okat.

---

## Flow-k kiajánlása

A flow-k speciális kezelést igényelnek, mivel nem ADK Agent-ek. A `FlowWrapperAgent` wrapper osztály egy ADK `Agent`-et hoz létre egyetlen `run_flow` tool-lal:

```
FlowWrapperAgent.build_agent()
  └─ Agent(name=flow_name, tools=[run_flow])
       └─ run_flow(input: str)    ← Parsolja a flow YAML-t, létrehozza a FlowEngine-t,
                                     végrehajtja, és JSON-ként adja vissza az eredményt
```

Az agent instrukciója tartalmazza a flow leírását és az elvárt input schema-t, így az LLM tudja, hogyan kell használni a `run_flow` tool-t.

---

## Konfiguráció

### Környezeti változó / Settings

```env
# A2A agent card-okban használt publikus alap URL
APP_A2A_BASE_URL=http://localhost:8000
```

**Pydantic Settings mező:** `backend/src/config.py` → `Settings.a2a_base_url`

### YAML flag

Az `expose` flag hozzáadása:

| Definíció típus | Fájl minta | YAML kulcs |
|-----------------|------------|------------|
| Agent | `agents/*/agent.yaml` | `agent.expose: true` |
| Root Agent | `root_agents/*.root.yaml` | `root_agent.expose: true` |
| Flow | `flows/*.flow.yaml` | `flow.expose: true` |

---

## Implementáció részletek

### Inicializálás (startup)

A `main.py` lifespan-ben:

1. Az `A2AGateway` példányosítása az `AgentFactory`, `RootAgentManager`, `SessionManager` stb. referenciákkal
2. `a2a_gw.initialize()` — bejárja az összes definíciót, `expose: true` szűrés, A2A stack építése
3. Minden `ExposedEndpoint` Starlette sub-app-je mount-olásra kerül a FastAPI alkalmazásba

### Lazy Runner factory

Az `A2aAgentExecutor` egy `Callable[..., Runner | Awaitable[Runner]]` factory-t kap. Ez minden kéréshez friss `Runner` + `InMemorySessionService` példányt hoz létre, biztosítva a kérések közötti izoláltságot.

### Kulcs fájlok

| Fájl | Szerep |
|------|--------|
| `backend/src/shared/a2a/gateway.py` | A2AGateway szolgáltatás — endpoint scanning, card building, Starlette app mounting |
| `backend/src/shared/a2a/flow_wrapper.py` | FlowWrapperAgent — flow-t ADK Agent-ként csomagol |
| `backend/src/routers/a2a_gateway.py` | `/a2a/catalog` REST endpoint |
| `backend/src/main.py` | Lifespan: A2AGateway init + mount, `/.well-known/agents.json` platform card |
| `backend/src/config.py` | `a2a_base_url` setting |
| `backend/src/shared/agents/schema.py` | `AgentDefinition.expose`, `RootAgentDefinition.expose` |
| `backend/src/features/flows/engine/dsl/schema.py` | `FlowDefinition.expose` |
| `backend/src/features/flows/engine/dsl/parser.py` | `expose` flag parsing |

---

## Nem implementált funkciók

| Funkció | Megjegyzés |
|---------|------------|
| **RemoteA2aAgent (kliens oldal)** | Külső A2A szolgáltatások fogyasztása sub-agentként — későbbi fázisban tervezett |
| **Push notifications** | Jelenleg nincs implementálva; polling/SSE alapú |
| **OAuth 2 autentikáció** | Nincs auth middleware az A2A endpointokon — produkciós környezetben szükséges |
| **gRPC transport** | Csak HTTP JSON-RPC + SSE van implementálva |
| **Extended agent card** | `supportsAuthenticatedExtendedCard` — nem használt |

---

## Összegzés

A platform az A2A protokoll **kiajánlási (serving) oldalát** valósítja meg: minden `expose: true` definíció szabványos A2A végpontot kap, amelyet bármely A2A-kompatibilis kliens felfedezhet és meghívhat. A belső architektúra a Google ADK `A2aAgentExecutor` + `AgentCardBuilder` és az `a2a-sdk` `A2AStarletteApplication` kombinációjára épül, a platform saját `A2AGateway` szolgáltatásán keresztül összekötve. A fogyasztási oldal (RemoteA2aAgent) egy későbbi fejlesztési fázisban kerül implementálásra.
