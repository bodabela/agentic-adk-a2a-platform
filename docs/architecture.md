# Platform architektúra

Ez a dokumentum a platform teljes technikai architektúráját ismerteti: a deklaratív ágens rendszertől a Google ADK integrációig, a flow engine-en és az interakciós rendszeren át a frontend valós idejű megjelenítéséig.

---

## 1. Rendszer áttekintés

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Frontend                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Dashboard │ │ Tasks    │ │ Flows    │ │ Agents   │ │ Costs    │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       └─────────────┴────────────┴─────────────┴────────────┘       │
│                              │ SSE + REST                           │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                       FastAPI Backend                                │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────┐      │
│  │                    API Layer                               │      │
│  │  /api/tasks  /api/flows  /api/agents  /api/root-agents    │      │
│  │  /api/interactions  /api/events/stream  /api/llm          │      │
│  └───────────┬───────────────┬───────────────┬───────────────┘      │
│              │               │               │                      │
│  ┌───────────▼──┐ ┌─────────▼────┐ ┌────────▼─────────┐           │
│  │ RootAgent    │ │ Flow Engine  │ │ Interaction      │           │
│  │ Manager      │ │              │ │ Broker           │           │
│  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘           │
│         │                │                   │                      │
│  ┌──────▼────────────────▼───────┐  ┌────────▼─────────┐          │
│  │      AgentFactory             │  │ Channel Adapters │          │
│  │  (YAML → ADK Agent)          │  │ WebUI│Teams│WA   │          │
│  └──────┬────────────────────────┘  └──────────────────┘          │
│         │                                                          │
│  ┌──────▼──────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ Session     │ │ Event Bus    │ │ Cost Tracker │                │
│  │ Manager     │ │ (SSE pub/sub)│ │              │                │
│  └─────────────┘ └──────────────┘ └──────────────┘                │
└────────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼──────┐ ┌──────▼──────┐ ┌───────▼─────┐
     │ Google ADK    │ │ MCP Tools   │ │ LLM         │
     │ Runner        │ │ (stdio)     │ │ Providers   │
     └───────────────┘ └─────────────┘ └─────────────┘
```

A platform két fő végrehajtási útvonalat kínál:

| Útvonal | Leírás | Használat |
|---------|--------|-----------|
| **Tasks** | Root ágens orkesztrál, ADK LoopAgent + sub-agentek | Ad-hoc, szabad szöveges feladatok |
| **Flows** | YAML állapotgép, lépésenként hív agenteket | Ismétlődő, strukturált munkafolyamatok |

Mindkét útvonal **ugyanazt az AgentFactory-t** használja az ágens létrehozáshoz, és **ugyanazt az InteractionBroker-t** a felhasználói interakciókhoz.

---

## 2. Deklaratív ágens rendszer

### 2.1 Könyvtárstruktúra

```
agents/
  coder_agent/
    agent.yaml              # Ágens definíció
    prompts/
      system_prompt.md      # System prompt (Markdown)
  user_agent/
    agent.yaml
    prompts/
      system_prompt.md
  tools/
    mcp_server.py           # Megosztott MCP eszközszerver

root_agents/
  default_orchestrator.root.yaml   # Root ágens (orkesztrátor) definíció
```

### 2.2 Agent YAML séma

Minden ágens egy `agent.yaml` fájlban van definiálva:

```yaml
agent:
  name: "coder_agent"
  version: "0.1.0"
  description: "Code generation and modification agent"
  category: "development"

  # LLM konfiguráció
  model: "gemini-2.5-flash"
  model_fallback: "gemini-2.5-pro"

  # Utasítás: relatív fájl útvonal (.md) VAGY inline szöveg
  instruction: "prompts/system_prompt.md"

  # Session state kulcs az ágens kimenetéhez
  output_key: "coder_agent_output"

  # Képességek (kereshetőség, UI megjelenítés)
  capabilities:
    - "code_generation"
    - "code_modification"

  # Gondolkodási mód (thinking)
  generate_content_config:
    thinking: true

  # Peer transfer szabályozás
  disallow_transfer_to_peers: false    # Engedélyezett-e a peer-ek közti transfer
  disallow_transfer_to_parent: false   # Visszatérhet-e a szülő agenthez

  # Eszközök
  tools:
    mcp:
      - transport: "stdio"
        server: "../tools/mcp_server.py"    # Relatív az agents/ könyvtárhoz
        workspace: "{{ workspace_dir }}"     # Template változó, futáskor helyettesítve
    builtin:
      - "exit_loop"
      - "ask_user"    # Speciális: a framework biztosítja az implementációt
