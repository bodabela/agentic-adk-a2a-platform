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
| **A2A Gateway** | Ágensek, root ágensek és flow-k kiajánlása szabványos A2A (Agent-to-Agent) protokollon |

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
    ├── A2A Gateway        → Ágensek/flow-k kiajánlása A2A protokollon
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
| **Google** | gemini-3.1-pro-preview, gemini-2.5-flash, gemini-2.5-pro | `GOOGLE_API_KEY` |
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

A csatornák az `InteractionBroker`-en keresztül működnek, és a `.env` fájlban konfigurálhatók (lásd 11.1).

### 2.9 Sessions (Munkamenetek)

Az ADK session-ök kezelik az ágens-felhasználó közötti állapotot:

- Minden task végrehajtás saját session-ben fut
- A session-ök tartalmazzák a kontextust, előzményeket
- A **Sessions** oldalon listázhatók, leállíthatók és törölhetők

---

## 3. Projekt struktúra és létrehozás

### 3.1 Multi-projekt felépítés

A platform **multi-projekt** felépítésű. Minden projekt a `projects/` könyvtárban kap egy saját mappát:

```
projects/
├── personal_assistant/          # 1. projekt
│   ├── agents/                  # Ágens definíciók
│   │   ├── calendar_agent/
│   │   │   ├── agent.yaml       # Ágens konfiguráció
│   │   │   ├── prompts/
│   │   │   │   └── system_prompt.md
│   │   │   └── tools/
│   │   │       └── mcp_server.py
│   │   ├── email_agent/
│   │   └── ...
│   ├── root_agents/             # Root orkesztrátor ágensek
│   │   └── personal_assistant.root.yaml
│   └── flows/                   # Munkafolyamat definíciók
│       ├── meeting_prep.flow.yaml
│       └── simple_code_task.flow.yaml
│
└── my_new_project/              # 2. projekt (saját ágensekkel és flow-kkal)
    ├── agents/
    ├── root_agents/
    └── flows/
```

### 3.2 Új projekt létrehozása

1. Hozzon létre egy új könyvtárat a `projects/` mappában:
   ```
   projects/my_project/
   ├── agents/
   ├── root_agents/
   └── flows/
   ```

2. Állítsa be az aktív projektet a `.env` fájlban:
   ```env
   APP_PROJECT=my_project
   ```

3. Hozza létre a szükséges ágens definíciókat, root ágenst és flow-kat (lásd a következő fejezetek).

4. Indítsa újra a backend-et — az ágensek és flow-k automatikusan betöltődnek.

---

## 4. Agent YAML referencia

Minden ágens a `projects/<projekt>/agents/<agent_name>/agent.yaml` fájlban definiált.

### 4.1 Teljes séma

```yaml
agent:
  # ── Azonosítás ──────────────────────────────────────
  name: "agent_neve"                        # KÖTELEZŐ — egyedi azonosító
  version: "0.1.0"                          # Szemantikus verzió (alapértelmezett: "0.1.0")
  description: "Az ágens leírása"           # Emberileg olvasható leírás
  category: "general"                       # Kategória (pl. "personal_assistant", "general", "interaction")

  # ── LLM konfiguráció ───────────────────────────────
  model: "gemini-2.5-flash"                 # Elsődleges LLM modell (alapértelmezett: "gemini-2.5-flash")
  model_fallback: "gemini-2.5-pro"          # Tartalék modell, ha az elsődleges nem elérhető (null = nincs)

  # ── Utasítás ────────────────────────────────────────
  instruction: "prompts/system_prompt.md"   # Inline szöveg VAGY relatív útvonal .md fájlhoz
                                            # Ha .md-re végződik → fájlként tölti be az ágens könyvtárából

  # ── Kimenet ─────────────────────────────────────────
  output_key: "agent_neve_output"           # Kimenet kulcs a session state-ben
                                            # Alapértelmezett: "{name}_output"

  # ── Képességek ──────────────────────────────────────
  capabilities:                             # Képesség címkék listája
    - "calendar_management"                 # Flow-kban skill alapú ágens kiválasztáshoz használható
    - "event_scheduling"

  # ── LLM generálási konfig ──────────────────────────
  generate_content_config:
    thinking: true                          # Extended thinking mód engedélyezése (alapértelmezett: false)

  # ── Eszközök ────────────────────────────────────────
  tools:
    mcp: []                                 # MCP szerver kapcsolatok listája (lásd 5. fejezet)
    builtin: []                             # Beépített eszközök listája (lásd 4.3)

  # ── Ágens-transzfer szabályozás ─────────────────────
  disallow_transfer_to_peers: false         # true = nem delegálhat más ágenseknek
  disallow_transfer_to_parent: false        # true = nem adhat vissza feladatot a root ágensnek

  # ── A2A kiajánlás ─────────────────────────────────
  expose: false                             # true = A2A végpontként elérhető (/a2a/agents/{name}/)
```

### 4.2 Mezők részletes leírása

| Mező | Típus | Alapértelmezett | Leírás |
|------|-------|-----------------|--------|
| `name` | string | **kötelező** | Egyedi ágens azonosító. Betűk, számok, alulvonás. |
| `version` | string | `"0.1.0"` | Szemantikus verziószám |
| `description` | string | `""` | Emberileg olvasható leírás — a root ágens az `{{ agents_desc }}` template-ben használja |
| `category` | string | `"general"` | Kategória címke |
| `model` | string | `"gemini-2.5-flash"` | LLM modell ID (a `config/llm_providers.yaml`-ben definiált modellek valamelyike) |
| `model_fallback` | string\|null | `null` | Tartalék modell, ha az elsődleges nem elérhető |
| `instruction` | string | `""` | Ágens utasítás — inline szöveg, vagy relatív útvonal egy `.md` fájlhoz |
| `output_key` | string\|null | `null` | Kimenet kulcs (alapért.: `"{name}_output"`) |
| `capabilities` | list[string] | `[]` | Képesség címkék — flow-kban `required_skill`/`required_capabilities` szűrőkkel használható |
| `generate_content_config.thinking` | bool | `false` | Extended thinking mód (mélyebb gondolkodás a válaszadás előtt) |
| `tools.mcp` | list | `[]` | MCP szerver kapcsolatok (lásd 5. fejezet) |
| `tools.builtin` | list[string] | `[]` | Beépített eszközök nevei |
| `disallow_transfer_to_peers` | bool | `false` | Tiltja a peer ágensekhez delegálást |
| `disallow_transfer_to_parent` | bool | `false` | Tiltja a szülő (root) ágenshez visszaadást |
| `expose` | bool | `false` | A2A végpontként kiajánlás (`/a2a/agents/{name}/`) |

