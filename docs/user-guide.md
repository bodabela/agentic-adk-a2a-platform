# Felhasználói kézikönyv

## Moduláris Multi-Ágens Platform

---

## 1. Rendszer áttekintés

A platform egy AI-alapú, moduláris multi-ágens rendszer, amely lehetővé teszi összetett feladatok automatizálását LLM-ek (nagy nyelvi modellek), ágensek és eszközök összehangolt működtetésével.

### Fő komponensek

| Komponens | Leírás |
|-----------|--------|
| **Frontend** | React webalkalmazás — dashboard, feladat-beküldés, flow-indítás, ágens-kezelés, költségkövetés, tracing |
| **Backend** | FastAPI szerver — API végpontok, flow motor, költségkövetés, tracing, eseménykezelés |
| **Flow Engine** | YAML-alapú állapotgép — többlépéses munkafolyamatok definiálása és futtatása |
| **Ágensek** | Önálló modulok, amelyek LLM-eket és eszközöket használva hajtanak végre feladatokat |
| **LLM providerek** | Több szolgáltató támogatása: Google Gemini, Anthropic Claude, OpenAI GPT |
| **Observability** | Prometheus metrikák, Grafana dashboardok, Tempo elosztott nyomkövetés, Langfuse LLM analytics |
| **Multi-channel** | Emberi interakciók több csatornán: Web UI, Microsoft Teams, WhatsApp (Twilio) |

### Architektúra

```
Felhasználó (böngésző / Teams / WhatsApp)
    │
    ▼
React Frontend ──SSE──▶ Valós idejű események
    │
    ▼
FastAPI Backend
    ├── Task API           → Feladatok beküldése és végrehajtása
    ├── Flow API           → Munkafolyamatok indítása és kezelése
    ├── Session API        → ADK session-ök kezelése
    ├── Event Bus          → Esemény-broadcast minden kliensnek
    ├── Cost Tracker       → LLM és eszközhasználat költségkövetése
    ├── Interaction Broker → Multi-channel emberi interakciók
    ├── Tracing            → OpenTelemetry nyomkövetés
    └── Agent Registry     → Modulok felfedezése és nyilvántartása
         │
         ▼
    Ágens modulok (calendar, email, research, stb.)
         │
         ▼
    LLM providerek (Google, Anthropic, OpenAI)

Observability Stack
    ├── Prometheus   → Metrikagyűjtés (/metrics endpoint)
    ├── Tempo        → Elosztott nyomkövetés (OTLP gRPC)
    ├── Grafana      → Dashboardok és vizualizáció
    └── Langfuse     → LLM-specifikus analytics
```

---

## 2. Alapfogalmak

### 2.1 Task (Feladat)

A **task** egy felhasználó által beküldött munkaegység szöveges leírással. A rendszer a root ágens segítségével dolgozza fel, aki szükség szerint további ágens-moduloknak delegálja a munkát.

- Beküldés a **Tasks** oldalon
- Minden taskhoz egyedi `task_id` tartozik
- Állapotok: `submitted` → `running` → `completed` / `failed`
- A végrehajtás során keletkező események valós időben jelennek meg
- Minden task költsége nyomon követhető

### 2.2 Flow (Munkafolyamat)

A **flow** egy YAML fájlban definiált, többlépéses állapotgép. A task-kal ellentétben a flow előre meghatározott lépéseket követ, ahol minden lépés (state) típusa megadja, mi történik.

- Definiálás: `flows/*.flow.yaml` fájlok
- Indítás a **Flows** oldalon (legördülő menüből kiválasztva)
- Trigger data: a flow induló bemenete (JSON formátumban)
- Az állapotok között automatikusan halad, de egyes pontokon emberi beavatkozást kérhet

### 2.3 Agent (Ágens)

Az **ágens** egy önálló modul, amely LLM-eket és eszközöket használva hajt végre feladatokat. Minden ágens a `projects/<projekt>/agents/<agent_name>/` könyvtárban található, és a következő fájlokból áll:

- **agent.yaml**: ágens konfiguráció (név, modell, képességek, eszközök)
- **prompts/system_prompt.md**: az ágens viselkedési utasításai
- **tools/mcp_server.py**: MCP protokollon elérhető lokális eszközök (opcionális)

Az ágensek a Google ADK-n keresztül futnak, a root ágens sub-agentekként koordinálja őket.

### 2.4 LLM Provider (Nyelvi modell szolgáltató)

