# Google A2A Integration

> A rendszer Google Agent-to-Agent (A2A) protokoll kihasználtságának dokumentációja.

---

## Következő fejlesztési prioritások

### 1. Thinking metadata továbbfejlesztése

**Prioritás:** Magas | **Jelenlegi állapot:** Részleges

Jelenleg a thinking output sima szövegként streamelődik a `thinking` SSE event-ben. Az A2A spec strukturált metadata-t definiál, amit meg kellene valósítani:

- **Phase tracking** — az agent gondolkodási fázisainak jelzése (analyzing, planning, generating, reviewing)
- **Confidence score** — bizonyossági szint az egyes válaszrészekhez (0.0–1.0)
- **Reasoning steps** — strukturált lépések listája a döntéshozatali folyamatból
- **Summary** — tömör összefoglaló a gondolkodási folyamatról

**Érintett fájlok:**
- `modules/coder_agent/agent/serve_a2a.py` — thinking event payload bővítése
- `backend/src/flow_engine/engine.py` — strukturált thinking feldolgozás
- Frontend — thinking vizualizáció frissítése

### 2. Új Agent hozzáadása

**Prioritás:** Magas | **Jelenlegi állapot:** Részleges

A rendszer jelenleg két modult tartalmaz (`coder_agent`, `user_agent`). A moduláris A2A architektúra lehetővé teszi további specializált agentek bevezetését:

- Új modul könyvtár létrehozása a `modules/` alatt a meglévő struktúra mintájára
- `module.yaml` konfiguráció saját A2A host/port beállításokkal
- `agent_card.json` az új agent képességeivel, skill-jeivel és `protocolVersion` mezővel
- `serve_a2a.py` A2A server az összes standard endpoint-tal
- Agent regisztráció az `AgentRegistry`-ben automatikusan megtörténik a discovery során
- Flow definíciók bővítése az új agent task node-jaival

**Érintett fájlok:**
- `modules/<new_agent>/` — teljes modul struktúra
- `backend/src/flow_engine/` — flow definíciók bővítése
- `backend/src/orchestrator/agent_registry.py` — automatikus discovery (már támogatott)

### 3. Agent-to-Agent capability negotiation

**Prioritás:** Közepes | **Jelenlegi állapot:** Implementált (Flows), Részleges (Tasks)

Implementált funkciók:

- **Dinamikus skill discovery** — AgentRegistry futásidőben lekérdezi az agent card-okat és cache-eli a skill-eket
- **Capability matching** — Flow Engine a `required_skill` és `required_capabilities` alapján választja ki a legalkalmasabb agentet
- **Graceful degradation** — ha az elsődleges agent nem elérhető, `fallback_agent` aktiválódik; ha semmi nem elérhető, `on_error` state-re ugrik
- **Version negotiation** — protokoll verzió ellenőrzés az agentek között (warning, nem blokkoló)
- **Dinamikus registry refresh** — 30 másodpercenként frissíti az agent státuszokat, loggol ha agent live/offline állapota megváltozik
- **Pre-flight validáció** — flow indítása előtt ellenőrzi az összes `agent_task` node agent-elérhetőségét

Nem implementált (Tasks / ADK sub-agent kontextus):
- Skill-alapú agent routing az ADK LoopAgent architektúrán belül

**Érintett fájlok:**
- `backend/src/orchestrator/agent_registry.py` — capability cache, matching logika, refresh loop
- `backend/src/flow_engine/engine.py` — dinamikus agent kiválasztás, pre-flight validáció
- `modules/*/agent/agent_card.json` — strukturált capability, skill és protocolVersion definíciók

---

## Protokoll verzió

**A2A Protocol v0.3** — JSON-RPC + Server-Sent Events (SSE) alapú kommunikáció.

---

## Implementált funkciók

### Core protokoll

| Funkció | Státusz | Leírás |
|---------|---------|--------|
| JSON-RPC üzenetformátum | Teljes | `tasks/send` (szinkron) + `tasks/sendSubscribe` (streaming) |
| SSE streaming | Teljes | 5 event típus: `streaming_text`, `thinking`, `tool_call`, `tool_result`, `final` |
| Agent discovery | Teljes | `GET /.well-known/agent.json` endpoint |
| Health check | Teljes | `GET /health` endpoint |
| Session continuity | Teljes | `task_id → session_id` mapping multi-turn beszélgetéshez |
| Szinkron fallback | Teljes | Ha a streaming nem elérhető, `tasks/send`-re esik vissza |

### Google ADK integráció