### 4.3 Beépített eszközök (builtin)

| Eszköz neve | Leírás |
|-------------|--------|
| `ask_user` | Kérdést tesz fel a felhasználónak és megvárja a választ (task kontextusban) |
| `send_notification` | Értesítést küld a felhasználónak (nem blokkoló) |
| `list_channels` | Elérhető kommunikációs csatornák listázása |
| `exit_loop` | Kilépés az orkesztrációs ciklusból (a root ágens használja a feladat lezárásához) |

### 4.4 Ágens könyvtár felépítése

```
projects/<projekt>/agents/<agent_name>/
├── agent.yaml                  # KÖTELEZŐ — ágens konfiguráció
├── prompts/
│   └── system_prompt.md        # Ágens viselkedési utasítás (az instruction mezőből hivatkozva)
└── tools/                      # Opcionális
    └── mcp_server.py           # MCP protokollú helyi eszközszerver
```

### 4.5 Példa: Minimális ágens

```yaml
agent:
  name: "simple_agent"
  description: "Egyszerű segéd ágens"
  model: "gemini-2.5-flash"
  instruction: |
    Te egy segítőkész asszisztens vagy. Válaszolj röviden és pontosan.
  tools:
    mcp: []
    builtin: []
```

### 4.6 Példa: Teljes ágens MCP eszközzel

```yaml
agent:
  name: "calendar_agent"
  version: "0.1.0"
  description: "Calendar management - events, scheduling, availability, conflict detection"
  category: "personal_assistant"
  model: "gemini-2.5-flash"
  model_fallback: "gemini-2.5-pro"
  instruction: "prompts/system_prompt.md"
  output_key: "calendar_agent_output"
  capabilities:
    - "calendar_management"
    - "event_scheduling"
    - "availability_check"
    - "conflict_detection"
  generate_content_config:
    thinking: true
  tools:
    mcp:
      - transport: "stdio"
        server: "tools/mcp_server.py"
    builtin:
      - "send_notification"
```

### 4.7 Példa: Ágens felhasználói interakcióval

```yaml
agent:
  name: "user_agent"
  version: "0.1.0"
  description: "Handles direct human interaction - asks the user for clarification"
  category: "interaction"
  model: "gemini-2.5-flash"
  instruction: "prompts/system_prompt.md"
  output_key: "user_agent_output"
  capabilities:
    - "user_interaction"
    - "clarification"
  generate_content_config:
    thinking: false
  tools:
    mcp: []
    builtin:
      - "ask_user"
```

---

## 5. MCP eszköz konfiguráció referencia

Az MCP (Model Context Protocol) eszközök biztosítják az ágensek számára a külvilággal való kommunikációt. Három szállítási mód (transport) támogatott.

### 5.1 Teljes séma

```yaml
tools:
  mcp:
    - # ── Transport ────────────────────────────────────
      transport: "stdio"              # "stdio" | "sse" | "streamable_http"
                                      # Alapértelmezett: "stdio"

      # ── STDIO — egyszerű mód (Python MCP szerver) ──
      server: "tools/mcp_server.py"   # Relatív útvonal az ágens könyvtárától
      workspace: "{{ workspace_dir }}" # Munkaterület útvonal (template változó)

      # ── STDIO — haladó mód (tetszőleges parancs) ───
      command: "npx"                  # Futtatandó parancs
      args:                           # Parancssori argumentumok (template-ek támogatottak)
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "{{ workspace_dir }}"
      env:                            # Extra környezeti változók
        NODE_ENV: "production"

      # ── SSE / Streamable HTTP ──────────────────────
      url: "http://localhost:3001/sse" # Szerver URL
      headers:                         # HTTP fejlécek (pl. autentikáció)
        Authorization: "Bearer {{ env.MCP_TOKEN }}"

      # ── Időtúllépések ─────────────────────────────
      timeout: 5.0                    # Kapcsolódási timeout (másodperc, alapért.: 5.0)
      sse_read_timeout: 300.0         # SSE olvasási timeout (másodperc, alapért.: 300.0)

      # ── Eszköz szűrés ─────────────────────────────
      tool_filter:                    # Csak ezeket az eszközöket teszi elérhetővé
        - "read_file"                 # Ha null → az összes eszköz elérhető
        - "write_file"
```

### 5.2 Transport típusok

#### STDIO — Egyszerű mód (Python MCP szerver)

A leggyakoribb mód. Egy Python szkriptet futtat MCP szerverként, amely az ágens könyvtárában található.

```yaml
tools:
  mcp:
    - transport: "stdio"
      server: "tools/mcp_server.py"
```

- A `server` útvonal relatív az ágens könyvtárához képest
- A rendszer az aktuális Python interpreterrel futtatja
- A `workspace` paraméterrel átadható a munkaterület útvonal

#### STDIO — Haladó mód (tetszőleges parancs)

Tetszőleges parancssori eszközt futtat MCP szerverként (pl. npx, node, uvx).

```yaml
tools:
  mcp:
    - transport: "stdio"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "{{ workspace_dir }}"
      env:
        NODE_ENV: "production"
```

- A `command` mező a futtatandó parancs
- Az `args` lista a parancssori argumentumok
- Az `env` dict extra környezeti változókat ad hozzá

#### SSE (Server-Sent Events)

Távoli MCP szerverhez csatlakozik SSE protokollon.

```yaml
tools:
  mcp:
    - transport: "sse"
      url: "http://mcp-server:3001/sse"
      headers:
        Authorization: "Bearer {{ env.MCP_API_KEY }}"
      timeout: 10.0
      sse_read_timeout: 600.0
```

#### Streamable HTTP

Távoli MCP szerverhez csatlakozik HTTP streaming protokollon.

```yaml
tools:
  mcp:
    - transport: "streamable_http"
      url: "http://mcp-server:3001/stream"
      headers:
        X-API-Key: "{{ env.MCP_API_KEY }}"
```

### 5.3 Mezők részletes leírása

