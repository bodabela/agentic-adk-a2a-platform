# Felhasználói kézikönyv

## Moduláris Multi-Ágens Platform

---

## 1. Rendszer áttekintés

A platform egy AI-alapú, moduláris multi-ágens rendszer, amely lehetővé teszi összetett feladatok automatizálását LLM-ek (nagy nyelvi modellek), ágensek és eszközök összehangolt működtetésével.

### Fő komponensek

| Komponens | Leírás |
|-----------|--------|
| **Frontend** | React webalkalmazás — dashboard, feladat-beküldés, flow-indítás, költségkövetés |
| **Backend** | FastAPI szerver — API végpontok, flow motor, költségkövetés, eseménykezelés |
| **Flow Engine** | YAML-alapú állapotgép — többlépéses munkafolyamatok definiálása és futtatása |
| **Ágensek** | Önálló modulok, amelyek LLM-eket és eszközöket használva hajtanak végre feladatokat |
| **LLM providerek** | Több szolgáltató támogatása: Google Gemini, Anthropic Claude, OpenAI GPT |

### Architektúra

```
Felhasználó (böngésző)
    │
    ▼
React Frontend ──SSE──▶ Valós idejű események
    │
    ▼
FastAPI Backend
    ├── Task API        → Feladatok beküldése és végrehajtása
    ├── Flow API        → Munkafolyamatok indítása és kezelése
    ├── Event Bus       → Esemény-broadcast minden kliensnek
    ├── Cost Tracker    → LLM és eszközhasználat költségkövetése
    └── Agent Registry  → Modulok felfedezése és nyilvántartása
         │
         ▼
    Ágens modulok (coder_agent, stb.)
         │
         ▼
    LLM providerek (Google, Anthropic, OpenAI)
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

### 2.6 Cost Tracking (Költségkövetés)

Minden LLM hívás és eszközhasználat költsége automatikusan mérésre kerül:

- Token-szintű árazás (input/output tokenek)
- Task-szintű aggregáció
- Valós idejű megjelenítés a dashboardon és a Costs oldalon

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

### 3.4 Costs oldal

Költségek részletes nyomon követése.

- **Total Spend** — teljes költés összege
- **Cost by Task** — feladatonkénti költségbontás
- **Recent Events** — utolsó költségesemények időrendben (modul, ágens, művelet típusa, összeg)

### 3.5 Navigáció

A bal oldali **Sidebar** tartalmazza a navigációs linkeket:
- Dashboard, Tasks, Flows, Costs
- Állapotjelzők: aktív flow-ok és függő interakciók száma

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

A platform **multi-projekt** felépítésű. Minden projekt a `projects/` könyvtárban található, saját ágensekkel, root ágensekkel és flow-kkal:

```
projects/
├── personal_assistant/        # Alapértelmezett projekt
│   ├── agents/                # Ágens definíciók
│   │   ├── calendar_agent/
│   │   │   ├── agent.yaml           # Ágens YAML konfiguráció
│   │   │   ├── prompts/
│   │   │   │   └── system_prompt.md  # System prompt
│   │   │   └── tools/
│   │   │       └── mcp_server.py     # MCP eszközök
│   │   ├── email_agent/
│   │   ├── research_agent/
│   │   └── ...
│   ├── root_agents/           # Root orkesztrátor definíciók
│   │   └── personal_assistant.root.yaml
│   └── flows/                 # Flow definíciók
│       ├── meeting_prep.flow.yaml
│       └── schedule_meeting.flow.yaml
└── another_project/           # Új projekt hozzáadása
    ├── agents/
    ├── root_agents/
    └── flows/
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

---

## 8. API végpontok

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| GET | `/health` | Szerver állapot ellenőrzés |
| POST | `/api/tasks/` | Feladat beküldése |
| GET | `/api/tasks/{task_id}` | Feladat költségjelentése |
| GET | `/api/flows/` | Elérhető flow-k listázása |
| POST | `/api/flows/start` | Flow indítása |
| POST | `/api/flows/interact` | Emberi válasz beküldése flow-nak |
| GET | `/api/flows/active` | Aktív flow-k listája |
| GET | `/api/agents/` | Ágens definíciók listázása |
| GET | `/api/agents/{name}` | Ágens részletek (YAML + prompt + definíció) |
| POST | `/api/agents/` | Ágens létrehozása |
| PUT | `/api/agents/{name}` | Ágens módosítása |
| DELETE | `/api/agents/{name}` | Ágens törlése |
| GET | `/api/root-agents/` | Root ágens definíciók |
| GET | `/api/llm/providers` | LLM providerek és modellek |
| GET | `/api/tools/` | Összes elérhető MCP és beépített eszköz |
| GET | `/api/interactions/pending` | Függő emberi interakciók |
| POST | `/api/interactions/respond` | Válasz küldése interakcióra |
| GET | `/api/events/stream` | SSE eseményfolyam |