```

**Pydantic modell:** `backend/src/agents/schema.py` → `AgentDefinition`

### 2.3 Root Agent YAML séma

A root ágens az orkesztrátor, amely sub-agenteket koordinál:

```yaml
root_agent:
  name: "default_orchestrator"
  version: "1.0.0"
  description: "Default task orchestrator"
  model: "gemini-2.5-flash"

  orchestration:
    strategy: "loop"          # LoopAgent stratégia
    max_iterations: 10        # Maximum iterációk száma

  sub_agents:                 # Hivatkozott ágens nevek (agents/ könyvtárból)
    - "coder_agent"
    - "user_agent"

  instruction: |
    You are the orchestrator. Available agents:
    {{ agents_desc }}
    Transfer to the appropriate sub-agent or call exit_loop.

  generate_content_config:
    thinking: true
```

Az `instruction` mezőben használható template változók:
- `{{ agents_desc }}` — sub-agentek neve és leírása felsorolásban
- `{{ output_keys_desc }}` — session state kulcsok az agentek kimenetéhez

**Pydantic modell:** `backend/src/agents/schema.py` → `RootAgentDefinition`

### 2.4 YAML betöltés és CRUD

A `backend/src/agents/loader.py` modul felelős a fájlrendszer kezelésért:

| Funkció | Leírás |
|---------|--------|
| `load_agent_definitions(agents_dir)` | Beolvassa az összes `*/agent.yaml` fájlt |
| `resolve_instruction(defn, agents_dir)` | Ha `.md` fájl, beolvassa; ha inline, megtartja |
| `save_agent_definition(...)` | Menti az `agent.yaml`-t és a prompt fájlt |
| `delete_agent_definition(...)` | Törli az ágens könyvtárát |
| `load_root_agent_definitions(root_agents_dir)` | Beolvassa a `*.root.yaml` fájlokat |
| `save_root_agent_definition(...)` | Menti a root ágens YAML-t |

Minden CRUD művelet után `factory.reload()` és `root_manager.reload()` hívás szükséges.

---

## 3. AgentFactory — az ágens létrehozás központja

**Fájl:** `backend/src/agents/factory.py`

Az `AgentFactory` az egyetlen belépési pont az ADK `Agent` objektumok létrehozásához. Mind a Tasks, mind a Flows útvonal ezen keresztül hoz létre agenteket.

### 3.1 Létrehozási folyamat

```
create_agent(name, model_override, task_id, interaction_broker, channel, ...)
    │
    ├── 1. Definíció keresése (_agent_defs dict-ből)
    ├── 2. Modell feloldása (override > YAML > default)
    ├── 3. Instruction feloldása (fájl beolvasás vagy inline)
    ├── 4. Eszközök építése (_build_tools)
    │       ├── MCP toolok (_build_mcp_tool → StdioConnectionParams)
    │       └── Builtin toolok (_resolve_builtin)
    │             ├── "exit_loop" → ADK exit_loop tool
    │             └── "ask_user" → _create_ask_user_tool_broker() VAGY _create_ask_user_tool()
    ├── 5. GenerateContentConfig (thinking)
    ├── 6. Peer context injektálás (opcionális)
    └── 7. Return Agent(model, name, instruction, tools, ...)
```

### 3.2 MCP eszközök

Az MCP (Model Context Protocol) eszközök stdio transzporton keresztül kapcsolódnak:

```python
# Belső működés
McpToolset(
    connection_params=StdioConnectionParams(
        command="python",
        args=[str(server_path)],
        cwd=str(workspace_path),
    )
)
```

- A `server` útvonal relatív az ágens könyvtárához
- A `{{ workspace_dir }}` template változó a konfigurált workspace könyvtárra cserélődik
- Minden `create_agent()` hívás új MCP process-t indít (stdio lifecycle)

### 3.3 Peer context injektálás

Amikor több sub-ágens dolgozik együtt, mindegyik megkapja a társai leírását:

```python
_inject_peer_context(instruction, peer_agents) →
    instruction + """
    ## Peer Agents
    You can communicate with the following peer agents using transfer tools:
    - coder_agent: Code generation and modification agent
    - user_agent: Handles direct human interaction
    Use transfer_to_<agent_name> to delegate work.
    """