| Mező | Típus | Alapértelmezett | Transport | Leírás |
|------|-------|-----------------|-----------|--------|
| `transport` | string | `"stdio"` | mind | Szállítási mód: `"stdio"`, `"sse"`, `"streamable_http"` |
| `server` | string\|null | `null` | stdio | Relatív útvonal a Python MCP szerver szkripthez |
| `workspace` | string\|null | `null` | stdio | Munkaterület útvonal (template: `{{ workspace_dir }}`) |
| `command` | string\|null | `null` | stdio | Futtatandó parancs (haladó mód) |
| `args` | list[string] | `[]` | stdio | Parancssori argumentumok |
| `env` | dict[str,str] | `{}` | stdio | Extra környezeti változók |
| `url` | string\|null | `null` | sse, streamable_http | Szerver URL |
| `headers` | dict[str,str] | `{}` | sse, streamable_http | HTTP fejlécek |
| `timeout` | float | `5.0` | mind | Kapcsolódási timeout (másodperc) |
| `sse_read_timeout` | float | `300.0` | sse | SSE olvasási timeout (másodperc) |
| `tool_filter` | list[string]\|null | `null` | mind | Eszköznév whitelist — ha `null`, minden eszköz elérhető |

### 5.4 Template változók

A YAML értékekben Jinja2 template változók használhatók:

| Változó | Jelentés |
|---------|---------|
| `{{ workspace_dir }}` | A projekt munkaterület könyvtár útvonala |
| `{{ env.VALTOZO_NEV }}` | Környezeti változó értéke |

### 5.5 Több MCP szerver egyetlen ágensben

Egy ágens egyszerre több MCP szerverre is csatlakozhat:

```yaml
tools:
  mcp:
    - transport: "stdio"
      server: "tools/mcp_server.py"           # Saját Python eszközök
    - transport: "stdio"
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{{ workspace_dir }}"]
      tool_filter: ["read_file", "list_files"]  # Csak olvasás
    - transport: "sse"
      url: "http://remote-mcp:3001/sse"        # Távoli eszközök
  builtin:
    - "send_notification"
```

---

## 6. Root Agent YAML referencia

A root ágens az orkesztrátor, amely koordinálja a sub-ágenseket. A `projects/<projekt>/root_agents/<name>.root.yaml` fájlban definiált.

### 6.1 Teljes séma

```yaml
root_agent:
  # ── Azonosítás ──────────────────────────────────────
  name: "my_orchestrator"                   # KÖTELEZŐ — egyedi azonosító
  version: "1.0.0"                          # Szemantikus verzió (alapértelmezett: "1.0.0")
  description: "Az orkesztrátor leírása"    # Emberileg olvasható leírás

  # ── LLM konfiguráció ───────────────────────────────
  model: "gemini-2.5-flash"                 # LLM modell (alapértelmezett: "gemini-2.5-flash")

  # ── Orkesztráció ────────────────────────────────────
  orchestration:
    strategy: "loop"                        # Orkesztrációs stratégia ("loop" = LoopAgent)
    max_iterations: 15                      # Maximum iterációk száma (alapértelmezett: 10)

  # ── Sub-ágensek ─────────────────────────────────────
  sub_agents:                               # Koordinálandó ágens modulok nevei
    - "calendar_agent"                      # Meg kell egyeznie az agents/ könyvtárban lévő
    - "email_agent"                         # agent.yaml-ben definiált name mezővel
    - "task_agent"

  # ── Utasítás ────────────────────────────────────────
  instruction: |                            # Inline szöveg VAGY relatív útvonal .md fájlhoz
    Te egy orkesztrátor vagy, aki koordinálja az alábbiakat:
    {{ agents_desc }}

    A sub-ágensek kimenetei:
    {{ output_keys_desc }}

  # ── LLM generálási konfig ──────────────────────────
  generate_content_config:
    thinking: true                          # Extended thinking mód

  # ── A2A kiajánlás ─────────────────────────────────
  expose: false                             # true = A2A végpontként elérhető (/a2a/root-agents/{name}/)
```

### 6.2 Mezők részletes leírása

| Mező | Típus | Alapértelmezett | Leírás |
|------|-------|-----------------|--------|
| `name` | string | **kötelező** | Egyedi root ágens azonosító |
| `version` | string | `"1.0.0"` | Szemantikus verziószám |
| `description` | string | `""` | Emberileg olvasható leírás |
| `model` | string | `"gemini-2.5-flash"` | LLM modell ID |
| `orchestration.strategy` | string | `"loop"` | Orkesztrációs stratégia — jelenleg: `"loop"` (LoopAgent) |
| `orchestration.max_iterations` | int | `10` | Maximum orkesztrációs iterációk (ciklusszám) |
| `sub_agents` | list[string] | `[]` | Sub-ágens nevek listája (az `agents/` könyvtárban definiáltak) |
| `instruction` | string | `""` | Orkesztrátor utasítás — inline szöveg vagy .md fájl útvonal |
| `generate_content_config.thinking` | bool | `false` | Extended thinking mód |
| `expose` | bool | `false` | A2A végpontként kiajánlás (`/a2a/root-agents/{name}/`) |

### 6.3 Template változók az instrukcióban

A root ágens `instruction` mezőjében speciális template változók használhatók:

| Változó | Jelentés |
|---------|---------|
| `{{ agents_desc }}` | A sub-ágensek neveinek és leírásainak formázott listája |
| `{{ output_keys_desc }}` | A sub-ágensek output key-jeinek listája (pl. `calendar_agent_output`) |

Ezek a változók futásidőben automatikusan kitöltődnek a sub-ágens definíciók alapján.

### 6.4 Példa: Minimális root ágens

```yaml
root_agent:
  name: "my_assistant"
  description: "Egyszerű asszisztens orkesztrátor"
  model: "gemini-2.5-flash"
  sub_agents:
    - "helper_agent"
  instruction: |
    Koordináld a feladatokat a rendelkezésre álló ágensek között.
    Elérhető ágensek: {{ agents_desc }}
```

### 6.5 Példa: Teljes root ágens

```yaml
root_agent:
  name: "personal_assistant"
  version: "1.0.0"
  description: "Personal assistant orchestrator"
  model: "gemini-2.5-flash"
  orchestration:
    strategy: "loop"
    max_iterations: 15
  sub_agents:
    - "calendar_agent"
    - "email_agent"
    - "document_agent"
    - "task_agent"
    - "comms_agent"
    - "research_agent"
    - "user_agent"
  instruction: |
    You are a Personal Assistant orchestrator.
    Available agents: {{ agents_desc }}
    Output keys: {{ output_keys_desc }}

    INTENT CLASSIFICATION:
    - Calendar/schedule/meeting → calendar_agent
    - Email/inbox/message → email_agent
    - Document/file/search docs → document_agent
    - Task/todo/sprint → task_agent
    - Slack/Teams/chat → comms_agent
    - Research/look up/search web → research_agent
    - Ambiguous/needs clarification → user_agent
  generate_content_config:
    thinking: true
```

---