- **Runner**: `google.adk.runners.Runner` — agent futtatás streaming támogatással
- **Session Service**: `google.adk.sessions.InMemorySessionService` — session perzisztencia
- **Streaming Config**: `RunConfig(streaming_mode=StreamingMode.SSE)`
- **Model override**: Per-request model kiválasztás a `params["model"]` mezőn keresztül

### Agent Registry

- Automatikus agent discovery a `modules/*/module.yaml` fájlokból
- A2A URL kinyerése az `a2a: {host, port}` konfigurációból
- Élő agent card lekérdezés `GET /.well-known/agent.json` hívással
- Health check és agent állapot cache-elés
- **ÚJ:** `skills` lista cache-elése az agent card-ból (id, name, description, inputModes, outputModes, tags, version)
- **ÚJ:** `protocol_version` cache-elése és kompatibilitás ellenőrzés
- **ÚJ:** `find_agent_by_skill(skill_id)` — skill ID alapján keres élő agentet
- **ÚJ:** `find_best_agent(required_skill, required_capabilities)` — capability-alapú optimális agent választás
- **ÚJ:** `is_protocol_compatible(name)` — protokoll verzió egyeztetés
- **ÚJ:** `start_refresh_loop(interval_seconds=30)` — háttér task, agent státusz periodikus frissítése

### Capability Negotiation (Flow Engine)

- **ÚJ:** `_resolve_agent_for_task(node)` — agent feloldási lánc:
  1. Explicit `agent` név → health check → `fallback_agent`
  2. `required_skill` + `required_capabilities` → registry lookup
  3. Ha semmi nem talált → `RuntimeError` (on_error state aktiválódik)
- **ÚJ:** `flow_agent_negotiated` event — ha fallback vagy skill-match alapú routing történt
- **ÚJ:** `flow_agent_unavailable` event — ha egyetlen agent sem elérhető
- **ÚJ:** `validate_agent_requirements(flow)` — pre-flight validáció, `flow_validation_warning` event
- **ÚJ:** Proper error propagation — soft-fail helyett `RuntimeError`, az `on_error` state valóban aktiválódik

### Cost Tracking

- Usage metadata kinyerése az A2A válaszokból (input/output tokenek, latency, model, provider)
- `CostTracker.record_llm_call()` integráció
- Költségszámítás token árak alapján

---

## SSE streaming event típusok

| Event | Leírás | Payload |
|-------|--------|---------|
| `streaming_text` | Token-by-token szöveg output | `{task_id, author, text, is_thought: false}` |
| `thinking` | Agent gondolkodás/reasoning | `{task_id, author, text, is_thought: true}` |
| `tool_call` | Tool meghívás argumentumokkal | `{task_id, author, tool_name, tool_args}` |
| `tool_result` | Tool végrehajtás eredménye | `{task_id, author, tool_name, tool_response}` |
| `final` | Végső eredmény teljes válasszal | `{jsonrpc, id, result: {artifacts, usage}}` |

### Flow Engine event típusok (capability negotiation)

| Event | Leírás | Payload |
|-------|--------|---------|
| `flow_agent_negotiated` | Fallback vagy skill-match alapú routing | `{flow_id, state, requested_agent, resolved_agent, required_skill, negotiation}` |
| `flow_agent_unavailable` | Egyetlen agent sem elérhető | `{flow_id, state, agent, required_skill}` |
| `flow_validation_warning` | Pre-flight: agent elérhetőségi problémák | `{flow_id, issues: [...]}` |

---

## Kommunikációs flow

```
Frontend (React)
     │ SSE
     ▼
Flow Engine (FastAPI)
     │ capability negotiation → AgentRegistry
     │ A2A JSON-RPC + SSE
     ▼
Module Agent (FastAPI A2A Server)
     │ Google ADK Runner
     ▼
Gemini LLM
     │ MCP (stdio)
     ▼
MCP Tool Servers
```

### Részletes task delegálás

1. `FlowEngine._resolve_agent_for_task()` — agent feloldás: explicit → health check → fallback → skill-match
2. `FlowEngine._handle_agent_task()` — task input feloldása, A2A prompt építése
3. `_call_agent_a2a()` — agent kikeresése a registry-ből, version check, JSON-RPC payload összeállítása
4. `POST /tasks/sendSubscribe` — streaming hívás az agent felé
5. SSE stream feldolgozás — eventek továbbítása a frontend felé az Event Bus-on keresztül
6. `parse_a2a_result()` — artifacts + usage kinyerése a végső válaszból
7. Fallback: ha a streaming sikertelen, `POST /` szinkron hívás `tasks/send` metódussal