```

A peer transfer vezérlése az `agent.yaml`-ben:
- `disallow_transfer_to_peers: true` → az ágens nem használhat `transfer_to_*` eszközöket
- `disallow_transfer_to_parent: true` → nem térhet vissza az orkesztrátorhoz

### 3.4 GenerateContentConfig

Ha a YAML-ben `thinking: true` van beállítva:

```python
genai_types.GenerateContentConfig(
    thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
)
```

Ez engedélyezi a modell gondolkodási folyamatának megjelenítését (thinking tokens), ami a streamed eseményekben `is_thought: true` flag-gel jelenik meg.

---

## 4. RootAgentManager — orkesztrátor kezelés

**Fájl:** `backend/src/agents/root_factory.py`

### 4.1 Működés

A `RootAgentManager` root ágens definíciókat tölt be YAML-ből és futó instance-okat kezel.

```
RootAgentManager
    │
    ├── _root_defs: dict[str, RootAgentDefinition]  # Betöltött definíciók
    └── _instances: dict[str, RootAgentInstance]     # Futó instance-ok
         ├── instance_id (UUID)
         ├── definition_name
         ├── status: idle | running | stopped
         ├── started_at
         └── task_ids: list[str]
```

### 4.2 LoopAgent létrehozás

A `create_root_agent()` metódus egy teljes ADK `LoopAgent`-et épít:

```
create_root_agent(definition_name, model_override, task_id, interaction_broker, channel)
    │
    ├── 1. Root definíció betöltése
    ├── 2. Sub-agentek létrehozása (AgentFactory.create_agent() mindegyikhez)
    ├── 3. Peer context injektálás (ha >1 sub-agent)
    ├── 4. Orchestrator Agent építése
    │       ├── model: definícióból vagy override
    │       ├── instruction: template-ek feloldva (agents_desc, output_keys_desc)
    │       ├── sub_agents: az összes létrehozott sub-ágens
    │       ├── tools: [exit_loop]
    │       └── generate_content_config: thinking
    └── 5. LoopAgent wrap
            ├── name: definíció neve
            ├── sub_agents: [orchestrator]
            └── max_iterations: definícióból (default 10)
```

**Eredmény hierarchia:**
```
LoopAgent ("default_orchestrator")
  └── Agent ("orchestrator")          # Az orkesztrátor LLM ágens
        ├── sub_agents:
        │     ├── Agent ("coder_agent")   # Kód generáló ágens
        │     │     └── tools: [McpToolset, exit_loop, ask_user]
        │     └── Agent ("user_agent")    # Felhasználói interakciós ágens
        │           └── tools: [ask_user]
        └── tools: [exit_loop]
```

A `LoopAgent` iteratívan futtatja az orkesztrátort, amíg az `exit_loop`-ot nem hív, vagy eléri a `max_iterations` limitet.

---

## 5. Session kezelés

**Fájl:** `backend/src/agents/session_manager.py`

### 5.1 Koncepció

Minden ágens futás egy ADK session-ben történik. A session megőrzi:
- **State:** kulcs-érték párok (ágens kimenetek, változók)
- **Events:** teljes beszélgetési előzmény (üzenetek, tool call-ok, válaszok)

### 5.2 Context ID séma

| Útvonal | Context ID | App Name |
|---------|-----------|----------|
| Tasks | `task_id` | `"agent_platform"` |
| Flows | `"{flow_id}_{agent_name}"` | `"flow_{flow_id}"` |

Ugyanaz a `task_id` → ugyanaz a session. Ez biztosítja a multi-turn beszélgetés folytonosságát és a felfüggesztett ágens állapotmegőrzését.

### 5.3 ADK InMemorySessionService

```python
session_manager.get_or_create(context_id, app_name)
    → (InMemorySessionService, session_id)
```

- Első híváskor létrehoz egy új session service-t és session-t
- Későbbi híváskor visszaadja a meglévőt
- A `remove(context_id)` törli a session-t (task befejezésnél NEM hívódik — multi-turn támogatás)

---

## 6. Task végrehajtás

**Fájl:** `backend/src/api/tasks.py`

### 6.1 Teljes végrehajtási folyamat

```
POST /api/tasks/ (TaskSubmission)
    │
    ├── task_id generálás
    ├── Háttér feladat indítás: _execute_task()
    └── Azonnali válasz: {task_id, status: "submitted"}