## 7. Flow YAML referencia

A flow-k a `projects/<projekt>/flows/<name>.flow.yaml` fájlokban definiált állapotgépek.

### 7.1 Teljes felső szintű séma

```yaml
flow:
  # ── Azonosítás ──────────────────────────────────────
  name: "flow_neve"                         # KÖTELEZŐ — egyedi azonosító
  version: "1.0.0"                          # Szemantikus verzió
  description: "A flow leírása"             # Emberileg olvasható leírás

  # ── Trigger ─────────────────────────────────────────
  trigger:
    type: "manual"                          # Trigger típus (jelenleg: "manual")
    input_schema:                           # JSON Schema — a flow várt bemenete
      type: "object"
      required: ["field1"]
      properties:
        field1:
          type: "string"
          description: "Mező leírása"
        field2:
          type: "string"

  # ── Konfiguráció ────────────────────────────────────
  config:
    max_retry_loops: 5                      # Újrapróbálkozási limit (alapértelmezett: 5)
    max_parallel_branches: 4                # Párhuzamos ágak max. száma (alapértelmezett: 4)
    timeout_minutes: 120                    # Flow timeout percben (alapértelmezett: 120)
    provider: "google"                      # LLM provider felülbírálás (opcionális)
    model: "gemini-2.5-flash"               # LLM modell felülbírálás (opcionális)
    fallback_model: "gemini-2.5-pro"        # Tartalék modell (opcionális)

  # ── A2A kiajánlás ─────────────────────────────────
  expose: false                             # true = A2A végpontként elérhető (/a2a/flows/{name}/)

  # ── Állapotok ───────────────────────────────────────
  states:
    elso_lepes:
      type: "agent_task"
      # ...
    masodik_lepes:
      type: "llm_decision"
      # ...
    vegeredmeny:
      type: "terminal"
      # ...
```

### 7.2 Config mezők

| Mező | Típus | Alapértelmezett | Leírás |
|------|-------|-----------------|--------|
| `max_retry_loops` | int | `5` | Hányszor próbálkozhat újra egy agent_task |
| `max_parallel_branches` | int | `4` | Egyidejű párhuzamos ágak maximuma |
| `timeout_minutes` | int | `120` | Az egész flow timeout-ja percben |
| `provider` | string\|null | `null` | LLM provider override (pl. `"google"`, `"anthropic"`) |
| `model` | string\|null | `null` | LLM modell override (pl. `"gemini-2.5-flash"`) |
| `fallback_model` | string\|null | `null` | Tartalék modell |

### 7.3 Node típusok

Minden állapot (state) egy node, amelynek `type` mezője határozza meg a viselkedését. Elérhető típusok:

| Típus | Leírás |
|-------|--------|
| `agent_task` | Ágens feladat delegálás |
| `llm_decision` | LLM-alapú döntés átmenetek között |
| `human_interaction` | Emberi beavatkozás kérés |
| `parallel` | Párhuzamos ág végrehajtás |
| `conditional` | Feltételes elágazás |
| `wait_for_event` | Külső eseményre várakozás |
| `trigger_flow` | Al-flow indítás |
| `terminal` | Végállapot (siker/hiba) |

#### 7.3.1 `agent_task` — Ágens feladat

Egy ágens modult bíz meg feladattal.

```yaml
generate_code:
  type: "agent_task"

  # ── Ágens kiválasztás (legalább az egyik szükséges) ─
  agent: "dev_agent"                        # Explicit ágens név
  required_skill: "coding"                  # Skill ID alapú dinamikus kiválasztás
  required_capabilities: ["python"]         # Képesség szűrők
  fallback_agent: "general_agent"           # Tartalék ágens, ha az elsődleges nem elérhető

  description: "Kód generálása"             # Leírás (logoláshoz)
  tools: ["file_write", "file_read"]        # Specifikus eszközök engedélyezése

  # ── Bemenet / Kimenet ──────────────────────────────
  input:                                    # Bemenet mapping: kulcs → template kifejezés
    requirement: "{{ trigger.task_description }}"
    context: "{{ states.previous_step.output.data }}"
  output: [source_files, summary]           # Elvárt kimeneti mezők

  # ── Végrehajtás vezérlés ───────────────────────────
  mode: null                                # Végrehajtási mód
  duration_minutes: null                    # Várható időtartam
  retry_loop: "generate_revise"             # Újrapróbálkozási ciklus neve
  condition: "{{ flow.should_generate }}"   # Feltételes végrehajtás (Jinja2)

  # ── Állapotátmenetek ───────────────────────────────
  on_complete: "next_step"                  # Siker esetén a következő állapot
  on_error: "error_handler"                 # Hiba esetén a következő állapot
  on_event: null                            # Esemény-alapú átmenet

  # ── Mellékhatás ────────────────────────────────────
  side_effect:
    set:
      flow_phase: "code_generated"          # Flow szintű változó beállítása
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `agent` | string\|null | `null` | Ágens neve (vagy `required_skill` használata) |
| `required_skill` | string\|null | `null` | Skill ID alapú ágens kiválasztás |
| `required_capabilities` | list[string] | `[]` | Képesség szűrő |
| `fallback_agent` | string\|null | `null` | Tartalék ágens |
| `description` | string | `""` | Leírás |
| `tools` | list[string] | `[]` | Engedélyezett eszközök |
| `input` | dict[str,str] | `{}` | Bemenet — kulcs: érték template |
| `output` | list[string] | `[]` | Elvárt kimeneti mező nevek |
| `retry_loop` | string\|null | `null` | Retry ciklus állapot neve |
| `condition` | string\|null | `null` | Feltételes végrehajtás (Jinja2 boolean) |
| `on_complete` | string\|null | `null` | Következő állapot siker esetén |
| `on_error` | string\|null | `null` | Következő állapot hiba esetén |
| `on_event` | string\|null | `null` | Esemény-alapú átmenet |
| `side_effect.set` | dict[str,str] | `{}` | Flow változók beállítása |

#### 7.3.2 `llm_decision` — LLM döntés

Egy LLM-et hív meg, hogy válasszon a lehetséges átmenetek közül.

```yaml
review_result:
  type: "llm_decision"

  # ── LLM konfig (opcionális — a flow config-ból örökli) ─
  provider: "google"                        # Provider felülbírálás
  model: "gemini-2.5-pro"                   # Modell felülbírálás

  # ── Kontextus és döntés ────────────────────────────
  context:                                  # Kontextus lista az LLM számára
    - "{{ states.generate_code.output }}"
    - "Original task: {{ trigger.task_description }}"
  decision_prompt: |                        # A döntési prompt
    Értékeld a generált kódot:
    - Ha jó → accept
    - Ha javítani kell → revise
    - Ha kérdés van → ask_user

  # ── Átmenetek ──────────────────────────────────────
  transitions:                              # Döntés → következő állapot mapping
    accept: "complete_success"
    revise: "generate_code"
    ask_user: "ask_user_input"

  # ── Mellékhatás ────────────────────────────────────
  side_effect:
    set:
      review_decision: "{{ decision }}"
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `provider` | string\|null | `null` | LLM provider override |
| `model` | string\|null | `null` | LLM modell override |
| `context` | list[string] | `[]` | Kontextus adatok listája (template kifejezések) |
| `decision_prompt` | string | `""` | Döntési prompt — az LLM a `transitions` kulcsai közül választ |
| `transitions` | dict[str,str] | `{}` | Döntés → állapot mapping |
| `side_effect.set` | dict[str,str] | `{}` | Flow változók beállítása |