### Prompt építés

A `_build_a2a_prompt()` metódus a task_input dict-et szöveggé alakítja:

```
Input:  {"requirement": "Build REST API", "stack": "Node.js"}
Output: "requirement: Build REST API\nstack: Node.js"
```

User feedback kérdések és válaszok is beépülnek a promptba.

---

## Nem implementált A2A funkciók

| Funkció | Megjegyzés |
|---------|------------|
| **gRPC transport** | Csak HTTP JSON-RPC + SSE van implementálva. gRPC alacsonyabb latency-t adna. |
| **Push notifications** | Az agent card-ban deklarálva, de nincs mögötte működő implementáció. Jelenleg polling/SSE alapú. |
| **State transition history** | Deklarálva az agent card-ban, de nem működik — nincs audit trail az állapotátmenetekről. |
| **OAuth 2 autentikáció** | Nincs auth middleware az A2A endpointokon. Produkciós környezetben szükséges lenne. |
| **Extended agent card** | `supportsAuthenticatedExtendedCard: false` — nem használt. |
| **Per-event cost metadata** | Költségadatok csak a `final` event-ben érkeznek, nem streaming közben. |

---

## Részlegesen implementált funkciók

| Funkció | Jelenlegi állapot | Hiányzik |
|---------|-------------------|----------|
| **Artifact típusok** | Csak `text/plain` | Multimedia, kód-blokk, markdown típusú artifact-ok |
| **Thinking metadata** | Sima text streaming | Strukturált metadata: phase, confidence, reasoning_steps |
| **Agent questions** | Regex-alapú kinyerés a válaszból | First-class A2A támogatás strukturált kérdésekhez |
| **Version negotiation** | Warning logolás, nem blokkoló | Semver kompatibilitás, blokkoló policy opció |

---

## Konfiguráció

### module.yaml (agent konfiguráció)

```yaml
a2a:
  host: "127.0.0.1"
  port: 8001

agent:
  model: "gemini-2.5-flash"
  model_fallback: "gemini-2.5-flash"
  max_tokens: 8192
  capabilities:
    - "code_generation"
    - "code_modification"
    - "hotfix_creation"
```

### agent_card.json (A2A discovery)

```json
{
  "name": "coder_agent",
  "description": "Code generation and modification",
  "version": "0.1.0",
  "protocolVersion": "0.3",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "generate_code",
      "name": "Code Generation",
      "description": "Generate source code from specifications",
      "inputModes": ["text/plain", "application/json"],
      "outputModes": ["text/plain"],
      "tags": ["code", "generation"],
      "version": "1.0"
    }
  ]
}
```

### Flow DSL (capability negotiation)

```yaml
# Explicit agent (eredeti viselkedés — backward compatible)
generate_code:
  type: agent_task
  agent: coder_agent
  on_error: handle_error
  ...

# Skill-alapú dinamikus kiválasztás (ÚJ)
generate_code:
  type: agent_task
  required_skill: generate_code
  required_capabilities: [streaming]
  fallback_agent: coder_agent
  on_error: handle_error
  ...
```

---

## Kulcs fájlok

| Fájl | Szerep |
|------|--------|
| `modules/coder_agent/agent/serve_a2a.py` | FastAPI A2A server endpointok |
| `modules/coder_agent/agent/agent.py` | ADK Agent definíció |
| `modules/coder_agent/agent/agent_card.json` | Agent metadata, capabilities, skills, protocolVersion |
| `modules/coder_agent/module.yaml` | Agent konfiguráció |
| `modules/user_agent/agent/agent_card.json` | User interaction agent metadata |
| `backend/src/flow_engine/engine.py` | A2A client, capability negotiation, task delegálás, event emission |
| `backend/src/flow_engine/dsl/schema.py` | Flow DSL: AgentTaskNode (required_skill, fallback_agent) |
| `backend/src/orchestrator/agent_registry.py` | Agent discovery, skill cache, matching, refresh loop |
| `backend/src/orchestrator/a2a_client.py` | A2A process manager (dev) |
| `backend/src/events/bus.py` | Event broadcasting a frontend felé |

---

## Összegzés

A rendszer az A2A spec **~70-75%-át** használja ki. A core protokoll (discovery, JSON-RPC, SSE streaming, session management, cost tracking) teljes mértékben működik. A capability negotiation (skill-alapú agent kiválasztás, fallback, version check, registry refresh) a Flow Engine szintjén implementált. A fő fennmaradó hiányosságok a biztonság (auth), skálázhatóság (gRPC, push notifications) és a strukturált artifact típusok terén vannak.