_execute_task(task_id, submission, request)
    │
    ├── 1. Root ágens definíció feloldás
    │       (submission.root_agent_definition VAGY első elérhető)
    │
    ├── 2. Root ágens létrehozás
    │       root_manager.create_root_agent(
    │           definition_name,
    │           task_id=task_id,
    │           interaction_broker=broker,
    │           channel=channel,
    │       )
    │
    ├── 3. Session létrehozás / visszatöltés
    │       session_manager.get_or_create(task_id)
    │
    ├── 4. ADK Runner létrehozás
    │       Runner(agent=loop_agent, app_name="agent_platform",
    │              session_service=service)
    │
    ├── 5. Streaming futtatás
    │       async for event in runner.run_async(
    │           user_id="user", session_id=session_id,
    │           new_message=Content(role="user", parts=[Part(text=description)]),
    │           run_config=RunConfig(streaming_mode=StreamingMode.SSE),
    │       ):
    │           ├── Partial text → emit "streaming_text"
    │           ├── Thinking → emit "thinking"
    │           ├── Final text → emit "agent_response"
    │           ├── Function call → emit "tool_call" (+ transfer_context)
    │           ├── Function response → emit "tool_result"
    │           └── Usage metadata → cost_tracker.record_llm_call()
    │
    ├── 6a. Sikeres befejezés → emit "task_completed"
    ├── 6b. AgentSuspended → emit "agent_suspended"
    └── 6c. Hiba → emit "task_failed"
```

### 6.2 Transfer context gazdagítás

Amikor egy ágens `transfer_to_<agent_name>` tool call-t hajt végre, a rendszer hozzácsatolja a teljes session kontextust:

```python
# Session állapot lekérése
sess = await service.get_session(...)
transfer_context = {
    "state": {k: str(v)[:3000] for k, v in sess.state.items()},
    "history": [...]  # Feldolgozott beszélgetési előzmény
}
```

A `history` tömb elemei:
```json
[
    {"agent": "orchestrator", "text": "I'll delegate to coder_agent"},
    {"agent": "coder_agent", "tool_call": "edit_file", "args": {"path": "..."}},
    {"agent": "coder_agent", "tool_result": "edit_file", "result": "File edited"},
    {"agent": "user", "text": "Please use TypeScript instead"}
]
```

Ez a kontextus a frontenden a **TransferContextPopup** modálban jelenik meg.

### 6.3 Költségkövetés

Minden nem-partial ADK event-nél:
```python
if event.usage_metadata:
    cost_tracker.record_llm_call(
        task_id=task_id,
        model=model_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )
```

---

## 7. Flow Engine

**Fájl:** `backend/src/flow_engine/engine.py`

### 7.1 Állapotgép végrehajtás

A flow engine egy reaktív állapotgépet futtat, amelyet YAML definiál:

```
FlowEngine.execute_flow(flow_definition, trigger_data)
    │
    while current_state != terminal:
    │
    ├── _handle_agent_task()       → Ágens hívás in-process
    ├── _handle_llm_decision()     → LLM döntési pont
    ├── _handle_human_interaction() → Emberi beavatkozás várakozás
    ├── _handle_parallel()         → Párhuzamos ágak
    ├── _handle_conditional()      → Feltételes elágazás
    ├── _handle_wait_for_event()   → Külső esemény várakozás
    └── _handle_trigger_flow()     → Al-flow indítás
```

### 7.2 In-process ágens hívás

A `_call_agent_in_process()` metódus ugyanazt az `AgentFactory`-t és ADK `Runner`-t használja, mint a Tasks útvonal:

```python
agent = self.agent_factory.create_agent(
    agent_name,
    model_override=model,
    task_id=flow_id,
    pending_interactions=self._pending_interactions,
    interaction_broker=self._interaction_broker,
    context_type="flow",
    channel=self._channel,
)

runner = Runner(agent=agent, app_name=f"flow_{flow_id}", session_service=service)

async for event in runner.run_async(...):
    # Ugyanaz a streaming logika, mint tasks.py-ban
    # Event-ek: flow_agent_streaming_text, flow_agent_thinking,
    #           flow_agent_tool_use, flow_agent_tool_result