#### 7.3.3 `human_interaction` — Emberi beavatkozás

Megállítja a flow-t és a felhasználótól vár választ.

```yaml
ask_user_input:
  type: "human_interaction"

  # ── Interakció típus ───────────────────────────────
  interaction_type: "free_text"             # "free_text" | "choice" | "multi_question"

  # ── Megjelenítés ───────────────────────────────────
  prompt: "Kérjük, adjon meg további részleteket."
  context: "Az ágens az alábbi kérdéseket tette fel..."

  # ── Choice típushoz ────────────────────────────────
  options:
    - id: "option_a"
      label: "A lehetőség"
    - id: "option_b"
      label: "B lehetőség"

  # ── Multi-question típushoz ────────────────────────
  questions:                                # Inline lista VAGY template hivatkozás
    - id: "q1"
      text: "Mi a projekt neve?"
      question_type: "free_text"            # "free_text" | "choice"
      required: true
    - id: "q2"
      text: "Válasszon nyelvet:"
      question_type: "choice"
      options:
        - id: "python"
          label: "Python"
        - id: "typescript"
          label: "TypeScript"
      required: true

  # ── Fájl feltöltés ────────────────────────────────
  file_upload: null                         # Fájl feltöltés konfig (opcionális)

  # ── Timeout ────────────────────────────────────────
  timeout_seconds: null                     # Válasz timeout (null = végtelen)
  default_value: null                       # Alapértelmezett érték timeout esetén

  # ── Átmenetek ──────────────────────────────────────
  on_response: "next_step"                  # Következő állapot válasz esetén
  on_timeout: "timeout_handler"             # Következő állapot timeout esetén
  transitions:                              # Choice → állapot mapping (opcionális)
    option_a: "path_a"
    option_b: "path_b"
```

**Interakció típusok:**

| Típus | Leírás |
|-------|--------|
| `free_text` | Szabad szöveges válasz |
| `choice` | Előre megadott lehetőségek közül választás |
| `multi_question` | Több kérdés egyszerre — inline lista vagy template hivatkozás |

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `interaction_type` | string | `"free_text"` | Interakció típus |
| `prompt` | string | `""` | Kérdés/prompt szöveg |
| `context` | string\|null | `null` | További kontextus |
| `options` | list[dict] | `[]` | Választási lehetőségek (choice típushoz) |
| `questions` | list\|string | `[]` | Kérdések (multi_question típushoz) — lista vagy template |
| `file_upload` | dict\|null | `null` | Fájl feltöltés konfig |
| `timeout_seconds` | int\|null | `null` | Válasz timeout |
| `default_value` | string\|null | `null` | Alapértelmezett válasz timeout esetén |
| `on_response` | string\|null | `null` | Következő állapot válasz esetén |
| `on_timeout` | string\|null | `null` | Következő állapot timeout esetén |
| `transitions` | dict[str,str] | `{}` | Choice → állapot mapping |

#### 7.3.4 `parallel` — Párhuzamos végrehajtás

Több ágat futtat egyszerre, majd egyesíti az eredményt.

```yaml
parallel_research:
  type: "parallel"

  branches:
    web_search:
      type: "agent_task"
      agent: "research_agent"
      input:
        requirement: "Keress a webes forrásokban: {{ trigger.topic }}"
      output: [web_results]
      condition: "{{ trigger.search_web }}"  # Feltételes ág

    doc_search:
      type: "agent_task"
      agent: "document_agent"
      input:
        requirement: "Keress a belső dokumentumokban: {{ trigger.topic }}"
      output: [doc_results]

  join: "all"                               # "all" = mindegyik végezzen | "any" = elég egy
  on_complete: "merge_results"              # Következő állapot a join után
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `branches` | dict[str, ParallelBranch] | `{}` | Párhuzamos ágak — kulcs: ág neve |
| `branches.*.type` | string | — | Ág típusa (általában `"agent_task"`) |
| `branches.*.agent` | string | `""` | Ágens neve |
| `branches.*.tools` | list[string] | `[]` | Engedélyezett eszközök |
| `branches.*.input` | dict[str,str] | `{}` | Bemenet mapping |
| `branches.*.output` | list[string] | `[]` | Kimeneti mező nevek |
| `branches.*.condition` | string\|null | `null` | Feltételes végrehajtás |
| `join` | string | `"all"` | Join stratégia: `"all"` (mind kész) \| `"any"` (elég egy) |
| `on_complete` | string\|null | `null` | Következő állapot join után |

#### 7.3.5 `conditional` — Feltételes elágazás

Boolean feltétel alapján választ két állapot között.

```yaml
check_quality:
  type: "conditional"
  condition: "{{ states.review.output.score > 80 }}"
  if_true: "deploy"
  if_false: "revise"
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `condition` | string | `""` | Jinja2 boolean kifejezés |
| `if_true` | string | `""` | Következő állapot, ha igaz |
| `if_false` | string | `""` | Következő állapot, ha hamis |

#### 7.3.6 `wait_for_event` — Eseményre várakozás

Külső eseményre vár megadott timeouttal.