A rendszer több LLM szolgáltatót támogat, amelyek között flow- és feladatszinten is lehet választani:

| Provider | Modellek | API kulcs env változó |
|----------|----------|----------------------|
| **Google** | gemini-3.1-pro-preview, gemini-2.0-flash | `GOOGLE_API_KEY` |
| **Anthropic** | claude-sonnet-4, claude-haiku-3 | `ANTHROPIC_API_KEY` |
| **OpenAI** | gpt-4o, gpt-4o-mini | `OPENAI_API_KEY` |

Az alapértelmezett provider és modell a `config/llm_providers.yaml` fájlban konfigurálható.

### 2.5 Event Bus (Eseményrendszer)

A rendszer minden fontos eseményt valós időben közvetít a frontend felé SSE (Server-Sent Events) protokollon:

- Task események (beküldés, lépések, befejezés)
- Flow események (állapotváltás, döntések, emberi beavatkozás kérése)
- Költség események (minden LLM hívás és eszközhasználat)
- Tracing események (span-ok, trace-ek)

### 2.6 Cost Tracking (Költségkövetés)

Minden LLM hívás és eszközhasználat költsége automatikusan mérésre kerül:

- Token-szintű árazás (input/output tokenek)
- Task-szintű aggregáció
- Valós idejű megjelenítés a dashboardon és a Costs oldalon

### 2.7 Tracing & Observability (Nyomkövetés és megfigyelhetőség)

A platform teljes megfigyelhetőségi stack-kel rendelkezik:

- **OpenTelemetry** — elosztott nyomkövetés (trace-ek és span-ok) a backend műveletekhez
- **Prometheus** — metrikagyűjtés a `/metrics` végponton
- **Grafana** — előkonfigurált dashboardok a platform teljesítményéhez
- **Tempo** — trace backend, amely tárolja és indexeli a nyomkövetési adatokat
- **Langfuse** — LLM-specifikus analytics: prompt-ok, válaszok, költségek, latencia

A trace-ek a frontend **Trace** oldalán is megtekinthetők, illetve deep-linkek vezetnek a Grafana és Langfuse felületekre.

### 2.8 Multi-channel Interactions (Többcsatornás interakciók)

Az emberi beavatkozást igénylő flow lépések több csatornán is kézbesíthetők:

| Csatorna | Leírás |
|----------|--------|
| **Web UI** | Alapértelmezett — a böngészős felületen jelenik meg |
| **Microsoft Teams** | Bot-on keresztül küldött értesítések és válaszlehetőségek |
| **WhatsApp** | Twilio integráción keresztül SMS-szerű interakció |

A csatornák az `InteractionBroker`-en keresztül működnek, és a `.env` fájlban konfigurálhatók (lásd 6.2).

### 2.9 Sessions (Munkamenetek)

Az ADK session-ök kezelik az ágens-felhasználó közötti állapotot:

- Minden task végrehajtás saját session-ben fut
- A session-ök tartalmazzák a kontextust, előzményeket
- A **Sessions** oldalon listázhatók, leállíthatók és törölhetők

---

## 3. Felhasználói felület

### 3.1 Dashboard

Az áttekintő oldal KPI kártyákat jelenít meg:

- **Total Tasks** — összes beküldött feladat száma
- **Running** — jelenleg futó feladatok
- **Active Flows** — aktív munkafolyamatok száma
- **Pending Interactions** — emberi beavatkozásra váró flow lépések
- **Total Cost** — összesített költség (USD)

### 3.2 Tasks oldal

Feladatok beküldése és nyomon követése.

**Feladat beküldése:**
1. Írja be a feladat leírását a szövegmezőbe
2. Kattintson a **Submit** gombra
3. A rendszer létrehoz egy task-ot és elindítja a feldolgozást

**Feladat követése:**
- Az idővonal (timeline) mutatja a feladat eseményeit időrendben
- Állapot badge jelzi az aktuális státuszt (submitted, running, completed, failed)
- Az ágens diagram vizualizálja az aktuális ágens hierarchiát és delegálást

### 3.3 Flows oldal

Munkafolyamatok indítása és kezelése.

**Flow indítása:**
1. Válasszon egy flow-t a **legördülő menüből** — a rendszer automatikusan betölti az elérhető flow-okat
2. A kiválasztáskor a **Trigger data** mező automatikusan kitöltődik a flow alapértelmezett bemenetével
3. Szerkessze a trigger data JSON-t az igényeinek megfelelően
4. Válasszon **LLM providert** és **modellt** (opcionális — alapértelmezés a flow konfigurációjából)
5. Kattintson a **Start Flow** gombra