```

### 7.3 Ágens feloldás

A flow engine többlépéses ágens-feloldást alkalmaz:

1. **Explicit:** a YAML `agent:` mezőjében megadott ágens
2. **Fallback:** ha nem elérhető, keresés capability alapján
3. **Negotiation:** ha nincs egyezés, egyeztetés az elérhető ágensek között

### 7.4 Flow vs Task ágens hívás különbségei

| Szempont | Task | Flow |
|----------|------|------|
| Context type | `"task"` | `"flow"` |
| SSE event prefix | `task_event` | `flow_agent_*` |
| Session context_id | `task_id` | `"{flow_id}_{agent_name}"` |
| Orkesztráció | LoopAgent dönt | YAML állapotgép dönt |
| Retry | Nincs (ágens kezeli) | `max_retry_loops` a flow config-ban |

---

## 8. Interakciós rendszer

**Fájlok:** `backend/src/interactions/`

### 8.1 Architektúra

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Ágens       │────▶│ InteractionBroker│────▶│ Channel Adapter │
│ (ask_user)  │     │                  │     │ ┌─────────────┐ │
│             │◀────│  ┌────────────┐  │     │ │ WebUI (SSE) │ │
│             │     │  │ Waiter     │  │     │ │ Teams (Bot) │ │
│             │     │  │ (asyncio)  │  │     │ │ WhatsApp    │ │
│             │     │  └────────────┘  │     │ └─────────────┘ │
│             │     │  ┌────────────┐  │     └─────────────────┘
│             │     │  │ SQLite     │  │              │
│             │     │  │ Store      │  │              │
│             │     │  └────────────┘  │     ┌────────▼────────┐
│             │     └──────────────────┘     │ Webhooks        │
│             │              ▲               │ /teams/webhook  │
│             │              │               │ /whatsapp/webhook│
│             │              └───────────────│                 │
└─────────────┘                              └─────────────────┘
```

### 8.2 Interaction modell

```python
class Interaction:
    interaction_id: str      # UUID
    context_id: str          # task_id vagy flow_id
    context_type: str        # "task" | "flow"
    channel: str             # "web_ui" | "teams" | "whatsapp"
    interaction_type: str    # free_text | choice | confirmation | form
    prompt: str              # A feltett kérdés
    options: list[dict]      # Választási lehetőségek (choice típusnál)
    questions: list[dict]    # Strukturált kérdések (form típusnál)
    status: str              # pending → answered | expired | cancelled | suspended
    response: Any            # A felhasználó válasza
    responder: str           # Ki válaszolt
    created_at, answered_at, expires_at: datetime
```

### 8.3 Kérdés-válasz életciklus

**Szinkron (WebUI):**
```
1. Ágens hív: ask_user("Melyik verziót?")
2. Broker: create_interaction(channel="web_ui")
   → SQLite-be ment
   → WebUIChannel: SSE event a böngészőnek
   → asyncio.Event létrehozás (in-memory waiter)
3. Broker: wait_for_response(timeout=300)
   → asyncio.Event.wait() 5 percig
4. Felhasználó válaszol a böngészőben
   → POST /api/interactions/respond
   → Broker: submit_response() → Event.set()
5. Ágens megkapja a választ, folytatja a munkát
```

**Aszinkron (Teams/WhatsApp):**
```
1. Ágens hív: ask_user("Jóváhagyod a költségvetést?")
2. Broker: create_interaction(channel="teams")
   → SQLite-be ment
   → TeamsChannel: Adaptive Card küldés
   → WebUIChannel: SSE event (fallback)
3. Broker: wait_for_response(timeout=300, suspend_on_timeout=True)
   → 5 perc várakozás...
   → Nincs válasz → AgentSuspended kivétel
4. Task állapot: "suspended" (NEM "failed")
   → Session state megőrizve az ADK session-ben
5. Órákal később: felhasználó válaszol Teams-ben
   → POST /api/channels/teams/webhook
   → Broker: submit_response()
   → Resume callback → ágens újraindítás ugyanabban a session-ben
6. Ágens folytatja a munkát a válasszal
```

### 8.4 ask_user tool implementáció

A factory két implementációt kínál:

**Broker-alapú (preferált):**
```python
async def ask_user(question, question_type="free_text", options=None) -> str:
    interaction_id = await broker.create_interaction(
        context_id=task_id,
        context_type="task",
        channel=channel,           # "web_ui" | "teams" | "whatsapp"
        interaction_type=question_type,
        prompt=question,
        options=options,
    )
    suspend_on_timeout = (channel != "web_ui")
    response = await broker.wait_for_response(
        interaction_id,
        timeout=300,
        suspend_on_timeout=suspend_on_timeout,
        context_id=task_id,
    )
    return response
```

**Legacy (visszafelé kompatibilitás):**
- Event Bus alapú, asyncio.Future-ökkel
- Csak web_ui csatornát támogatja
- Akkor használja, ha nincs `interaction_broker` konfigurálva

### 8.5 Channel Adapter interfész

```python
class ChannelAdapter(ABC):
    name: str                                    # "web_ui", "teams", "whatsapp"

    async def send_question(self, interaction: Interaction) -> None: ...
    async def setup_routes(self, app: FastAPI) -> None: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
    def format_prompt(self, interaction: Interaction) -> str: ...
```

| Adapter | Küldés módja | Fogadás módja |
|---------|-------------|---------------|
| **WebUIChannel** | SSE event (`task_input_required` / `flow_input_required`) | REST API (`/api/interactions/respond`) |
| **TeamsChannel** | Bot Framework REST API + Adaptive Card | Webhook (`/api/channels/teams/webhook`) |
| **WhatsAppChannel** | Twilio REST API | Webhook (`/api/channels/whatsapp/webhook`) |

### 8.6 SQLite perzisztencia

Az `InteractionStore` WAL módú SQLite-ot használ:

```sql
CREATE TABLE interactions (
    interaction_id TEXT PRIMARY KEY,
    context_id TEXT,
    context_type TEXT,
    channel TEXT,
    interaction_type TEXT,
    prompt TEXT,
    options TEXT,        -- JSON
    questions TEXT,      -- JSON
    metadata TEXT,       -- JSON
    status TEXT,
    response TEXT,       -- JSON
    responder TEXT,
    created_at TEXT,
    answered_at TEXT,
    expires_at TEXT
);
CREATE INDEX idx_status ON interactions(status);
CREATE INDEX idx_context ON interactions(context_id);
CREATE INDEX idx_channel ON interactions(channel);
```

---

## 9. Event Bus és SSE streaming

**Fájl:** `backend/src/events/bus.py`

### 9.1 Működés

Az `EventBus` egy in-memory async pub/sub rendszer:

```python
# Feliratkozás (frontend SSE endpoint)
queue = asyncio.Queue(maxsize=100)
unsubscribe = event_bus.subscribe(queue)

# Esemény kibocsátás (bármelyik komponens)
await event_bus.emit("task_event", {
    "task_id": "...",
    "event_type": "streaming_text",
    "text": "Hello...",
})
```

Az események minden feliratkozónak eljutnak. Ha egy subscriber queue-ja tele van, az üzenet eldobódik (nincs backpressure).

### 9.2 Eseménytípusok

**Task események:**

| Esemény | Leírás |
|---------|--------|
| `task_event` | Minden task-hoz kapcsolódó esemény (altípus: `event_type` mező) |
| `task_completed` | Task sikeresen befejezve |
| `task_failed` | Task hibával leállt |

A `task_event` altípusai (`event_type` mező):

| event_type | Leírás |
|------------|--------|
| `streaming_text` | Részleges szöveg streaming (+ `is_thought` flag) |
| `thinking` | Gondolkodási szöveg (thinking tokens) |
| `agent_response` | Végleges ágens válasz |
| `tool_call` | Eszköz hívás (+ `transfer_context` ha transfer) |
| `tool_result` | Eszköz válasz |
| `agent_suspended` | Ágens felfüggesztve (külső válaszra vár) |

**Flow események:**

| Esemény | Leírás |
|---------|--------|
| `flow_started` | Flow elindult |
| `flow_state_entered` | Új állapotba lépett |
| `flow_agent_streaming_text` | Ágens szöveg streaming |
| `flow_agent_thinking` | Ágens gondolkodás |
| `flow_agent_tool_use` | Ágens eszköz hívás |
| `flow_agent_tool_result` | Ágens eszköz eredmény |
| `flow_agent_task_started` | Ágens feladat indult |
| `flow_agent_task_completed` | Ágens feladat kész |
| `flow_llm_decision` | LLM döntés meghozva |
| `flow_input_required` | Emberi beavatkozás szükséges |
| `flow_user_response` | Felhasználó válaszolt |
| `flow_completed` | Flow befejezve |