```yaml
wait_for_approval:
  type: "wait_for_event"
  event_source: "approval_system"
  event_type: "approval_response"
  timeout_minutes: 60
  on_event: "process_approval"
  on_timeout: "auto_reject"
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `event_source` | string | `""` | Eseményforrás azonosító |
| `event_type` | string | `""` | Várt esemény típus |
| `timeout_minutes` | int | `60` | Timeout percben |
| `on_event` | string | `""` | Következő állapot esemény beérkezésekor |
| `on_timeout` | string | `""` | Következő állapot timeout esetén |

#### 7.3.7 `trigger_flow` — Alflow indítás

Egy másik flow-t indít el al-munkafolyamatként.

```yaml
run_sub_flow:
  type: "trigger_flow"
  flow_name: "validation_flow"
  input:
    data: "{{ states.generate.output.result }}"
  on_complete: "check_validation"
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `flow_name` | string | `""` | Az indítandó flow neve |
| `input` | dict[str,str] | `{}` | Bemenet az al-flow számára |
| `on_complete` | string | `""` | Következő állapot az al-flow befejezése után |

#### 7.3.8 `terminal` — Végállapot

Lezárja a flow-t sikerrel vagy hibával.

```yaml
complete_success:
  type: "terminal"
  status: "success"                         # "success" | "failed"
  output:
    result: "{{ states.generate_code.output }}"
    cost: "{{ flow.cost_report }}"

handle_error:
  type: "terminal"
  status: "failed"
  output:
    error: "{{ error }}"
```

**Mezők:**

| Mező | Típus | Alapért. | Leírás |
|------|-------|----------|--------|
| `status` | string | `"success"` | Végállapot: `"success"` \| `"failed"` |
| `output` | dict[str,str] | `{}` | Kimeneti adatok (template kifejezések) |

### 7.4 Template kifejezések (Jinja2)

A flow node-ok közötti adatáramlást template kifejezések biztosítják `{{ ... }}` szintaxissal:

| Kifejezés | Jelentés |
|-----------|---------|
| `{{ trigger.field }}` | A flow induló bemenetének egy mezője |
| `{{ states.step_name.output }}` | Egy korábbi lépés teljes kimenete |
| `{{ states.step_name.output.field }}` | Kimenet egy adott mezője |
| `{{ flow.variable }}` | Flow szintű változó (`side_effect.set`-tel állítható) |
| `{{ flow.cost_report }}` | Automatikus költségjelentés |
| `{{ error }}` | Hiba üzenet (`on_error` ágban elérhető) |
| `{{ value \| default('fallback') }}` | Alapértelmezett érték szűrő |
| `{{ value if condition else other }}` | Inline feltétel |

### 7.5 Újrapróbálkozás (retry)

Az `agent_task` node-ok `retry_loop` paramétere megadja, melyik állapotra ugorjon vissza újrapróbálkozás esetén. A `config.max_retry_loops` határozza meg a maximális próbálkozások számát.

```yaml
config:
  max_retry_loops: 3

states:
  generate_code:
    type: "agent_task"
    agent: "dev_agent"
    retry_loop: "generate_revise"      # Erre az állapotra ugrik vissza retry esetén
    on_complete: "review"
    on_error: "handle_error"
```

### 7.6 Flow életciklus

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

### 7.7 Példa: Komplett flow ágens delegálással és emberi interakcióval

```yaml
flow:
  name: "simple_code_task"
  version: "1.0.0"
  description: "Felhasználó kód feladatot küld, az ágens megoldja"

  trigger:
    type: "manual"
    input_schema:
      type: "object"
      required: ["task_description"]
      properties:
        task_description:
          type: "string"

  config:
    max_retry_loops: 3
    timeout_minutes: 30
    provider: "google"
    model: "gemini-2.5-flash"

  states:
    generate_code:
      type: "agent_task"
      agent: "dev_agent"
      description: "Kód generálása a feladatleírásból"
      retry_loop: "generate_revise"
      input:
        requirement: "{{ trigger.task_description }}"
        user_feedback: "{{ states.ask_user_input.output.response | default('') }}"
      output: [source_files, summary, agent_questions]
      on_complete: "review_result"
      on_error: "handle_error"

    review_result:
      type: "llm_decision"
      context:
        - "{{ states.generate_code.output }}"
      decision_prompt: |
        Értékeld az ágens kimenetét:
        - Ha kérdés van (agent_questions nem üres) → ask_user
        - Ha a kód kész és helyes → accept
        - Ha javítani kell → revise
      transitions:
        accept: "complete_success"
        revise: "generate_code"
        ask_user: "ask_user_input"

    ask_user_input:
      type: "human_interaction"
      interaction_type: "multi_question"
      prompt: "{{ states.review_result.output.reason | default('Az ágensnek kérdései vannak.') }}"
      questions: "{{ states.review_result.output.questions | default('') }}"
      on_response: "generate_code"

    handle_error:
      type: "terminal"
      status: "failed"
      output:
        error: "{{ error }}"

    complete_success:
      type: "terminal"
      status: "success"
      output:
        result: "{{ states.generate_code.output }}"
        cost: "{{ flow.cost_report }}"
```

### 7.8 Példa: Szekvenciális multi-ágens flow

```yaml
flow:
  name: "meeting_prep"
  version: "1.0.0"
  description: "Meeting brief készítés — naptár, kutatás, dokumentumok, emailek"

  trigger:
    type: "manual"
    input_schema:
      type: "object"
      required: ["target_date"]
      properties:
        target_date:
          type: "string"
          description: "Dátum ISO formátumban (pl. 2026-03-13)"

  config:
    max_retry_loops: 3
    timeout_minutes: 30

  states:
    fetch_calendar:
      type: "agent_task"
      agent: "calendar_agent"
      input:
        requirement: "List all events for {{ trigger.target_date }}"
      output: [events_list, event_count]
      on_complete: "review_calendar"
      on_error: "handle_error"

    review_calendar:
      type: "llm_decision"
      context:
        - "{{ states.fetch_calendar.output }}"
      decision_prompt: |
        - If events found → research
        - If no events → no_meetings
      transitions:
        research: "research_attendees"
        no_meetings: "no_meetings"

    no_meetings:
      type: "terminal"
      status: "success"
      output:
        result: "Nincs meeting erre a napra: {{ trigger.target_date }}"

    research_attendees:
      type: "agent_task"
      agent: "research_agent"
      input:
        requirement: "Kutatás a meeting résztvevőiről: {{ states.fetch_calendar.output.events_list }}"
      output: [attendee_briefs, topic_background]
      on_complete: "compile_brief"
      on_error: "compile_brief"

    compile_brief:
      type: "terminal"
      status: "success"
      output:
        result: |
          Meeting brief — {{ trigger.target_date }}:
          Naptár: {{ states.fetch_calendar.output }}
          Kutatás: {{ states.research_attendees.output | default('Nem elérhető') }}
        cost: "{{ flow.cost_report }}"

    handle_error:
      type: "terminal"
      status: "failed"
      output:
        error: "{{ error }}"
```