**Aktív flow-ok:**
- A flow kártyák mutatják az aktuális állapotot és a lépések státuszát
- Ha egy flow emberi beavatkozást kér (human interaction), megjelenik a kérdés és a válaszlehetőségek
- A flow diagram vizuálisan ábrázolja az állapotgépet és az aktuális pozíciót

### 3.4 Agents oldal

Ágens definíciók böngészése és kezelése.

- Elérhető ágensek listázása (YAML konfiguráció, prompt, eszközök)
- Új ágens létrehozása a **+ New** gombbal
- Ágens szerkesztése és törlése

### 3.5 Root Agents oldal

Root orkesztrátor ágensek kezelése.

- Root ágens definíciók listázása
- Sub-agent hozzárendelések és konfiguráció megtekintése

### 3.6 Tools oldal

Az összes elérhető eszköz (MCP és beépített) böngészése.

- Eszközök listázása teljes paraméter sémával
- Szűrés ágens vagy eszköz típus alapján

### 3.7 Sessions oldal

ADK munkamenetek kezelése.

- Aktív és lezárt session-ök listázása
- Session leállítása és törlése

### 3.8 Costs oldal

Költségek részletes nyomon követése.

- **Total Spend** — teljes költés összege
- **Cost by Task** — feladatonkénti költségbontás
- **Recent Events** — utolsó költségesemények időrendben (modul, ágens, művelet típusa, összeg)

### 3.9 Trace oldal

Egyedi trace-ek részletes megtekintése.

- Span-ok hierarchikus megjelenítése
- Deep-linkek Grafana és Langfuse dashboardokra
- Elérhető a `/trace/:traceId` útvonalon (task és flow oldalakról linkelhető)

### 3.10 Navigáció

A bal oldali **Sidebar** tartalmazza a navigációs linkeket:
- Dashboard, Tasks, Flows, Agents, Root Agents, Tools, Sessions, Costs

A felső **TopBar** megjeleníti:
- Platform neve
- Aktuális összköltség (CostBadge)
- SSE kapcsolat állapotjelző (zöld/piros pont)

---

## 4. Flow-k részletesen

### 4.1 Flow YAML struktúra

Egy flow definíció a következő fő részekből áll:

```yaml
flow:
  name: "flow_neve"
  version: "1.0.0"
  description: "A flow leírása"

  trigger:
    type: "manual"
    input_schema:           # A trigger data várt struktúrája
      type: "object"
      required: ["field1"]
      properties:
        field1:
          type: "string"

  config:
    max_retry_loops: 3      # Újrapróbálkozási limit
    timeout_minutes: 30     # Időtúllépés
    provider: "google"      # Alapértelmezett LLM provider
    model: "gemini-3.1-pro-preview"

  states:
    step_1:
      type: "agent_task"
      # ...
    step_2:
      type: "llm_decision"
      # ...
```

### 4.2 Trigger és input_schema

A `trigger` rész határozza meg, hogyan indul a flow:

- **type: "manual"** — kézi indítás a felületen
- **input_schema** — JSON Schema formátumú leírás, amely megadja, milyen mezőket vár a flow bemenetként

A felületen a flow kiválasztásakor az `input_schema` alapján automatikusan generálódik egy alapértelmezett JSON, amelyet a felhasználó szerkeszthet.

### 4.3 Node típusok

A flow minden állapota (state) egy node, amelynek típusa határozza meg a viselkedését:

#### agent_task — Ágens feladat

Egy ágens modult bíz meg feladattal. Az ágens LLM-et és eszközöket használva dolgozik.

```yaml
generate_code:
  type: "agent_task"
  agent: "coder_agent"          # Meghívott ágens modul
  description: "Kód generálása"
  input:
    requirement: "{{ trigger.task_description }}"  # Template kifejezés
  output: [source_files, summary]
  on_complete: "next_step"      # Sikeres befejezés utáni állapot
  on_error: "error_handler"     # Hiba esetén
```

#### llm_decision — LLM döntés

Egy LLM-et hív meg, hogy válasszon a lehetséges átmenetek közül.