**Költség események:**

| Esemény | Leírás |
|---------|--------|
| `cost_event` | LLM hívás költsége (provider, model, tokens, cost_usd) |

### 9.3 Frontend SSE feldolgozás

**Fájl:** `frontend/src/hooks/useSSE.ts`

A frontend `EventSource`-on keresztül csatlakozik:

```typescript
const es = new EventSource("/api/events/stream");

es.addEventListener("task_event", (e) => {
    const data = JSON.parse(e.data);
    if (data.event_type === "streaming_text") {
        taskStore.appendStreamingText(data);  // Typewriter effektus
    } else {
        taskStore.addEvent(data);
    }
});

es.addEventListener("task_input_required", (e) => {
    taskStore.addInteraction({
        interaction_id, task_id, prompt, options, channel
    });
});
```

A `streaming_text` események speciális kezelést kapnak: egymás utáni streaming események összeolvadnak egyetlen `event`-be a store-ban (typewriter effektus a UI-n).

---

## 10. Frontend megjelenítés

### 10.1 Task Timeline

**Fájl:** `frontend/src/components/task/TaskTimeline.tsx`

Az idővonal minden ADK eseményt megjelenít:
- **Szín kódolás:** minden event_type saját háttér- és szegély színnel rendelkezik
- **Transfer context popup:** `tool_call` eseményeknél kattintható "context" badge
- **Delta idő:** az előző esemény óta eltelt idő (`+120ms`, `+1.5s`)
- **Gondolkodás:** `thinking` és `is_thought` események halvány háttérrel

**TransferContextPopup:**
- Középre igazított modális ablak (70vw, max 800px)
- **Session State** szekció: kulcs-érték párok sárga fejléccel
- **Conversation History** szekció: színkódolt előzmények
  - Szöveg üzenetek (kék szegély)
  - Tool call-ok (zöld szegély, JSON args)
  - Tool result-ok (narancs szegély)

### 10.2 Zustand Store-ok

**taskStore:**
- `tasks: Task[]` — feladatok listája
- `pendingInteractions: TaskPendingInteraction[]` — válaszra váró interakciók
- `submitTask()` — feladat beküldés
- `addEvent()` / `appendStreamingText()` — esemény hozzáadás
- `addInteraction()` / `resolveInteraction()` — interakció kezelés

**flowStore:**
- `activeFlows: ActiveFlow[]` — futó flow-k
- `events: FlowEvent[]` — flow események
- `pendingInteractions` — flow interakciók

---

## 11. Startup és inicializálás

**Fájl:** `backend/src/main.py`

A FastAPI lifespan context manager sorrendben inicializál:

```python
async def lifespan(app):
    # 1. Konfiguráció betöltés
    settings = Settings()
    llm_config = load_llm_config(settings.llm_config_path)

    # 2. Infrastruktúra
    event_bus = EventBus()
    cost_tracker = CostTracker(event_bus, llm_config)

    # 3. Ágens rendszer
    agent_factory = AgentFactory(agents_dir, workspace_dir, event_bus, llm_config)
    agent_factory.load_definitions()
    session_manager = SessionManager()
    root_manager = RootAgentManager(agent_factory, root_agents_dir)
    root_manager.load_definitions()

    # 4. Interakciós rendszer
    interaction_store = InteractionStore(settings.interactions_db)
    interaction_broker = InteractionBroker(interaction_store)
    interaction_broker.register_channel(WebUIChannel(event_bus))

    # 5. Opcionális csatornák
    if settings.teams_enabled:
        teams = TeamsChannel(app_id=..., app_password=..., broker=interaction_broker)
        interaction_broker.register_channel(teams)
        await teams.setup_routes(app)

    if settings.whatsapp_enabled:
        whatsapp = WhatsAppChannel(account_sid=..., auth_token=..., broker=interaction_broker)
        interaction_broker.register_channel(whatsapp)
        await whatsapp.setup_routes(app)

    # 6. App state
    app.state.agent_factory = agent_factory
    app.state.session_manager = session_manager
    app.state.root_agent_manager = root_manager
    app.state.interaction_broker = interaction_broker
    app.state.event_bus = event_bus
    app.state.cost_tracker = cost_tracker

    yield  # App fut

    # 7. Cleanup
    interaction_store.close()
    await event_bus.shutdown()
```