---

## 8. LLM Provider YAML referencia

A `config/llm_providers.yaml` fájl definiálja az elérhető LLM szolgáltatókat és modelleket.

### 8.1 Teljes séma

```yaml
# ── Alapértelmezések ──────────────────────────────────
defaults:
  provider: "google"                        # Alapértelmezett LLM provider
  model: "gemini-2.5-flash"                 # Alapértelmezett modell
  fallback_model: "gemini-2.5-pro"          # Tartalék modell

# ── Providerek ────────────────────────────────────────
providers:
  <provider_id>:                            # Provider azonosító (pl. "google", "anthropic", "openai")
    display_name: "Provider Neve"           # Megjelenítési név a felületen
    api_key_env: "API_KEY_ENV_VARIABLE"     # Környezeti változó neve az API kulcshoz
    models:
      <model_id>:                           # Modell azonosító (pl. "gemini-2.5-flash")
        display_name: "Modell Neve"         # Megjelenítési név
        pricing:
          input_per_token: 0.00000015       # Költség per input token (USD)
          output_per_token: 0.0000006       # Költség per output token (USD)
        max_tokens: 65536                   # Maximum token szám
```

### 8.2 Példa: Teljes konfiguráció

```yaml
defaults:
  provider: google
  model: gemini-2.5-flash
  fallback_model: gemini-2.5-pro

providers:
  google:
    display_name: "Google Gemini"
    api_key_env: "GOOGLE_API_KEY"
    models:
      gemini-2.5-flash:
        display_name: "Gemini 2.5 Flash"
        pricing:
          input_per_token: 0.00000015
          output_per_token: 0.0000006
        max_tokens: 65536
      gemini-2.5-pro:
        display_name: "Gemini 2.5 Pro"
        pricing:
          input_per_token: 0.00000125
          output_per_token: 0.000005
        max_tokens: 65536

  anthropic:
    display_name: "Anthropic Claude"
    api_key_env: "ANTHROPIC_API_KEY"
    models:
      claude-sonnet-4-20250514:
        display_name: "Claude Sonnet 4"
        pricing:
          input_per_token: 0.000003
          output_per_token: 0.000015
        max_tokens: 8192

  openai:
    display_name: "OpenAI"
    api_key_env: "OPENAI_API_KEY"
    models:
      gpt-4o:
        display_name: "GPT-4o"
        pricing:
          input_per_token: 0.0000025
          output_per_token: 0.00001
        max_tokens: 4096
```

### 8.3 Új provider hozzáadása

Bővítse a `providers` szekciót egy új blokkkal:

```yaml
providers:
  # ... meglévő providerek ...

  my_provider:
    display_name: "My LLM Provider"
    api_key_env: "MY_PROVIDER_API_KEY"
    models:
      my-model-v1:
        display_name: "My Model V1"
        pricing:
          input_per_token: 0.000001
          output_per_token: 0.000005
        max_tokens: 32768
```

Állítsa be az API kulcsot a `.env` fájlban:

```env
MY_PROVIDER_API_KEY=your-api-key-here
```

---

## 9. Felhasználói felület

### 9.1 Dashboard

Az áttekintő oldal KPI kártyákat jelenít meg:

- **Total Tasks** — összes beküldött feladat száma
- **Running** — jelenleg futó feladatok
- **Active Flows** — aktív munkafolyamatok száma
- **Pending Interactions** — emberi beavatkozásra váró flow lépések
- **Total Cost** — összesített költség (USD)

### 9.2 Tasks oldal

Feladatok beküldése és nyomon követése.

**Feladat beküldése:**
1. Írja be a feladat leírását a szövegmezőbe
2. Kattintson a **Submit** gombra
3. A rendszer létrehoz egy task-ot és elindítja a feldolgozást

**Feladat követése:**
- Az idővonal (timeline) mutatja a feladat eseményeit időrendben
- Állapot badge jelzi az aktuális státuszt (submitted, running, completed, failed)
- Az ágens diagram vizualizálja az aktuális ágens hierarchiát és delegálást

### 9.3 Flows oldal

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

### 9.4 Agents oldal

Ágens definíciók böngészése és kezelése.

- Elérhető ágensek listázása (YAML konfiguráció, prompt, eszközök)
- Új ágens létrehozása a **+ New** gombbal
- Ágens szerkesztése és törlése

### 9.5 Root Agents oldal

Root orkesztrátor ágensek kezelése.

- Root ágens definíciók listázása
- Sub-agent hozzárendelések és konfiguráció megtekintése

### 9.6 Tools oldal

Az összes elérhető eszköz (MCP és beépített) böngészése.

- Eszközök listázása teljes paraméter sémával
- Szűrés ágens vagy eszköz típus alapján

### 9.7 Sessions oldal

ADK munkamenetek kezelése.

- Aktív és lezárt session-ök listázása
- Session leállítása és törlése

### 9.8 Costs oldal

Költségek részletes nyomon követése.

- **Total Spend** — teljes költés összege
- **Cost by Task** — feladatonkénti költségbontás
- **Recent Events** — utolsó költségesemények időrendben (modul, ágens, művelet típusa, összeg)

### 9.9 Trace oldal

Egyedi trace-ek részletes megtekintése.

- Span-ok hierarchikus megjelenítése
- Deep-linkek Grafana és Langfuse dashboardokra
- Elérhető a `/trace/:traceId` útvonalon (task és flow oldalakról linkelhető)

### 9.10 Navigáció

A bal oldali **Sidebar** tartalmazza a navigációs linkeket:
- Dashboard, Tasks, Flows, Agents, Root Agents, Tools, Sessions, Costs

A felső **TopBar** megjeleníti:
- Platform neve
- Aktuális összköltség (CostBadge)
- SSE kapcsolat állapotjelző (zöld/piros pont)

---

## 10. Task-ok részletesen

### 10.1 Feladat beküldése

Egy task beküldésekor a következő történik:

1. A felhasználó megadja a feladat szöveges leírását
2. A rendszer generál egy egyedi `task_id`-t
3. A root ágens megkapja a feladatot
4. A root ágens elemzi a feladatot és szükség esetén delegálja ágens-moduloknak
5. Minden lépés eseményeket generál, amelyek valós időben megjelennek

### 10.2 Root ágens és delegálás

A **root ágens** a központi orkesztrátor:

- Fogadja a felhasználói feladatokat
- Ismeri az elérhető ágens-modulokat (Agent Registry)
- Eldönti, melyik sub-ágenst hívja meg (transfer_to_*)
- Összefogja a részeredményeket