```yaml
review_result:
  type: "llm_decision"
  context:
    - "{{ states.generate_code.output }}"   # Kontextus az LLM-nek
  decision_prompt: |
    Értékeld a generált kódot:
    - Ha jó → accept
    - Ha javítani kell → revise
  transitions:
    accept: "complete_success"
    revise: "generate_code"
```

#### human_interaction — Emberi beavatkozás

Megállítja a flow-t és a felhasználótól vár választ.

```yaml
ask_user:
  type: "human_interaction"
  interaction_type: "free_text"   # vagy: selection, confirmation
  prompt: "Kérjük, adjon meg további részleteket."
  options:                         # selection típusnál
    - id: "option_a"
      label: "A lehetőség"
    - id: "option_b"
      label: "B lehetőség"
  on_response: "next_step"
```

Interakció típusok:
- **free_text** — szabad szöveges válasz
- **selection** — előre megadott lehetőségek közül választás
- **confirmation** — igen/nem megerősítés

#### parallel — Párhuzamos végrehajtás

Több ágat futtat egyszerre, majd egyesíti az eredményt.

```yaml
parallel_work:
  type: "parallel"
  branches:
    branch_a:
      type: "agent_task"
      agent: "agent_1"
      input: { ... }
    branch_b:
      type: "agent_task"
      agent: "agent_2"
      input: { ... }
  join: "all"              # "all" = mindegyik végezzen, "any" = elég egy
  on_complete: "merge_step"
```

#### conditional — Feltételes elágazás

Boolean feltétel alapján választ két állapot között.

```yaml
check_condition:
  type: "conditional"
  condition: "{{ flow.phase == 'production' }}"
  if_true: "deploy_step"
  if_false: "staging_step"
```

#### terminal — Végállapot

Lezárja a flow-t sikerrel vagy hibával.

```yaml
complete_success:
  type: "terminal"
  status: "success"
  output:
    result: "{{ states.generate_code.output }}"
```

### 4.4 Template kifejezések

A flow node-ok közötti adatáramlást template kifejezések biztosítják `{{ ... }}` szintaxissal:

| Kifejezés | Jelentés |
|-----------|---------|
| `{{ trigger.field }}` | A flow induló bemenetének egy mezője |
| `{{ states.step_name.output }}` | Egy korábbi lépés kimenete |
| `{{ states.step_name.output.field }}` | Kimenet egy adott mezője |
| `{{ flow.variable }}` | Flow szintű változó (side_effect-tel állítható) |
| `{{ error }}` | Hiba üzenet (on_error ágban) |
| `{{ value \| default('fallback') }}` | Alapértelmezett érték szűrő |

### 4.5 Újrapróbálkozás (retry)

Az `agent_task` node-ok rendelkezhetnek `retry_loop` paraméterrel. Ha egy lépés hibával végződik, de van `on_error` átmenete, a flow újra megpróbálhatja. A `config.max_retry_loops` érték határozza meg, hányszor próbálkozhat, mielőtt véglegesen elbukna.

### 4.6 Flow életciklus

```
                    ┌─────────┐
                    │ PENDING │
                    └────┬────┘
                         │ start
                    ┌────▼────┐
              ┌─────│ RUNNING │◄────────┐
              │     └────┬────┘         │
              │          │              │
     human    │     ┌────▼─────┐   ágens/LLM
   interaction│     │ állapot  │   válasz
              │     │ végrehajtás   │
              │     └────┬─────┘    │
              │          │          │
         ┌────▼──────┐   │     ┌───▼────┐
         │ WAITING   │   │     │ next   │
         │ _INPUT    ├───┘     │ state  ├──┘
         └───────────┘         └───┬────┘
                                   │ terminal
                          ┌────────▼────────┐
                          │ COMPLETED/FAILED │
                          └─────────────────┘
```

---

## 5. Task-ok részletesen

### 5.1 Feladat beküldése

Egy task beküldésekor a következő történik:

1. A felhasználó megadja a feladat szöveges leírását
2. A rendszer generál egy egyedi `task_id`-t
3. A root ágens megkapja a feladatot
4. A root ágens elemzi a feladatot és szükség esetén delegálja ágens-moduloknak
5. Minden lépés eseményeket generál, amelyek valós időben megjelennek

### 5.2 Root ágens és delegálás

A **root ágens** a központi orkesztrátor:

- Fogadja a felhasználói feladatokat
- Ismeri az elérhető ágens-modulokat (Agent Registry)
- Eldönti, melyik modult hívja meg A2A protokollon
- Összefogja a részeredményeket