---

## 12. API végpontok összefoglaló

### Tasks

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `POST` | `/api/tasks/` | Task beküldése (description, root_agent_definition, channel) |
| `POST` | `/api/tasks/interact` | Legacy interakció válasz |
| `GET` | `/api/tasks/{task_id}` | Task költségjelentés |

### Flows

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `GET` | `/api/flows/` | Flow definíciók listázása |
| `POST` | `/api/flows/start` | Flow indítása |
| `POST` | `/api/flows/interact` | Flow interakció válasz |
| `GET` | `/api/flows/active` | Aktív flow-ok |
| `GET` | `/api/flows/definition/{file}` | Flow definíció |
| `GET` | `/api/flows/raw/{file}` | Nyers YAML |
| `POST` | `/api/flows/upload` | Új flow feltöltése |
| `PUT` | `/api/flows/{file}` | Flow frissítése |
| `DELETE` | `/api/flows/{file}` | Flow törlése |

### Agents

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `GET` | `/api/agents/` | Ágens definíciók listázása |
| `GET` | `/api/agents/{name}` | Ágens részletek (YAML + prompt) |
| `POST` | `/api/agents/` | Új ágens létrehozása |
| `PUT` | `/api/agents/{name}` | Ágens frissítése |
| `DELETE` | `/api/agents/{name}` | Ágens törlése |

### Root Agents

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `GET` | `/api/root-agents/definitions` | Root ágens definíciók |
| `GET` | `/api/root-agents/definitions/{name}` | Root ágens részletek |
| `POST` | `/api/root-agents/definitions` | Új root ágens |
| `PUT` | `/api/root-agents/definitions/{name}` | Root ágens frissítése |
| `DELETE` | `/api/root-agents/definitions/{name}` | Root ágens törlése |
| `GET` | `/api/root-agents/instances` | Futó instance-ok |
| `POST` | `/api/root-agents/instances` | Instance indítása |
| `DELETE` | `/api/root-agents/instances/{id}` | Instance leállítása |

### Interactions

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `POST` | `/api/interactions/respond` | Interakció válasz (unified) |
| `GET` | `/api/interactions/pending` | Függő interakciók |
| `GET` | `/api/interactions/` | Összes interakció |
| `GET` | `/api/interactions/channels` | Elérhető csatornák |

### Webhooks (csatorna-specifikus)

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `POST` | `/api/channels/teams/webhook` | Teams Bot Framework webhook |
| `POST` | `/api/channels/whatsapp/webhook` | Twilio WhatsApp webhook |

### Egyéb

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `GET` | `/api/events/stream` | SSE eseményfolyam |
| `GET` | `/api/llm/providers` | LLM providerek és modellek |
| `GET` | `/health` | Szerver állapot |

---

## 13. Kulcs tervezési döntések

1. **Egyetlen AgentFactory** — Tasks és Flows is ugyanazon a factory-n keresztül hoz létre agenteket, biztosítva a konzisztenciát.

2. **YAML-first konfiguráció** — Az ágens viselkedés teljesen deklaratív; Python kód csak a framework infrastruktúrában van.

3. **Broker pattern a Future helyett** — A régi `asyncio.Future` dict-et az `InteractionBroker` + SQLite váltja, ami perzisztens, multi-channel és restart-safe.

4. **Suspend, ne fail** — Külső csatornákon az `AgentSuspended` kivétel jelzi a felfüggesztést, nem hibát. A session megmarad a későbbi folytatáshoz.

5. **LoopAgent orkesztráció** — Az ADK LoopAgent iteratívan futtatja az orkesztrátort, aki `transfer_to_*` hívásokkal delegál és `exit_loop`-pal fejez be.

6. **Streaming-first** — Minden ADK event SSE-n keresztül azonnal megjelenik a frontenden, beleértve a részleges szöveget, gondolkodást és tool hívásokat.

7. **Channel fallback** — Ha egy külső csatorna nem elérhető, a kérdés automatikusan a web_ui-n is megjelenik.

8. **Peer awareness** — Sub-agentek ismerik egymás képességeit és direkt transfer-t kezdeményezhetnek, nem csak az orkesztrátoron keresztül.