### 10.3 Task vs Flow

| Szempont | Task | Flow |
|----------|------|------|
| Definiálás | Szabad szöveges leírás | YAML fájl, előre definiált lépések |
| Végrehajtás | Root ágens dönt a lépésekről | Állapotgép, előre meghatározott útvonal |
| Rugalmasság | Magas — az LLM dönti el, mit csinál | Közepes — a YAML határozza meg a struktúrát |
| Determinizmus | Alacsony | Magas (az LLM döntési pontok kivételével) |
| Használat | Ad-hoc feladatok | Ismétlődő, strukturált munkafolyamatok |

---

## 11. Konfiguráció

### 11.1 Környezeti változók

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

### 11.2 Teljes könyvtárstruktúra

```
agentic-adk-a2a-platform/
├── backend/                          # FastAPI backend
│   ├── src/
│   │   ├── main.py                   # Alkalmazás belépési pont
│   │   ├── config.py                 # Beállítások (Pydantic Settings)
│   │   ├── routers/                  # API route-ok
│   │   ├── features/
│   │   │   ├── flows/engine/         # Flow állapotgép motor
│   │   │   │   ├── engine.py         # Fő végrehajtó
│   │   │   │   ├── context.py        # Futási kontextus
│   │   │   │   ├── parallel.py       # Párhuzamos végrehajtás
│   │   │   │   ├── retry_manager.py  # Újrapróbálkozás
│   │   │   │   ├── node_handlers/    # Node típus kezelők
│   │   │   │   └── dsl/              # YAML DSL parser + schema
│   │   │   └── tasks/
│   │   │       └── executor.py       # Task végrehajtó
│   │   └── shared/
│   │       ├── a2a/                  # A2A Gateway (expose → A2A endpoint)
│   │       ├── agents/               # Ágens factory + loader
│   │       ├── cost/                 # Költségkövetés
│   │       ├── events/               # Event bus
│   │       ├── interactions/         # Interakció kezelés
│   │       ├── llm/                  # LLM provider konfiguráció
│   │       └── tracing/              # OpenTelemetry integráció
│   └── tests/
│
├── frontend/                         # React + Vite frontend
│   └── src/
│       ├── features/                 # Oldalak (dashboard, tasks, flows, ...)
│       └── shared/                   # Layout, hooks, komponensek
│
├── projects/                         # Multi-projekt ágensek
│   └── personal_assistant/
│       ├── agents/                   # Ágens definíciók
│       ├── root_agents/              # Root ágens YAML-ek
│       └── flows/                    # Flow YAML-ek
│
├── infra/                            # Observability infrastruktúra
│   ├── prometheus/prometheus.yml
│   ├── grafana/
│   └── tempo/tempo.yaml
│
├── config/
│   └── llm_providers.yaml            # LLM provider konfiguráció
│
├── workspace/                        # Ágens munkaterület
├── docker-compose.yaml               # Fő compose
├── docker-compose.prod.yaml          # Éles konfiguráció
├── .env / .env.example               # Környezeti változók
└── Makefile                          # Build automatizáció
```

---

## 12. Indítás

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
| A2A Discovery | http://localhost:8000/.well-known/agents.json |
| A2A Catalog | http://localhost:8000/a2a/catalog |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Tempo (query) | http://localhost:3200 |
| Langfuse | http://localhost:3001 |

---

## 13. API végpontok

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

### A2A Protocol

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| GET | `/.well-known/agents.json` | Kiajánlott agent card URL-ek listája |
| GET | `/a2a/catalog` | Kiajánlott A2A endpointok katalógusa (agent card-okkal) |
| GET | `/a2a/agents/{name}/.well-known/agent-card.json` | Ágens agent card |
| GET | `/a2a/root-agents/{name}/.well-known/agent-card.json` | Root ágens agent card |
| GET | `/a2a/flows/{name}/.well-known/agent-card.json` | Flow agent card |
| POST | `/a2a/{kind}/{name}/` | A2A JSON-RPC 2.0 endpoint (`tasks/send`, `tasks/sendSubscribe`) |

---

## 14. Gyors referencia — Projekt létrehozás lépésről lépésre

### 1. Projekt könyvtár létrehozása

```
projects/my_project/
├── agents/
├── root_agents/
└── flows/
```

### 2. Ágens(ek) definiálása

`projects/my_project/agents/my_agent/agent.yaml`:

```yaml
agent:
  name: "my_agent"
  description: "Az ágens feladata"
  model: "gemini-2.5-flash"
  instruction: "prompts/system_prompt.md"
  capabilities:
    - "my_skill"
  tools:
    mcp:
      - transport: "stdio"
        server: "tools/mcp_server.py"
    builtin:
      - "send_notification"
  expose: true                            # A2A-n keresztül elérhető (opcionális)
```

`projects/my_project/agents/my_agent/prompts/system_prompt.md`:

```markdown
Te egy specializált ágens vagy. A feladatod: ...
```

### 3. Root ágens definiálása

`projects/my_project/root_agents/my_project.root.yaml`:

```yaml
root_agent:
  name: "my_project"
  description: "Projekt orkesztrátor"
  model: "gemini-2.5-flash"
  orchestration:
    strategy: "loop"
    max_iterations: 10
  sub_agents:
    - "my_agent"
  instruction: |
    Koordináld a feladatokat. Elérhető ágensek:
    {{ agents_desc }}
  generate_content_config:
    thinking: true
  expose: true                            # A2A-n keresztül elérhető (opcionális)
```

### 4. Flow definiálása (opcionális)

`projects/my_project/flows/my_flow.flow.yaml`:

```yaml
flow:
  name: "my_flow"
  description: "Egyszerű munkafolyamat"
  trigger:
    type: "manual"
    input_schema:
      type: "object"
      required: ["input_text"]
      properties:
        input_text:
          type: "string"
  config:
    max_retry_loops: 3
    timeout_minutes: 30
  expose: true                            # A2A-n keresztül elérhető (opcionális)
  states:
    process:
      type: "agent_task"
      agent: "my_agent"
      input:
        requirement: "{{ trigger.input_text }}"
      output: [result]
      on_complete: "done"
      on_error: "error"
    done:
      type: "terminal"
      status: "success"
      output:
        result: "{{ states.process.output }}"
    error:
      type: "terminal"
      status: "failed"
      output:
        error: "{{ error }}"
```

### 5. Aktiválás

```env
# .env
APP_PROJECT=my_project
```

Indítás után az ágensek, root ágens és flow-k automatikusan betöltődnek és elérhetővé válnak a felületen.