### 5.3 Task vs Flow

| Szempont | Task | Flow |
|----------|------|------|
| Definiálás | Szabad szöveges leírás | YAML fájl, előre definiált lépések |
| Végrehajtás | Root ágens dönt a lépésekről | Állapotgép, előre meghatározott útvonal |
| Rugalmasság | Magas — az LLM dönti el, mit csinál | Közepes — a YAML határozza meg a struktúrát |
| Determinizmus | Alacsony | Magas (az LLM döntési pontok kivételével) |
| Használat | Ad-hoc feladatok | Ismétlődő, strukturált munkafolyamatok |

---

## 6. Konfiguráció

### 6.1 Projekt struktúra

A platform **multi-projekt** felépítésű. A teljes könyvtárszerkezet:

```
agentic-adk-a2a-platform/
├── backend/                          # FastAPI backend
│   ├── src/
│   │   ├── main.py                   # Alkalmazás belépési pont
│   │   ├── config.py                 # Beállítások (Pydantic Settings)
│   │   ├── routers/                  # API route-ok
│   │   │   ├── health.py             # Health check
│   │   │   ├── tasks.py              # Task CRUD + végrehajtás
│   │   │   ├── flows.py              # Flow CRUD + indítás
│   │   │   ├── agents.py             # Ágens CRUD
│   │   │   ├── root_agents.py        # Root ágens kezelés
│   │   │   ├── sessions.py           # ADK session-ök
│   │   │   ├── events.py             # SSE stream
│   │   │   ├── interactions.py       # Emberi interakciók
│   │   │   ├── tools.py              # Eszköz felfedezés
│   │   │   ├── llm.py                # LLM konfiguráció
│   │   │   └── traces.py             # Nyomkövetés
│   │   ├── features/
│   │   │   ├── flows/engine/         # Flow állapotgép motor
│   │   │   │   ├── engine.py         # Fő végrehajtó
│   │   │   │   ├── context.py        # Futási kontextus
│   │   │   │   ├── parallel.py       # Párhuzamos végrehajtás
│   │   │   │   ├── retry_manager.py  # Újrapróbálkozás
│   │   │   │   ├── node_handlers/    # Node típus kezelők
│   │   │   │   └── dsl/              # YAML DSL parser + validátor
│   │   │   └── tasks/
│   │   │       └── executor.py       # Task végrehajtó
│   │   └── shared/
│   │       ├── agents/               # Ágens factory + loader
│   │       ├── cost/                 # Költségkövetés
│   │       ├── events/               # Event bus
│   │       ├── interactions/         # Interakció kezelés
│   │       │   ├── broker.py         # Multi-channel broker
│   │       │   ├── store.py          # SQLite tároló
│   │       │   └── channels/         # Csatorna adapterek
│   │       │       ├── web_ui.py     # Web UI csatorna
│   │       │       ├── teams.py      # Microsoft Teams
│   │       │       └── whatsapp.py   # WhatsApp (Twilio)
│   │       ├── llm/                  # LLM provider konfiguráció
│   │       ├── tracing/              # OpenTelemetry integráció
│   │       │   ├── provider.py       # Tracing inicializálás
│   │       │   ├── callbacks.py      # Span callback-ek
│   │       │   ├── metrics.py        # Prometheus metrikák
│   │       │   └── langfuse_exporter.py  # Langfuse export
│   │       └── logging.py
│   ├── tests/                        # Pytest tesztek
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/                         # React + Vite frontend
│   ├── src/
│   │   ├── App.tsx                   # Routing
│   │   ├── features/
│   │   │   ├── dashboard/            # Áttekintő oldal
│   │   │   ├── tasks/                # Feladatok + ágens diagram
│   │   │   ├── flows/                # Munkafolyamatok + flow diagram
│   │   │   ├── agents/               # Ágens kezelés
│   │   │   ├── root-agents/          # Root ágens kezelés
│   │   │   ├── tools/                # Eszköz böngésző
│   │   │   ├── sessions/             # Session kezelés
│   │   │   ├── costs/                # Költségek
│   │   │   └── traces/               # Trace megjelenítő
│   │   └── shared/
│   │       ├── layout/               # AppShell, Sidebar, TopBar
│   │       ├── hooks/useSSE.ts       # SSE hook
│   │       ├── components/           # CostBadge, AgentBadges, TraceLinks
│   │       └── types/events.ts       # Esemény típusok
│   ├── Dockerfile
│   └── nginx.conf
│
├── projects/                         # Multi-projekt ágensek
│   └── personal_assistant/           # Alapértelmezett projekt
│       ├── agents/                   # Ágens definíciók
│       │   ├── calendar_agent/
│       │   │   ├── agent.yaml
│       │   │   ├── prompts/system_prompt.md
│       │   │   └── tools/mcp_server.py
│       │   ├── comms_agent/          # Kommunikációs ágens
│       │   ├── dev_agent/            # Fejlesztői ágens
│       │   ├── document_agent/       # Dokumentum ágens
│       │   ├── email_agent/          # Email ágens
│       │   ├── research_agent/       # Kutatási ágens
│       │   ├── task_agent/           # Feladat ágens
│       │   └── user_agent/           # Felhasználói ágens
│       ├── root_agents/
│       │   └── personal_assistant.root.yaml
│       └── flows/
│           ├── meeting_prep.flow.yaml
│           ├── schedule_meeting.flow.yaml
│           └── simple_code_task.flow.yaml
│
├── infra/                            # Observability infrastruktúra
│   ├── prometheus/prometheus.yml     # Metrikagyűjtés konfig
│   ├── grafana/
│   │   ├── dashboards/agent-platform.json  # Előkonfigurált dashboard
│   │   └── provisioning/             # Datasource + dashboard provisioning
│   └── tempo/tempo.yaml              # Trace backend konfig
│
├── config/
│   └── llm_providers.yaml            # LLM provider konfiguráció
│
├── docs/                             # Dokumentáció
├── workspace/                        # Ágens munkaterület
├── docker-compose.yaml               # Fő compose (dev + observability)
├── docker-compose.override.yaml      # Fejlesztői override-ok
├── docker-compose.prod.yaml          # Éles konfiguráció
├── run.cmd / run-dev.cmd             # Windows indítószkriptek
├── Makefile                          # Build automatizáció
└── .env / .env.example               # Környezeti változók
```

