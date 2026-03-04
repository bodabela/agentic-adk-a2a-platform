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

**Prioritás:** Magas | **Jelenlegi állapot:** Nincs

A rendszer jelenleg egyetlen modult tartalmaz (`coder_agent`). A moduláris A2A architektúra lehetővé teszi további specializált agentek bevezetését:

- Új modul könyvtár létrehozása a `modules/` alatt a meglévő struktúra mintájára
- `module.yaml` konfiguráció saját A2A host/port beállításokkal
- `agent_card.json` az új agent képességeivel és skill-jeivel
- `serve_a2a.py` A2A server az összes standard endpoint-tal
- Agent regisztráció az `AgentRegistry`-ben automatikusan megtörténik a discovery során
- Flow definíciók bővítése az új agent task node-jaival

**Érintett fájlok:**
- `modules/<new_agent>/` — teljes modul struktúra
- `backend/src/flow_engine/` — flow definíciók bővítése
- `backend/src/orchestrator/agent_registry.py` — automatikus discovery (már támogatott)

### 3. Agent-to-Agent capability negotiation

**Prioritás:** Közepes | **Jelenlegi állapot:** Nem implementált

Jelenleg az agentek nem kérdezik le egymás képességeit futásidőben. A capability negotiation lehetővé tenné:

- **Dinamikus skill discovery** — agentek futásidőben lekérdezik egymás agent card-ját és az elérhető skill-eket
- **Capability matching** — a Flow Engine a task követelmények alapján választja ki a legalkalmasabb agentet
- **Graceful degradation** — ha egy agent nem támogat egy képességet, alternatív agent vagy fallback stratégia aktiválódik
- **Version negotiation** — protokoll verzió egyeztetés az agentek között

**Érintett fájlok:**
- `backend/src/orchestrator/agent_registry.py` — capability cache és matching logika
- `backend/src/flow_engine/engine.py` — dinamikus agent kiválasztás task követelmények alapján
- `modules/*/agent/agent_card.json` — részletesebb capability és skill definíciók

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

---

## Kommunikációs flow

```
Frontend (React)
     │ SSE
     ▼
Flow Engine (FastAPI)
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

1. `FlowEngine._handle_agent_task()` — task input feloldása, A2A prompt építése
2. `_call_agent_a2a()` — agent kikeresése a registry-ből, JSON-RPC payload összeállítása
3. `POST /tasks/sendSubscribe` — streaming hívás az agent felé
4. SSE stream feldolgozás — eventek továbbítása a frontend felé az Event Bus-on keresztül
5. `parse_a2a_result()` — artifacts + usage kinyerése a végső válaszból
6. Fallback: ha a streaming sikertelen, `POST /` szinkron hívás `tasks/send` metódussal

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
| **Push notifications** | Az agent card-ban deklarálva (`true`), de nincs mögötte működő implementáció. Jelenleg polling/SSE alapú. |
| **State transition history** | Deklarálva az agent card-ban, de nem működik — nincs audit trail az állapotátmenetekről. |
| **OAuth 2 autentikáció** | Nincs auth middleware az A2A endpointokon. Produkciós környezetben szükséges lenne. |
| **Extended agent card** | `supportsAuthenticatedExtendedCard: false` — nem használt. |
| **Capability negotiation** | Nincs dinamikus képesség-egyeztetés az agentek között. |
| **Per-event cost metadata** | Költségadatok csak a `final` event-ben érkeznek, nem streaming közben. |

---

## Részlegesen implementált funkciók

| Funkció | Jelenlegi állapot | Hiányzik |
|---------|-------------------|----------|
| **Artifact típusok** | Csak `text/plain` | Multimedia, kód-blokk, markdown típusú artifact-ok |
| **Thinking metadata** | Sima text streaming | Strukturált metadata: phase, confidence, reasoning_steps |
| **Agent questions** | Regex-alapú kinyerés a válaszból | First-class A2A támogatás strukturált kérdésekhez |

---

## Konfiguráció

### module.yaml (agent konfiguráció)

```yaml
a2a:
  host: "127.0.0.1"
  port: 8001

agent:
  model: "gemini-3.1-pro-preview"
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
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "generate_code",
      "name": "Code Generation",
      "description": "Generate source code from specifications"
    }
  ]
}
```

---

## Kulcs fájlok

| Fájl | Szerep |
|------|--------|
| `modules/coder_agent/agent/serve_a2a.py` | FastAPI A2A server endpointok |
| `modules/coder_agent/agent/agent.py` | ADK Agent definíció |
| `modules/coder_agent/agent/agent_card.json` | Agent metadata és capabilities |
| `modules/coder_agent/module.yaml` | Agent konfiguráció |
| `backend/src/flow_engine/engine.py` | A2A client, task delegálás, event emission |
| `backend/src/orchestrator/agent_registry.py` | Agent discovery, regisztráció, health check |
| `backend/src/orchestrator/a2a_client.py` | A2A process manager (dev) |
| `backend/src/events/bus.py` | Event broadcasting a frontend felé |

---

## Összegzés

A rendszer az A2A spec **~60-65%-át** használja ki. A core protokoll (discovery, JSON-RPC, SSE streaming, session management, cost tracking) teljes mértékben működik. A fő hiányosságok a biztonság (auth), skálázhatóság (gRPC, push notifications) és agent-interoperabilitás (capability negotiation, strukturált artifact-ok) terén vannak.