Az aktív projekt az `APP_PROJECT` környezeti változóval választható ki (lásd 6.2).

### 6.2 Környezeti változók

A `.env` fájlban (vagy az operációs rendszer környezeti változóiban) állítandók:

```env
# API kulcsok (a modell/árazás konfig a config/llm_providers.yaml fájlban)
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

APP_DEBUG=true

# Aktív projekt kiválasztása (könyvtárnév a projects/ alatt)
APP_PROJECT=personal_assistant

# Tracing / Observability
APP_TRACING_ENABLED=true
APP_OTLP_ENDPOINT=http://tempo:4317

# Langfuse (LLM analytics)
APP_LANGFUSE_ENABLED=true
APP_LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key

# Dashboard URL-ek (frontend deep-linkekhez)
APP_GRAFANA_BASE_URL=http://localhost:3000
APP_LANGFUSE_BASE_URL=http://localhost:3001

# Microsoft Teams csatorna (opcionális)
APP_TEAMS_ENABLED=false
APP_TEAMS_APP_ID=
APP_TEAMS_APP_PASSWORD=
APP_TEAMS_DEFAULT_CONVERSATION_ID=

# WhatsApp / Twilio csatorna (opcionális)
APP_WHATSAPP_ENABLED=false
APP_WHATSAPP_ACCOUNT_SID=
APP_WHATSAPP_AUTH_TOKEN=
APP_WHATSAPP_FROM_NUMBER=
```

**Projekt váltása:**

```bash
# .env fájlban:
APP_PROJECT=another_project

# Vagy környezeti változóval:
set APP_PROJECT=another_project      # Windows
export APP_PROJECT=another_project   # Linux/macOS
```

### 6.3 LLM providerek konfigurálása

A `config/llm_providers.yaml` fájlban:

```yaml
defaults:
  provider: google
  model: gemini-3.1-pro-preview

providers:
  google:
    display_name: "Google Gemini"
    api_key_env: "GOOGLE_API_KEY"
    models:
      gemini-3.1-pro-preview:
        display_name: "Gemini 3.1 Pro"
        pricing:
          input_per_token: 0.00000125
          output_per_token: 0.000005
        max_tokens: 65536
```

### 6.4 Új ágens hozzáadása

Hozzon létre egy új könyvtárat a projekt `agents/` mappájában:

```
projects/<projekt>/agents/<agent_name>/
├── agent.yaml
├── prompts/
│   └── system_prompt.md
└── tools/                  # opcionális
    └── mcp_server.py
```

Az ágens automatikusan megjelenik a felületen és használható flow-kban és task-okban. A webes felületen az **Agents** oldalon is létrehozható a **+ New** gombbal.

### 6.5 Flow-k hozzáadása

Új flow létrehozásához hozzon létre egy `.flow.yaml` fájlt a projekt `flows/` könyvtárában. A flow automatikusan megjelenik a Flows oldal legördülő menüjében.

---

## 7. Indítás

### Docker (ajánlott)

**Éles mód** (statikus frontend build):

```bash
# Windows — egy kattintás:
run.cmd

# Linux / macOS:
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d
```

**Fejlesztői mód** (hot reload backend + frontend):

```bash
# Windows — egy kattintás:
run-dev.cmd

# Linux / macOS:
docker compose up --build -d
```

Fejlesztői módban a `backend/src/` és `frontend/src/` mappák be vannak mount-olva a konténerekbe, így a kódmódosítások automatikus újraindítást (uvicorn `--reload`) és HMR-t (Vite) aktiválnak.

A `docker-compose.yaml` a következő szolgáltatásokat indítja:

| Szolgáltatás | Leírás |
|-------------|--------|
| **backend** | FastAPI szerver (port 8000) |
| **frontend** | React app Nginx-szel (port 5173) |
| **tempo** | Elosztott trace backend (port 4317 gRPC, 3200 query) |
| **prometheus** | Metrikagyűjtés (port 9090) |
| **grafana** | Dashboard-ok (port 3000, admin/admin) |
| **langfuse** | LLM analytics (port 3001) |
| **langfuse-db** | PostgreSQL a Langfuse-hoz |

A `run.cmd` és `run-dev.cmd` szkriptek automatikusan:
- Ellenőrzik a Docker elérhetőségét
- Megkeresik a projekt könyvtárat
- Létrehozzák a `.env` fájlt, ha nincs (`.env.example`-ból)
- Elindítják a szolgáltatásokat
- Megvárják, amíg a backend egészséges lesz
- Leállítják a szolgáltatásokat bármilyen gombnyomásra

### Helyi futtatás (Docker nélkül)

```bash
# Telepítés
cd backend && pip install -e ".[dev]"
cd frontend && pnpm install

# Backend indítása (1. terminál)
cd backend
uvicorn src.main:app --reload --port 8000

# Frontend indítása (2. terminál)
cd frontend
pnpm dev
```

### Elérhetőség

| Szolgáltatás | URL |
|-------------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| SSE Stream | http://localhost:8000/api/events/stream |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Tempo (query) | http://localhost:3200 |
| Langfuse | http://localhost:3001 |

---

## 8. API végpontok

### Client API

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| GET | `/health` | Szerver állapot ellenőrzés |
| POST | `/api/tasks/` | Feladat beküldése |
| GET | `/api/tasks/{task_id}` | Feladat költségjelentése |
| POST | `/api/flows/start` | Flow indítása |
| POST | `/api/flows/interact` | Emberi válasz beküldése flow-nak |
| GET | `/api/events/stream` | SSE eseményfolyam |
| GET | `/api/interactions/pending` | Függő emberi interakciók |
| POST | `/api/interactions/respond` | Válasz küldése interakcióra |

### Admin API

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| GET | `/api/flows/` | Elérhető flow-k listázása |
| GET | `/api/flows/active` | Aktív flow-k listája |
| GET | `/api/agents/` | Ágens definíciók listázása |
| GET | `/api/agents/{name}` | Ágens részletek (YAML + prompt + definíció) |
| POST | `/api/agents/` | Ágens létrehozása |
| PUT | `/api/agents/{name}` | Ágens módosítása |
| DELETE | `/api/agents/{name}` | Ágens törlése |
| GET | `/api/root-agents/` | Root ágens definíciók |
| GET | `/api/llm/providers` | LLM providerek és modellek |
| GET | `/api/tools/` | Összes elérhető MCP és beépített eszköz |
| GET | `/api/sessions/` | ADK session-ök listázása |
| DELETE | `/api/sessions/{id}` | Session törlése |
| GET | `/api/traces/` | Trace-ek listázása |
| GET | `/api/traces/{trace_id}` | Trace részletek |
| GET | `/metrics` | Prometheus metrikák (ha tracing engedélyezett) |
