# Ágens Keretrendszer Specifikáció

## Moduláris Multi-Ágens Platform — Google ADK, A2A & MCP alapokon

**Verzió:** 0.2.0-draft  
**Dátum:** 2026-03-03  
**Státusz:** Tervezési fázis

---

## 1. Vezetői összefoglaló

Ez a dokumentum egy moduláris, multi-ágens keretrendszer specifikációját tartalmazza, amely a Google Agent Development Kit (ADK) platformra épül, és az Agent-to-Agent (A2A) valamint a Model Context Protocol (MCP) nyílt protokollokat használja. A rendszer célja, hogy AI ágenseket modulárisan lehessen fejleszteni, telepíteni és üzemeltetni — akár elosztott, multi-cloud környezetben is — miközben minden művelet költsége és teljesítménye granulárisan mérhető, a felhasználó pedig valós időben követheti a feladatok állapotát.

A keretrendszer képességeit egyetlen, végig vezetett példán mutatjuk be: egy **autonóm szoftverrendszer-építő és -üzemeltető ágens-hálózat**, amely üzleti igényből kiindulva megtervezi, megépíti, teszteli, telepíti, majd folyamatosan felügyeli és önállóan javítja a rendszert.

---

## 2. Alapelvek és tervezési filozófia

### 2.1 Modularitás elsőként
Minden ágens és eszköz önálló, telepíthető modul. A modulok lazán csatoltak, protokollokon keresztül kommunikálnak — soha nem közvetlen függőségeken.

### 2.2 Protokoll-vezérelt architektúra
- **MCP** = ágens ↔ eszköz kommunikáció (tools, resources, prompts)
- **A2A** = ágens ↔ ágens kommunikáció (feladat-delegálás, együttműködés)

### 2.3 Átláthatóság
A felhasználó minden pillanatban látja, mi történik: melyik ágens dolgozik, milyen eszközt használ, mire vár, mennyibe kerül.

### 2.4 Költségtudatosság
Minden LLM hívás, eszközhasználat és ágens-interakció mérhető és riportálható — token szinttől az aggregált feladat-szintig.

### 2.5 Teljes életciklus
Az ágensek nem egyszeri feladatot végeznek, hanem a rendszer teljes életciklusát lefedik: tervezés → fejlesztés → build → teszt → telepítés → felügyelet → hibajavítás → újratelepítés → ...

---

## 3. Architektúra áttekintés

### 3.1 Rendszerkomponensek

```
┌─────────────────────────────────────────────────────────┐
│                    FELHASZNÁLÓI RÉTEG                    │
│         (Dinamikus, widget-alapú felület)                │
│  ┌───────────────────────────────────────────────────┐  │
│  │  • YAML-ből konfigurált oldalak és menü           │  │
│  │  • Ágens/eszköz widgetek (modulonként fejlesztett)│  │
│  │  • Valós idejű stream (SSE/WebSocket)             │  │
│  │  • Interaktív kérdés-válasz overlay               │  │
│  │  • Költség dashboard                              │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │ A2A (JSON-RPC / SSE / gRPC)
┌─────────────────────▼───────────────────────────────────┐
│                ORCHESTRÁTOR RÉTEG                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Flow Engine + Root Agent (ADK)                 │    │
│  │  • YAML DSL flow definíciók                     │    │
│  │  • Eseményvezérelt reaktív állapotgép           │    │
│  │  • LLM döntési pontok                           │    │
│  │  • Agent Card registry                          │    │
│  │  • Cost Tracker middleware                      │    │
│  └──────┬──────────────┬───────────────┬───────────┘    │
│         │ A2A          │ A2A           │ A2A            │
│  ┌──────▼─────┐ ┌──────▼──────┐ ┌─────▼──────────┐    │
│  │  Modul A   │ │  Modul B    │ │  Modul C       │    │
│  │ (Agent+MCP)│ │ (Agent+MCP) │ │ (csak Agent)   │    │
│  └──────┬─────┘ └──────┬──────┘ └─────┬──────────┘    │
│         │ MCP          │ MCP          │ MCP (remote)   │
│  ┌──────▼─────┐ ┌──────▼──────┐ ┌─────▼──────────┐    │
│  │ Helyi MCP  │ │ Helyi MCP   │ │ Távoli MCP     │    │
│  │ Server(ek) │ │ Server(ek)  │ │ Server (cloud) │    │
│  └────────────┘ └─────────────┘ └────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Közös Eszköz Pool (Shared MCP Tool Registry)   │    │
│  │  • Ágens-független eszközök                     │    │
│  │  • Bármely ágens elérheti MCP-n keresztül       │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              INFRASTRUKTÚRA RÉTEG                        │
│  • Google Cloud (Vertex AI, Cloud Run, GKE)             │
│  • Távoli MCP szerverek (AWS, Azure, on-prem)           │
│  • Telemetria (OpenTelemetry → riportok)                │
│  • Secret management, Auth (OAuth 2.1)                  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Modul-típusok mátrix

| Típus | Ágens | Saját MCP eszközök | Külső MCP használat | Példa |
|-------|-------|--------------------|---------------------|-------|
| **Teljes modul** | ✅ | ✅ | ✅ | Dokumentum-elemző modul saját parser eszközzel |
| **Eszköz nélküli ágens** | ✅ | ❌ | ✅ | Döntéshozó ágens, amely távoli MCP eszközöket hív |
| **Ágens nélküli eszköz** | ❌ | ✅ (közös pool) | – | PDF konverter, képfeldolgozó, DB connector |
| **Tiszta A2A proxy** | ✅ | ❌ | ❌ | Más rendszer A2A ágensét közvetítő adapter |

---

## 4. Modul specifikáció

### 4.1 Modul struktúra

Minden modul egy önálló, telepíthető egység a következő könyvtárstruktúrával:

```
modules/
└── <module_name>/                    # Modul gyökér
    ├── module.yaml                   # Modul manifest (metaadatok)
    ├── agent/
    │   ├── agent.py                  # ADK Agent definíció
    │   ├── agent_card.json           # A2A Agent Card
    │   └── prompts/
    │       └── system_prompt.md      # Rendszer prompt
    ├── tools/
    │   ├── mcp_server.py             # Helyi MCP szerver
    │   ├── tool_definitions.py       # Eszköz definíciók
    │   └── schemas/
    │       └── input_output.json     # JSON sémák
    ├── ui/                           # UI réteg
    │   ├── widgets.yaml              # Widget manifest
    │   └── <widget_name>/
    │       ├── Widget.tsx            # React komponens
    │       ├── useHooks.ts           # Custom hook-ok
    │       └── styles.module.css
    ├── config/
    │   ├── default.yaml              # Alapértelmezett konfiguráció
    │   └── cost_config.yaml          # LLM költség konfiguráció
    ├── tests/
    ├── Dockerfile
    └── README.md
```

### 4.2 Modul Manifest (`module.yaml`)

```yaml
module:
  name: "coder_agent"
  version: "1.2.0"
  description: "Kód generálása és módosítása terv vagy diagnózis alapján"
  category: "development"

agent:
  enabled: true
  model: "gemini-2.0-flash"
  model_fallback: "gemini-1.5-pro"
  max_tokens: 8192
  mode: "on_demand"                   # on_demand | persistent
  capabilities:
    - "code_generation"
    - "code_modification"
    - "hotfix_creation"
  supported_modalities:
    input: ["text", "application/json"]
    output: ["text", "application/json"]
  human_interaction:
    enabled: true
    interaction_types:
      - "confirmation"
      - "selection"
      - "file_upload"
      - "free_text"

tools:
  local:
    - name: "code_generator"
      description: "Kód generálás (scaffolding)"
      transport: "stdio"
    - name: "snippet_library"
      description: "Kód részletek könyvtára"
      transport: "stdio"
  remote:
    - ref: "source_repo_manager"

dependencies:
  shared_tools:
    - "shared/file_manager"

deployment:
  type: "cloud_run"
  region: "europe-west1"
  scaling:
    min_instances: 0
    max_instances: 5

cost_tracking:
  enabled: true
  budget_alert_threshold_usd: 10.0
```

### 4.3 Agent Card (A2A Discovery)

```json
{
  "name": "coder_agent",
  "description": "Kód generálása, módosítása és hotfix készítése",
  "version": "1.2.0",
  "url": "https://coder-agent.europe-west1.run.app",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "generate_code",
      "name": "Kód generálás",
      "description": "Rendszerterv alapján forráskód generálása"
    },
    {
      "id": "create_hotfix",
      "name": "Hotfix készítés",
      "description": "Diagnózis alapján célzott javítókód készítése"
    }
  ],
  "authentication": {
    "schemes": ["oauth2"]
  }
}
```

---

## 5. Felhasználói felület — Valós idejű interakció

### 5.1 Feladat életciklus és állapotkezelés

A rendszer az A2A Task életciklust követi, kiegészítve egyedi állapotokkal:

```
                    ┌──────────┐
                    │SUBMITTED │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
              ┌─────│ WORKING  │─────┐
              │     └────┬─────┘     │
              │          │           │
     ┌────────▼───┐ ┌───▼────┐ ┌───▼──────────┐
     │  THINKING  │ │TOOL_USE│ │INPUT_REQUIRED │
     │ (gondolko- │ │(eszköz │ │(felhasználói  │
     │  dás fázis)│ │ hívás) │ │ input kell)   │
     └────────┬───┘ └───┬────┘ └───┬──────────┘
              │          │          │
              └──────────┼──────────┘
                         │
                  ┌──────▼──────┐
                  │  COMPLETED  │
                  └──────┬──────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
        ┌─────▼──┐ ┌────▼───┐ ┌───▼────┐
        │SUCCESS │ │ FAILED │ │CANCELED│
        └────────┘ └────────┘ └────────┘
```

### 5.2 Valós idejű stream protokoll

A felület SSE vagy WebSocket kapcsolaton keresztül kap frissítéseket:

```typescript
interface TaskEvent {
  task_id: string;
  timestamp: string;
  event_type: TaskEventType;
  agent: { module: string; name: string };
  payload: ThinkingPayload | ToolUsePayload
         | InputRequiredPayload | ProgressPayload
         | ResultPayload | ErrorPayload;
  cost: IncrementalCost;
}

interface ThinkingPayload {
  type: "thinking";
  phase: string;
  summary: string;
  reasoning_steps: string[];
  confidence: number;
  next_planned_action: string;
}

interface ToolUsePayload {
  type: "tool_use";
  tool_name: string;
  tool_source: "local" | "remote" | "shared";
  mcp_server: string;
  endpoint?: string;
  status: "invoking" | "streaming" | "completed" | "failed";
  input_summary: string;
  output_summary?: string;
  duration_ms?: number;
}

interface InputRequiredPayload {
  type: "input_required";
  interaction_id: string;
  interaction_type: InteractionType;
  prompt: string;
  context: string;
  options?: InteractionOption[];
  file_requirements?: {
    accepted_types: string[];
    max_size_mb: number;
    description: string;
  };
  timeout_seconds?: number;
  default_value?: string;
}

type InteractionType =
  | "confirmation" | "single_select" | "multi_select"
  | "free_text" | "file_upload" | "parameter_adjust";
```

### 5.3 Interaktív kérdés-válasz folyamat

```
Felhasználó                 Flow Engine               Ágens (Modul)
    │                            │                         │
    │  "Építs rendszert X-re"    │                         │
    │───────────────────────────►│                         │
    │                            │──── A2A Task ─────────►│
    │  ◄── THINKING stream ─────│◄── thinking ────────────│
    │                            │                         │
    │  ◄── TOOL_USE stream ─────│◄── tool_use ────────────│
    │                            │                         │
    │  ◄── INPUT_REQUIRED ──────│◄── input_required ──────│
    │  "3 nyelv található.       │                         │
    │   Melyikre fókuszáljak?"   │                         │
    │                            │                         │
    │  válasz ─────────────────►│───── user_response ────►│
    │                            │                         │
    │  ◄── COMPLETED ───────────│◄── result ──────────────│
    │  + költség összesítő       │                         │
```

---

## 6. MCP eszközök — Helyi és távoli telepítés

### 6.1 MCP szerver típusok

| Típus | Transport | Hol fut | Példa |
|-------|-----------|---------|-------|
| **Helyi (stdio)** | stdin/stdout | Ugyanaz a konténer | PDF parser, regex eszköz |
| **Helyi (SSE)** | HTTP + SSE | Ugyanaz a hálózat | Adatbázis connector |
| **Távoli (SSE)** | HTTPS + SSE | Cloud szolgáltató | Google Drive, AWS S3 |
| **Távoli (gRPC)** | gRPC + TLS | Cloud szolgáltató | Nagy teljesítményű ML eszköz |

### 6.2 Távoli MCP telepítési sablonok

#### Google Cloud Run

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: mcp-cloudwatch-monitor
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "10"
    spec:
      containerConcurrency: 1
      containers:
        - image: europe-west1-docker.pkg.dev/PROJECT/mcp-tools/cloudwatch-monitor:latest
          ports:
            - containerPort: 8080
          env:
            - name: MCP_TRANSPORT
              value: "sse"
            - name: MCP_AUTH_TYPE
              value: "oauth2"
            - name: COST_TRACKING_ENABLED
              value: "true"
```

#### AWS Lambda

```yaml
mcp_server:
  name: "cloudwatch_log_monitor"
  runtime: "python3.12"
  transport: "sse"
  timeout: 300
  environment:
    MCP_AUTH_TYPE: "iam_role"
    COST_TRACKING_ENDPOINT: "https://telemetry.corp.example.com/cost"
```

#### On-Premise (Docker Compose)

```yaml
services:
  mcp-db-connector:
    image: corp-registry/mcp-db-connector:latest
    ports: ["8090:8080"]
    environment:
      MCP_TRANSPORT: "sse"
      MCP_AUTH_TYPE: "mtls"
```

### 6.3 MCP szerver regisztráció (központi registry)

```yaml
# config/mcp_registry.yaml
registry:
  name: "corp-mcp-registry"

servers:
  # === HELYI ESZKÖZÖK ===
  - id: "code_generator"
    type: "local"
    transport: "stdio"
    module: "coder_agent"
    tags: ["development", "codegen"]

  - id: "log_pattern_matcher"
    type: "local"
    transport: "stdio"
    module: "diagnoser_agent"
    tags: ["monitoring", "analysis"]

  # === TÁVOLI ESZKÖZÖK (AWS) ===
  - id: "cloudwatch_log_monitor"
    type: "remote"
    transport: "sse"
    endpoint: "https://xxx.lambda-url.eu-west-1.on.aws/mcp/cloudwatch-logs"
    auth:
      type: "iam_assume_role"
      role_arn: "arn:aws:iam::123456:role/mcp-cloudwatch-reader"
    capabilities:
      streaming: true
      event_emission: true
    config:
      log_groups: ["/ecs/production-app", "/lambda/api-handlers"]
      alert_patterns:
        - { type: "error", pattern: "ERROR|CRITICAL|FATAL|Exception", severity: "high" }
        - { type: "performance", pattern: "timeout|slow_query", severity: "medium" }
      polling_interval_seconds: 30
    tags: ["monitoring", "aws", "cloudwatch", "streaming"]

  - id: "trace_analyzer"
    type: "remote"
    transport: "sse"
    endpoint: "https://xxx.lambda-url.eu-west-1.on.aws/mcp/xray-traces"
    auth:
      type: "iam_assume_role"
      role_arn: "arn:aws:iam::123456:role/mcp-xray-reader"
    tags: ["monitoring", "aws", "tracing"]

  - id: "metric_collector"
    type: "remote"
    transport: "sse"
    endpoint: "https://metrics-mcp.corp.example.com"
    auth: { type: "oauth2" }
    tags: ["monitoring", "metrics"]

  - id: "deployment_manager"
    type: "remote"
    transport: "sse"
    endpoint: "https://xxx.lambda-url.eu-west-1.on.aws/mcp/deployer"
    auth:
      type: "iam_assume_role"
      role_arn: "arn:aws:iam::123456:role/mcp-deployer"
    capabilities:
      tools:
        - "create_canary_deployment"
        - "promote_canary"
        - "rollback_deployment"
        - "get_deployment_health"
    tags: ["deployment", "aws", "cd"]

  - id: "source_repo_manager"
    type: "remote"
    transport: "sse"
    endpoint: "https://mcp.corp.example.com/git"
    auth: { type: "oauth2" }
    capabilities:
      tools:
        - "clone_repo"
        - "create_branch"
        - "commit_and_push"
        - "create_pull_request"
        - "get_file_content"
    tags: ["git", "source_control"]

  # === KÖZÖS ESZKÖZÖK (ágens nélkül) ===
  - id: "compiler_runner"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/compiler"
    tags: ["build", "shared"]

  - id: "dependency_installer"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/deps"
    tags: ["build", "shared"]

  - id: "test_executor"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/test"
    tags: ["testing", "shared"]

  - id: "local_runner"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/runner"
    tags: ["runtime", "shared"]

  - id: "health_checker"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/health"
    tags: ["monitoring", "shared"]

  - id: "notification_sender"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/notifications"
    tags: ["notification", "shared"]

  - id: "file_manager"
    type: "shared"
    transport: "sse"
    endpoint: "http://shared-tools:8080/files"
    tags: ["filesystem", "shared"]
```

---

## 7. Költségmérés és telemetria

### 7.1 Költség-esemény séma (legkisebb granularitás)

```typescript
interface CostEvent {
  event_id: string;
  task_id: string;
  parent_task_id?: string;
  trace_id: string;
  span_id: string;
  timestamp: string;
  module: string;
  agent: string;
  operation_type: OperationType;

  llm?: {
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cached_tokens?: number;
    thinking_tokens?: number;
    cost_per_input_token: number;
    cost_per_output_token: number;
    total_cost_usd: number;
    latency_ms: number;
  };

  tool?: {
    tool_id: string;
    tool_source: "local" | "remote" | "shared";
    endpoint?: string;
    invocation_cost_usd: number;
    data_transfer_bytes?: number;
    latency_ms: number;
  };

  cumulative_task_cost_usd: number;
}

type OperationType =
  | "llm_call" | "llm_call_streaming" | "tool_invocation"
  | "a2a_delegation" | "file_processing" | "embedding"
  | "cache_hit" | "user_interaction_wait";
```

### 7.2 Feladat-szintű költség összesítő

```typescript
interface TaskCostReport {
  task_id: string;
  task_description: string;
  status: "success" | "failed" | "canceled";

  timing: {
    submitted_at: string;
    completed_at: string;
    total_duration_ms: number;
    active_processing_ms: number;
    user_wait_ms: number;
    tool_latency_ms: number;
    llm_latency_ms: number;
  };

  cost: {
    total_usd: number;
    breakdown: {
      llm_costs: {
        total_usd: number;
        by_model: Record<string, {
          calls: number;
          input_tokens: number;
          output_tokens: number;
          cost_usd: number;
        }>;
      };
      tool_costs: {
        total_usd: number;
        by_tool: Record<string, {
          invocations: number;
          cost_usd: number;
          avg_latency_ms: number;
        }>;
      };
    };
  };

  agents_involved: {
    module: string;
    agent: string;
    llm_calls: number;
    tool_calls: number;
    cost_usd: number;
    duration_ms: number;
  }[];

  user_interactions: {
    interaction_id: string;
    type: InteractionType;
    prompt: string;
    response_time_ms: number;
  }[];

  efficiency: {
    tokens_per_second: number;
    cost_per_output_token: number;
    cache_hit_rate: number;
    retry_count: number;
    error_count: number;
  };
}
```

### 7.3 Aggregált riportok

Napi/heti/havi összesítők, modul-szintű riportok, költségoptimalizációs javaslatok (cache-elhető hívások, túl drága modellek, kihasználatlan modulok).

---

## 8. Biztonság és hitelesítés

| Kommunikáció | Protokoll | Hitelesítés |
|---|---|---|
| Felhasználó → Orchestrátor | HTTPS | OAuth 2.1 + PKCE |
| Orchestrátor → Modul (A2A) | HTTPS / gRPC + TLS | Signed Agent Card + JWT |
| Ágens → Helyi MCP | stdio | Implicit (ugyanaz a konténer) |
| Ágens → Távoli MCP | HTTPS + SSE | OAuth 2.1 / mTLS / API Key |
| Ágens → Cloud MCP (GCP) | HTTPS | Service Account + IAM |
| Ágens → Cloud MCP (AWS) | HTTPS | IAM Assume Role / STS |

---

## 9. Flow definíciós motor — Eseményvezérelt reaktív orchestráció

### 9.1 Alapkoncepció

A flow-motor egy **eseményvezérelt reaktív állapotgép**, amelyben:

- **Determinisztikus váz**: Az állapotok, lehetséges átmenetek és invariánsok előre definiáltak YAML DSL-ben
- **LLM döntési pontok**: Bizonyos csomópontokon az LLM dönti el, melyik úton haladjon tovább
- **Visszacsatolási hurkok**: Hiba esetén az ágens visszatér egy korábbi állapotba, javít, és újrapróbálja
- **Párhuzamos ágak**: Független feladatok egyidejűleg futnak
- **Események**: Belső (eszköz eredmény, ágens válasz) és külső (felhasználói input, webhook, cloud alert) események triggerelnek átmeneteket
- **Fázisváltás**: Ugyanaz a flow átmenet nélkül vált a „build" és „operate" fázis között

### 9.2 Flow DSL csomópont-típusok

| Típus | Leírás | Determinisztikus? | Ki dönt? |
|---|---|---|---|
| `agent_task` | Egy ágens modul meghívása A2A-n | Igen | Az ágens |
| `llm_decision` | Döntési pont, ahol az LLM választ a lehetséges átmenetek közül | Részben | LLM |
| `human_interaction` | Felhasználói input bekérése | Igen | Felhasználó |
| `parallel` | Párhuzamos ágak indítása | Igen | Motor |
| `conditional` | Egyszerű feltétel (adat alapján) | Igen | Motor |
| `wait_for_event` | Külső eseményre várakozás | Igen | Külső |
| `trigger_flow` | Másik flow indítása (kompozíció) | Igen | Motor |
| `terminal` | Flow végállapot (success/failed) | Igen | Motor |

### 9.3 Flow Engine belső architektúra

```
┌──────────────────────────────────────────────────────┐
│                     FLOW ENGINE                       │
│                                                       │
│  ┌────────────────┐  ┌────────────────────────────┐  │
│  │  YAML Parser   │  │  State Store               │  │
│  │  & Validator   │  │  (Redis / Firestore)       │  │
│  └───────┬────────┘  └──────────┬─────────────────┘  │
│          ▼                      │                     │
│  ┌──────────────────────────────────────────────┐    │
│  │              Event Loop                       │    │
│  │                                               │    │
│  │  1. Esemény érkezik (agent_result, user_input,│    │
│  │     build_output, cloud_alert, stb.)          │    │
│  │  2. Állapot + átmeneti szabályok kiértékelése │    │
│  │  3a. Determinisztikus → közvetlen átmenet     │    │
│  │  3b. llm_decision → LLM hívás                │    │
│  │  3c. human_interaction → UI-nak küld          │    │
│  │  3d. parallel → ágak indítása                 │    │
│  │  4. Új állapot mentése + CostEvent kibocsátás │    │
│  │  5. Következő agent_task indítása (A2A)       │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │  Retry & Loop Manager                         │    │
│  │  • retry_loop számlálók per hurok             │    │
│  │  • Hasonlóság-detekció (ugyanaz a hiba?)      │    │
│  │  • Teljes flow timeout + költség-plafon        │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │  Context Accumulator                          │    │
│  │  • Minden állapot outputját gyűjti            │    │
│  │  • {{ states.X.output.Y }} → tényleges érték  │    │
│  │  • flow.history → korábbi állapotok           │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## 10. Referencia Use Case — Autonóm szoftverrendszer életciklus

### 10.1 Ágens modulok és közös eszközök

```
modules/
│
├── architect_agent/               # Rendszertervező
│   ├── agent/                     # Üzleti igény → rendszerterv, API design
│   ├── tools/
│   │   └── design_pattern_db      # MCP: tervezési minták adatbázisa
│   └── ui/
│       └── design_panel/          # Widget: rendszerterv vizualizáció
│
├── coder_agent/                   # Kód generáló ÉS hotfix készítő
│   ├── agent/                     # Terv → forráskód VAGY diagnózis → javítás
│   ├── tools/
│   │   ├── code_generator         # MCP: kód scaffolding
│   │   └── snippet_library        # MCP: kód részletek könyvtára
│   ├── remote tools:
│   │   └── source_repo_manager    # Távoli MCP: git műveletek
│   └── ui/
│       └── code_editor/           # Widget: kód megjelenítés, diff view
│
├── builder_agent/                 # Build / fordító (eszköz nélküli ágens)
│   ├── agent/                     # Build folyamat vezérlése
│   ├── tools: []                  # → shared/compiler_runner
│   └── ui/                        # → shared/dependency_installer
│       └── build_console/         # Widget: build log, error highlight
│
├── debugger_agent/                # Hibajavító (build ÉS runtime hibák)
│   ├── agent/                     # Hiba elemzés → javítás
│   ├── tools/
│   │   ├── error_analyzer         # MCP: hibaüzenetek elemzése
│   │   └── code_patcher           # MCP: célzott kód módosítás
│   └── ui/
│       └── debug_panel/           # Widget: hiba + javítás history
│
├── test_writer_agent/             # Teszt generáló (új + regressziós)
│   ├── agent/                     # Kód → tesztek VAGY root cause → regressziós teszt
│   ├── tools/
│   │   └── test_template_gen      # MCP: teszt sablonok
│   └── ui/
│       └── test_overview/         # Widget: teszt lefedettség
│
├── test_runner_agent/             # Teszt futtató (eszköz nélküli ágens)
│   ├── agent/                     # → shared/test_executor
│   └── ui/
│       └── test_dashboard/        # Widget: pass/fail, coverage
│
├── runner_agent/                  # Lokális futtató (eszköz nélküli ágens)
│   ├── agent/                     # → shared/local_runner, health_checker
│   └── ui/
│       └── app_status/            # Widget: app állapot, logok
│
├── watchdog_agent/                # Folyamatos cloud monitoring
│   ├── agent/
│   │   └── mode: persistent       # Folyamatosan fut!
│   ├── tools: []                  # Csak távoli MCP-ket használ:
│   │   # → cloudwatch_log_monitor (streaming)
│   │   # → metric_collector
│   │   # → trace_analyzer
│   └── ui/
│       ├── log_stream/            # Widget: valós idejű log stream
│       ├── alert_panel/           # Widget: alert lista + acknowledge
│       └── alert_feed/            # Widget: kompakt alert feed
│
├── diagnoser_agent/               # Root-cause elemző
│   ├── agent/                     # Logok + trace-ek + forráskód → diagnózis
│   ├── tools/
│   │   ├── log_pattern_matcher    # MCP: log korrelációk
│   │   └── stack_trace_parser     # MCP: stack trace → forráskód hely
│   ├── remote tools:
│   │   ├── cloudwatch_log_monitor
│   │   ├── trace_analyzer
│   │   └── source_repo_manager
│   └── ui/
│       └── diagnosis_panel/       # Widget: root cause fa, érintett fájlok
│
├── incident_coordinator/          # Incidens-vezénylő + deployer
│   ├── agent/                     # Diagnózistól deployig koordinál
│   ├── tools/
│   │   └── incident_knowledge_base  # MCP: korábbi incidensek DB
│   ├── remote tools:
│   │   ├── source_repo_manager
│   │   └── deployment_manager
│   └── ui/
│       ├── incident_timeline/     # Widget: incidens lépések
│       └── deploy_status/         # Widget: canary progress
│
├── reviewer_agent/                # Kód review és dokumentáció
│   ├── agent/
│   ├── tools/
│   │   ├── code_quality           # MCP: kód minőség elemzés
│   │   └── doc_generator          # MCP: dokumentáció generálás
│   └── ui/
│       └── review_panel/          # Widget: review notes, docs
│
└── shared/                        # Ágens nélküli közös MCP eszközök
    ├── compiler_runner/
    ├── dependency_installer/
    ├── test_executor/
    ├── local_runner/
    ├── health_checker/
    ├── file_manager/
    └── notification_sender/
```

### 10.2 Egységes flow — Tervezéstől az öngyógyításig

```yaml
# flows/autonomous_system_lifecycle.flow.yaml
flow:
  name: "autonomous_system_lifecycle"
  version: "1.0.0"
  description: >
    Teljes szoftverrendszer életciklus: üzleti igényből kiindulva megtervezi,
    megépíti, teszteli, telepíti a rendszert, majd folyamatosan felügyeli.
    Hiba detektálásakor diagnosztizál, javít, tesztel, és újra deployol.

  trigger:
    type: "manual"
    input_schema:
      type: "object"
      required: ["business_requirement"]
      properties:
        business_requirement:
          type: "string"
        tech_stack_preferences:
          type: "object"
        constraints:
          type: "array"
          items: { type: "string" }

  config:
    max_retry_loops: 5
    max_parallel_branches: 4
    timeout_minutes: 120
    llm_decision_model: "gemini-2.0-flash"
    fallback_model: "gemini-1.5-pro"
    auto_deploy_policy:
      severity_auto_approve: ["low", "medium"]
      severity_require_human: ["high", "critical"]
    canary_config:
      traffic_percentage: 5
      observation_minutes: 10
      success_threshold: 0.99
    rollback_policy:
      auto_rollback_on_error_spike: true
      error_rate_threshold: 0.05

  states:

    # ══════════════════════════════════════════════════
    #  FÁZIS 1 — TERVEZÉS
    # ══════════════════════════════════════════════════

    analyze_requirement:
      type: "agent_task"
      agent: "architect_agent"
      description: "Üzleti igény elemzése és rendszerterv készítése"
      input:
        requirement: "{{ trigger.business_requirement }}"
        constraints: "{{ trigger.constraints }}"
      output: [system_design, component_list, tech_decisions]
      on_complete: "plan_review"
      on_error: "error_handler"

    plan_review:
      type: "llm_decision"
      context: ["{{ states.analyze_requirement.output }}"]
      decision_prompt: |
        Értékeld a rendszertervet:
        - Teljes és konzisztens → proceed_to_code
        - Hiányos → refine_plan
        - Kérdés van → ask_user
      transitions:
        proceed_to_code: "generate_code"
        refine_plan: "analyze_requirement"
        ask_user: "user_plan_input"

    user_plan_input:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: "{{ states.plan_review.clarification_question }}"
      on_response: "analyze_requirement"

    # ══════════════════════════════════════════════════
    #  FÁZIS 2 — KÓD GENERÁLÁS
    # ══════════════════════════════════════════════════

    generate_code:
      type: "agent_task"
      agent: "coder_agent"
      input:
        system_design: "{{ states.analyze_requirement.output.system_design }}"
        component_list: "{{ states.analyze_requirement.output.component_list }}"
      output: [source_files, project_structure, dependency_manifest]
      on_complete: "build_project"

    # ══════════════════════════════════════════════════
    #  FÁZIS 3 — BUILD (közös a kezdeti buildhez ÉS hotfixhez)
    # ══════════════════════════════════════════════════

    build_project:
      type: "agent_task"
      agent: "builder_agent"
      tools: ["shared/compiler_runner", "shared/dependency_installer"]
      input:
        source_files: "{{ flow.current_source_files }}"
        dependency_manifest: "{{ flow.current_dependency_manifest }}"
      output: [build_result, build_log, error_details]
      on_complete: "build_evaluation"
      on_error: "error_handler"

    build_evaluation:
      type: "llm_decision"
      context:
        - "{{ states.build_project.output }}"
        - "{{ flow.retry_count.build_fix_loop }}"
      decision_prompt: |
        Build eredmény:
        - Sikeres → proceed_to_testing
        - Hiba ÉS retry < max → fix_build
        - Hiba ÉS retry >= max → ask_user_for_help
        - Architekturális hiba → back_to_design
      transitions:
        proceed_to_testing: "parallel_testing"
        fix_build: "fix_code"
        ask_user_for_help: "user_build_help"
        back_to_design: "analyze_requirement"

    fix_code:
      type: "agent_task"
      agent: "debugger_agent"
      retry_loop: "build_fix_loop"
      input:
        source_files: "{{ flow.current_source_files }}"
        error_details: "{{ states.build_project.output.error_details }}"
        build_log: "{{ states.build_project.output.build_log }}"
        previous_fixes: "{{ flow.history.fix_code }}"
      output: [fixed_files, fix_description]
      side_effect:
        set: { "flow.current_source_files": "{{ output.fixed_files }}" }
      on_complete: "build_project"

    user_build_help:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: |
        A build {{ flow.retry_count.build_fix_loop }} próbálkozás után sem sikerült.
        Utolsó hiba: {{ states.build_project.output.error_details }}
      file_upload:
        enabled: true
        description: "Opcionálisan csatolhat konfigurációs fájlokat"
      on_response: "fix_code"

    # ══════════════════════════════════════════════════
    #  FÁZIS 4 — TESZTELÉS (közös az építéshez ÉS hotfixhez)
    # ══════════════════════════════════════════════════

    parallel_testing:
      type: "parallel"
      branches:
        write_tests:
          type: "agent_task"
          agent: "test_writer_agent"
          input:
            source_files: "{{ flow.current_source_files }}"
            system_design: "{{ states.analyze_requirement.output.system_design }}"
            root_cause: "{{ states.deep_diagnosis.output.root_cause | default('') }}"
          output: [test_files, test_coverage_plan]

        run_local:
          type: "agent_task"
          agent: "runner_agent"
          tools: ["shared/local_runner", "shared/health_checker"]
          input:
            source_files: "{{ flow.current_source_files }}"
          output: [runtime_status, runtime_log, detected_issues]

      join: "all"
      on_complete: "run_tests"

    run_tests:
      type: "agent_task"
      agent: "test_runner_agent"
      tools: ["shared/test_executor"]
      input:
        test_files: "{{ states.parallel_testing.branches.write_tests.output.test_files }}"
        source_files: "{{ flow.current_source_files }}"
      output: [test_results, passed_count, failed_count, coverage_percent]
      on_complete: "test_evaluation"

    test_evaluation:
      type: "llm_decision"
      context:
        - "{{ states.run_tests.output }}"
        - "{{ states.parallel_testing.branches.run_local.output }}"
        - "{{ flow.retry_count.test_fix_loop }}"
      decision_prompt: |
        Teszt eredmények és futási állapot:
        - Minden zöld ÉS app fut → proceed_to_deploy
        - Bukott tesztek → fix_test_failures
        - Runtime hiba → fix_runtime
        - Tesztek hibásak → rewrite_tests
      transitions:
        proceed_to_deploy: "pre_deploy_review"
        fix_test_failures: "fix_code_for_tests"
        fix_runtime: "fix_code"
        rewrite_tests: "parallel_testing"

    fix_code_for_tests:
      type: "agent_task"
      agent: "debugger_agent"
      retry_loop: "test_fix_loop"
      input:
        source_files: "{{ flow.current_source_files }}"
        test_results: "{{ states.run_tests.output.test_results }}"
      output: [fixed_files, fix_description]
      side_effect:
        set: { "flow.current_source_files": "{{ output.fixed_files }}" }
      on_complete: "run_tests"

    # ══════════════════════════════════════════════════
    #  FÁZIS 5 — REVIEW ÉS DEPLOY
    # ══════════════════════════════════════════════════

    pre_deploy_review:
      type: "agent_task"
      agent: "reviewer_agent"
      input:
        source_files: "{{ flow.current_source_files }}"
        test_coverage: "{{ states.run_tests.output.coverage_percent }}"
        system_design: "{{ states.analyze_requirement.output.system_design }}"
        is_hotfix: "{{ flow.current_phase == 'operate' }}"
      output: [review_notes, documentation, readme, deployment_guide]
      on_complete: "deploy_decision"

    deploy_decision:
      type: "llm_decision"
      context:
        - "{{ states.pre_deploy_review.output }}"
        - "{{ flow.current_phase }}"
        - "{{ flow.config.auto_deploy_policy }}"
        - "{{ trigger.incident_event | default('') }}"
      decision_prompt: |
        Review kész. Döntsd el:
        - Ha kezdeti deploy VAGY low/medium severity hotfix → auto_deploy
        - Ha high/critical hotfix → ask_human_approval
        - Ha a review kritikus problémát talált → back_to_fix
      transitions:
        auto_deploy: "deploy_canary"
        ask_human_approval: "human_deploy_approval"
        back_to_fix: "fix_code"

    human_deploy_approval:
      type: "human_interaction"
      interaction_type: "single_select"
      prompt: |
        {{ "🔴 HOTFIX" if flow.current_phase == "operate" else "🚀 Kezdeti deploy" }}

        **Review**: {{ states.pre_deploy_review.output.review_notes }}
        {{ "**Root cause**: " + states.deep_diagnosis.output.root_cause if flow.current_phase == "operate" else "" }}
        **Teszt lefedettség**: {{ states.run_tests.output.coverage_percent }}%

        Engedélyezi a canary deploy-t?
      options:
        - { id: "approve", label: "Deploy engedélyezése", recommended: true }
        - { id: "approve_with_pr", label: "Deploy + PR review kell" }
        - { id: "reject", label: "Elutasítás" }
        - { id: "rollback_first", label: "Előbb rollback, aztán deploy" }
      transitions:
        approve: "deploy_canary"
        approve_with_pr: "wait_for_pr"
        reject: "monitoring"
        rollback_first: "emergency_rollback"

    wait_for_pr:
      type: "agent_task"
      agent: "coder_agent"
      tools: ["source_repo_manager"]
      input:
        files: "{{ flow.current_source_files }}"
        action: "create_pull_request"
      output: [pull_request_url]
      on_complete: "wait_for_pr_event"

    wait_for_pr_event:
      type: "wait_for_event"
      event_source: "source_repo_manager"
      event_type: "pr_approved"
      timeout_minutes: 120
      on_event: "deploy_canary"
      on_timeout: "human_deploy_approval"

    deploy_canary:
      type: "agent_task"
      agent: "incident_coordinator"
      tools: ["deployment_manager", "source_repo_manager"]
      input:
        source_files: "{{ flow.current_source_files }}"
        canary_config: "{{ flow.config.canary_config }}"
      output: [deployment_id, canary_url]
      on_complete: "canary_observation"

    canary_observation:
      type: "agent_task"
      agent: "watchdog_agent"
      mode: "timed"
      duration_minutes: "{{ flow.config.canary_config.observation_minutes }}"
      tools: ["cloudwatch_log_monitor", "metric_collector"]
      input:
        deployment_id: "{{ states.deploy_canary.output.deployment_id }}"
        baseline_error_rate: "{{ flow.config.rollback_policy.error_rate_threshold }}"
      output: [canary_health, error_rate, latency_p99, new_errors]
      on_complete: "canary_evaluation"

    canary_evaluation:
      type: "llm_decision"
      context: ["{{ states.canary_observation.output }}"]
      decision_prompt: |
        Canary eredmények:
        - Állapot: {{ canary_health }}, Error rate: {{ error_rate }}
        - Healthy → promote
        - Degraded → extend observation
        - Failing → rollback
      transitions:
        promote: "promote_deployment"
        extend: "canary_observation"
        rollback: "emergency_rollback"

    promote_deployment:
      type: "agent_task"
      agent: "incident_coordinator"
      tools: ["deployment_manager"]
      input:
        deployment_id: "{{ states.deploy_canary.output.deployment_id }}"
      output: [production_version]
      on_complete: "post_deploy"

    post_deploy:
      type: "parallel"
      branches:
        notify:
          type: "agent_task"
          agent: "incident_coordinator"
          tools: ["shared/notification_sender"]
          input:
            type: "{{ 'hotfix_deployed' if flow.current_phase == 'operate' else 'initial_deploy' }}"
            version: "{{ states.promote_deployment.output.production_version }}"
            cost_report: "{{ flow.cost_report }}"
        knowledge_base:
          type: "agent_task"
          agent: "incident_coordinator"
          condition: "{{ flow.current_phase == 'operate' }}"
          tools: ["incident_knowledge_base"]
          input:
            incident: "{{ trigger.incident_event }}"
            root_cause: "{{ states.deep_diagnosis.output.root_cause }}"
            fix: "{{ states.fix_code.output.fix_description | default('') }}"
      join: "all"
      on_complete: "monitoring"

    # ══════════════════════════════════════════════════
    #  FÁZIS 6 — FOLYAMATOS FELÜGYELET
    # ══════════════════════════════════════════════════

    monitoring:
      type: "agent_task"
      agent: "watchdog_agent"
      mode: "persistent_stream"
      tools: ["cloudwatch_log_monitor", "metric_collector", "trace_analyzer"]
      output: [incident_event]
      on_event: "incident_triage"
      # Nem áll meg! Továbbra is figyel.

    # ══════════════════════════════════════════════════
    #  FÁZIS 7 — INCIDENS KEZELÉS ÉS ÖNGYÓGYÍTÁS
    # ══════════════════════════════════════════════════

    incident_triage:
      type: "llm_decision"
      side_effect:
        set: { "flow.current_phase": "operate" }
      context: ["{{ trigger.incident_event }}"]
      decision_prompt: |
        Új incidens:
        - Severity: {{ severity }}, Hiba: {{ error_summary }}
        - Szolgáltatás: {{ affected_service }}, Előfordulások: {{ occurrence_count }}
        Döntsd el:
        - Kódhiba → diagnose
        - Infra probléma → infra_check
        - Ismert hiba → check_knowledge_base
        - Kritikus, azonnali → emergency
        - Átmeneti zaj → dismiss
      transitions:
        diagnose: "deep_diagnosis"
        infra_check: "infrastructure_check"
        check_knowledge_base: "lookup_known_fix"
        emergency: "emergency_human_escalation"
        dismiss: "monitoring"

    deep_diagnosis:
      type: "agent_task"
      agent: "diagnoser_agent"
      tools: ["cloudwatch_log_monitor", "trace_analyzer", "source_repo_manager"]
      input:
        incident: "{{ trigger.incident_event }}"
      output: [root_cause, affected_files, suggested_fix_strategy, confidence, impact_assessment]
      on_complete: "fix_strategy_decision"
      on_error: "diagnosis_failed"

    diagnosis_failed:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: |
        Az automatikus diagnózis nem tudta azonosítani a root cause-t.
        Incidens: {{ trigger.incident_event.error_summary }}
        Részleges eredmények: {{ states.deep_diagnosis.partial_output }}
      on_response: "deep_diagnosis"

    fix_strategy_decision:
      type: "llm_decision"
      context:
        - "{{ states.deep_diagnosis.output }}"
        - "{{ flow.config.auto_deploy_policy }}"
      decision_prompt: |
        Root cause: {{ root_cause }}, Confidence: {{ confidence }}
        Severity: {{ trigger.incident_event.severity }}
        - confidence > 0.8 ÉS low/medium → auto_fix
        - confidence > 0.8 ÉS high/critical → fix_with_approval
        - confidence <= 0.8 → ask_guidance
        - Architekturális változás kell → escalate_redesign
      transitions:
        auto_fix: "prepare_hotfix"
        fix_with_approval: "human_fix_approval"
        ask_guidance: "human_guidance"
        escalate_redesign: "escalate_to_redesign"

    human_fix_approval:
      type: "human_interaction"
      interaction_type: "single_select"
      prompt: |
        🔴 {{ trigger.incident_event.severity | upper }} incidens javítása.
        **Root cause**: {{ states.deep_diagnosis.output.root_cause }}
        **Javítás**: {{ states.deep_diagnosis.output.suggested_fix_strategy }}
        **Hatás**: {{ states.deep_diagnosis.output.impact_assessment }}
      options:
        - { id: "approve", label: "Javítás engedélyezése", recommended: true }
        - { id: "reject", label: "Manuálisan javítom" }
        - { id: "rollback_first", label: "Előbb rollback" }
      transitions:
        approve: "prepare_hotfix"
        reject: "monitoring"
        rollback_first: "emergency_rollback"

    human_guidance:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: |
        A diagnózis bizonytalan (confidence: {{ states.deep_diagnosis.output.confidence }}).
        Lehetséges okok: {{ states.deep_diagnosis.output.root_cause }}
      file_upload: { enabled: true }
      on_response: "prepare_hotfix"

    escalate_to_redesign:
      type: "human_interaction"
      interaction_type: "single_select"
      prompt: |
        A hiba architekturális változást igényel.
        **Root cause**: {{ states.deep_diagnosis.output.root_cause }}
      options:
        - { id: "guidance", label: "Iránymutatást adok" }
        - { id: "redesign", label: "Teljes újratervezés" }
        - { id: "workaround", label: "Workaround egyelőre" }
      transitions:
        guidance: "prepare_hotfix"
        redesign: "analyze_requirement"    # Vissza Fázis 1-be!
        workaround: "prepare_hotfix"

    prepare_hotfix:
      type: "agent_task"
      agent: "coder_agent"
      tools: ["source_repo_manager"]
      input:
        root_cause: "{{ states.deep_diagnosis.output.root_cause }}"
        affected_files: "{{ states.deep_diagnosis.output.affected_files }}"
        fix_strategy: "{{ states.deep_diagnosis.output.suggested_fix_strategy }}"
        human_guidance: "{{ states.human_guidance.response | default('') }}"
      output: [fixed_files, fix_description, hotfix_branch_name]
      side_effect:
        set: { "flow.current_source_files": "{{ output.fixed_files }}" }
      on_complete: "build_project"       # → Fázis 3-ba! (közös build)
      # Innentől: build → test → review → deploy → monitoring
      # Ugyanazok az állapotok, ugyanazok az ágensek!

    # ══════════════════════════════════════════════════
    #  ROLLBACK ÉS ESZKALÁCIÓ
    # ══════════════════════════════════════════════════

    emergency_rollback:
      type: "agent_task"
      agent: "incident_coordinator"
      tools: ["deployment_manager"]
      input:
        reason: "{{ states.canary_evaluation.context | default('manual') }}"
      output: [rolled_back_to_version, rollback_success]
      on_complete: "rollback_evaluation"

    rollback_evaluation:
      type: "llm_decision"
      context:
        - "{{ states.emergency_rollback.output }}"
        - "{{ flow.retry_count.full_fix_cycle }}"
      decision_prompt: |
        Rollback megtörtént.
        - Első kísérlet → retry fix más stratégiával
        - Többszöri kudarc → escalate
      transitions:
        retry: "deep_diagnosis"
        escalate: "final_human_escalation"

    emergency_human_escalation:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: |
        🚨 KRITIKUS — Azonnali beavatkozás szükséges!
        **Szolgáltatás**: {{ trigger.incident_event.affected_service }}
        **Hiba**: {{ trigger.incident_event.error_summary }}
      timeout_seconds: 300
      on_response: "incident_triage"
      on_timeout: "emergency_rollback"

    final_human_escalation:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: |
        ⚠️ Többszöri próbálkozás után sem sikerült automatikusan javítani.
        **Próbálkozások**: {{ flow.retry_count.full_fix_cycle }}
        **Eddigi költség**: {{ flow.cost_report.total_usd }} USD
        Manuális beavatkozás szükséges.
      on_response: "deep_diagnosis"

    # ══════════════════════════════════════════════════
    #  GLOBÁLIS HIBAKEZELÉS
    # ══════════════════════════════════════════════════

    infrastructure_check:
      type: "agent_task"
      agent: "diagnoser_agent"
      tools: ["metric_collector", "trace_analyzer"]
      input:
        incident: "{{ trigger.incident_event }}"
        check_type: "infrastructure"
      output: [infra_diagnosis, is_code_issue]
      on_complete: "infra_evaluation"

    infra_evaluation:
      type: "conditional"
      condition: "{{ states.infrastructure_check.output.is_code_issue }}"
      if_true: "deep_diagnosis"
      if_false: "notify_infra_team"

    notify_infra_team:
      type: "agent_task"
      agent: "incident_coordinator"
      tools: ["shared/notification_sender"]
      input:
        diagnosis: "{{ states.infrastructure_check.output.infra_diagnosis }}"
        channels: ["slack", "pagerduty"]
      on_complete: "monitoring"

    lookup_known_fix:
      type: "agent_task"
      agent: "incident_coordinator"
      tools: ["incident_knowledge_base"]
      input:
        incident: "{{ trigger.incident_event }}"
      output: [known_fix, confidence]
      on_complete: "known_fix_evaluation"

    known_fix_evaluation:
      type: "llm_decision"
      context: ["{{ states.lookup_known_fix.output }}"]
      decision_prompt: |
        Ismert javítás: {{ known_fix }}, confidence: {{ confidence }}
        - Ha confidence > 0.9 → apply directly
        - Ha bizonytalan → full diagnosis
      transitions:
        apply: "prepare_hotfix"
        full_diagnosis: "deep_diagnosis"

    error_handler:
      type: "llm_decision"
      context: ["{{ error }}", "{{ flow.current_state }}", "{{ flow.history }}"]
      decision_prompt: |
        Váratlan hiba. Döntés:
        - Újrapróbálható → retry
        - Felhasználó segítsége kell → ask_user
        - Fatális → abort
      transitions:
        retry: "{{ flow.current_state }}"
        ask_user: "user_error_help"
        abort: "flow_aborted"

    user_error_help:
      type: "human_interaction"
      interaction_type: "free_text"
      prompt: "Váratlan hiba: {{ error.message }}"
      on_response: "{{ flow.current_state }}"

    flow_aborted:
      type: "terminal"
      status: "failed"
      output:
        error: "{{ error }}"
        partial_results: "{{ flow.collected_outputs }}"
        cost_report: "{{ flow.cost_report }}"
```

### 10.3 Vizuális flow — Az egységes életciklus

```
                         ┌───────────────┐
                         │  ÜZLETI IGÉNY  │
                         │   (trigger)    │
                         └───────┬───────┘
                                 │
═══════════════ FÁZIS 1: TERVEZÉS ═══════════════
                                 │
                         ┌───────▼───────┐
                    ┌───►│  ARCHITECT    │◄─── user input (ha kérdés)
                    │    │  AGENT        │
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
  architekturális   │    │ LLM DECISION  │── nem OK ──►  vissza ▲
  redesign ─────────┤    └───────┬───────┘
  (fázis 7-ből!)    │            │ OK
                    │            │
═══════════════ FÁZIS 2: KÓD GENERÁLÁS ═════════
                    │            │
                    │    ┌───────▼───────┐
                    │    │  CODER AGENT  │
                    │    └───────┬───────┘
                    │            │
═══════════════ FÁZIS 3: BUILD ══════════════════
                    │            │              ┌──────────────┐
                    │    ┌───────▼───────┐      │              │
                    │    │ BUILDER AGENT │◄─────┤  DEBUGGER    │
                    │    └───────┬───────┘  fix │  AGENT       │
                    │    ┌───────▼───────┐      │  (javítás)   │
                    │    │ LLM DECISION  │─────►│              │
                    │    └───────┬───────┘      └──────────────┘
                    │            │ OK
═══════════════ FÁZIS 4: TESZTELÉS ══════════════
                    │            │
                    │    ┌───────▼───────┐
                    │    │   PARALLEL    │
                    │    │ ┌─────┐┌────┐ │
                    │    │ │TESZT││RUN │ │
                    │    │ │ÍRÁS ││APP │ │
                    │    │ └──┬──┘└──┬─┘ │
                    │    └────┼──────┼───┘
                    │    ┌────▼──────▼───┐
                    │    │  TEST RUNNER  │◄──── debugger fix hurok
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
                    │    │ LLM DECISION  │
                    │    └───────┬───────┘
                    │            │ all green
═══════════════ FÁZIS 5: REVIEW & DEPLOY ════════
                    │            │
                    │    ┌───────▼───────┐
                    │    │  REVIEWER     │
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
                    │    │  DEPLOY       │─── human approval (ha kell)
                    │    │  CANARY       │
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
                    │    │  WATCHDOG 👀  │─── canary figyelés
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
                    │    │ LLM DECISION  │─── failing → ROLLBACK
                    │    └───────┬───────┘
                    │            │ healthy
                    │    ┌───────▼───────┐
                    │    │  PROMOTE TO   │
                    │    │  PRODUCTION   │
                    │    └───────┬───────┘
                    │            │
═══════════════ FÁZIS 6: FELÜGYELET ═════════════
                    │            │
                    │    ┌───────▼───────┐
                    │    │  WATCHDOG     │  ← folyamatos figyelés
                    │    │  (persistent) │
                    │    └───────┬───────┘
                    │          event!
═══════════════ FÁZIS 7: ÖNGYÓGYÍTÁS ════════════
                    │            │
                    │    ┌───────▼───────┐
                    │    │ LLM DECISION  │─── zaj → vissza figyelés
                    │    │ (triage)      │─── kritikus → ember
                    │    └───────┬───────┘
                    │            │
                    │    ┌───────▼───────┐
                    │    │  DIAGNOSER    │◄─── ha fail → ember segít
                    │    │  AGENT        │
                    │    └───────┬───────┘
                    │    ┌───────▼───────┐
                    │    │ LLM DECISION  │─── alacsony confidence → ember
                    │    │(fix stratégia)│
                    │    └───────┬───────┘
                    │            │
                    │    ┌───────▼───────┐
                    │    │  CODER AGENT  │  ← UGYANAZ mint Fázis 2!
                    │    │  (hotfix)     │
                    │    └───────┬───────┘
                    │            │
                    │            ▼
                    │    ╔═══════════════╗
                    │    ║ VISSZA FÁZIS  ║  ← build → test → review
                    └────║ 3-BA!         ║    → deploy → monitoring
                         ╚═══════════════╝    → ... (végtelen ciklus)
```

### 10.4 A kulcs: közös állapotok, közös ágensek

A flow lényege, hogy a **Fázis 3–5 (build → test → review → deploy) teljesen közös** a kezdeti építéshez és a hotfix-hez. Ami ezt lehetővé teszi:

**`flow.current_source_files`** — Egy flow-szintű változó, amelyet mindig a legfrissebb forráskód-állapotra mutat. Akár a `generate_code`, akár a `prepare_hotfix` állítja be, a `build_project` mindig ugyanonnan olvassa.

**`flow.current_phase`** — `"build"` vagy `"operate"`. Néhány döntési pont (pl. `deploy_decision`) ennek alapján módosítja a viselkedését, de az ágensek és az állapotok azonosak.

**Ágens újrahasznosítás összefoglaló:**

| Ágens | Fázis 1-5 (Építés) | Fázis 6-7 (Üzemeltetés) |
|---|---|---|
| `architect_agent` | Rendszertervezés | Redesign (ha kell) |
| `coder_agent` | Kód generálás | Hotfix készítés |
| `builder_agent` | Kezdeti build | Hotfix build |
| `debugger_agent` | Build/teszt hiba javítás | Runtime hiba javítás |
| `test_writer_agent` | Tesztek írása | Regressziós tesztek |
| `test_runner_agent` | Tesztek futtatása | Tesztek futtatása |
| `reviewer_agent` | Kód review + docs | Hotfix review |
| `watchdog_agent` | – | Canary figyelés + monitoring |
| `diagnoser_agent` | – | Root-cause elemzés |
| `incident_coordinator` | Deploy | Incidens + deploy + knowledge base |

---

## 11. Frontend architektúra — Dinamikus, widget-alapú felület

### 11.1 Alapkoncepció

A keretrendszer felülete teljesen dinamikus: a felhasználó határozza meg, milyen oldalakat hoz létre, azokon milyen ágens- és eszköz-UI komponenseket jelenít meg, és milyen elrendezésben. Minden ágens modul és eszköz egy önálló UI widgetet is szállít. Az oldalak egy felső menübe rendeződnek, amelynek struktúrája YAML konfigurációban van.

```
┌────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Dinamikus felső menü (YAML-ből)                       │    │
│  │  ┌──────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐  │    │
│  │  │ Home │ │ Builder  │ │ Monitoring│ │ Cost Center │  │    │
│  │  └──────┘ └──────────┘ └───────────┘ └─────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Aktív oldal: "Monitoring"  (layout: 2x2 grid)        │    │
│  │                                                        │    │
│  │  ┌──────────────────┐  ┌──────────────────────────┐   │    │
│  │  │ watchdog_agent   │  │  diagnoser_agent         │   │    │
│  │  │ :log_stream      │  │  :diagnosis_panel        │   │    │
│  │  └──────────────────┘  └──────────────────────────┘   │    │
│  │  ┌──────────────────┐  ┌──────────────────────────┐   │    │
│  │  │ tool:metric_     │  │  incident_coordinator    │   │    │
│  │  │ collector:charts │  │  :incident_timeline      │   │    │
│  │  └──────────────────┘  └──────────────────────────┘   │    │
│  └────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Globális sáv: Flow állapot | Költség: $0.42 | SSE ●  │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### 11.2 Widget azonosítási konvenció

```
<scope>:<module_name>:<widget_name>

  agent:watchdog_agent:log_stream       → Ágens modul widgetje
  tool:metric_collector:charts          → MCP eszköz widgetje
  system:flow_tracker                   → Beépített rendszer widget
```

### 11.3 Workspace konfiguráció (YAML)

```yaml
# workspaces/developer_workspace.yaml
workspace:
  name: "Developer Workspace"
  owner: "bela@example.com"
  theme: "dark"

  navigation:
    position: "top"
    items:
      - id: "home"
        label: "Home"
        icon: "home"
        page: "dashboard"
      - id: "builder"
        label: "Rendszer Építő"
        icon: "hammer"
        page: "builder_view"
      - id: "monitoring"
        label: "Monitoring"
        icon: "activity"
        page: "monitoring_view"
        badge:
          source: "watchdog_agent"
          event: "active_incidents"
          color: "red"
      - id: "costs"
        label: "Költségek"
        icon: "dollar-sign"
        page: "cost_center"
      - id: "flows"
        label: "Flow-k"
        icon: "git-branch"
        children:
          - { id: "active", label: "Aktív flow-k", page: "active_flows_view" }
          - { id: "history", label: "Előzmények", page: "flow_history_view" }
      - id: "settings"
        label: "Beállítások"
        icon: "settings"
        page: "settings_view"
        position: "right"

  pages:
    dashboard:
      title: "Áttekintő"
      layout: { type: "grid", columns: 12, row_height: 80, gap: 16 }
      widgets:
        - widget: "system:flow_overview"
          position: { col: 1, row: 1, width: 8, height: 4 }
          config: { show_flows: ["autonomous_system_lifecycle"], display_mode: "timeline" }
        - widget: "system:cost_summary"
          position: { col: 9, row: 1, width: 4, height: 2 }
          config: { period: "today" }
        - widget: "system:active_interactions"
          position: { col: 9, row: 3, width: 4, height: 2 }
        - widget: "agent:watchdog_agent:alert_feed"
          position: { col: 1, row: 5, width: 6, height: 3 }
          config: { severity_filter: ["high", "critical"] }
        - widget: "agent:incident_coordinator:status_board"
          position: { col: 7, row: 5, width: 6, height: 3 }

    builder_view:
      title: "Rendszer Építő"
      layout: { type: "grid", columns: 12, row_height: 80, gap: 16 }
      widgets:
        - widget: "agent:architect_agent:design_panel"
          position: { col: 1, row: 1, width: 6, height: 5 }
          config: { show_system_diagram: true, editable: true }
        - widget: "agent:coder_agent:code_editor"
          position: { col: 7, row: 1, width: 6, height: 5 }
          config: { syntax_highlighting: true, diff_view: true, show_thinking: true }
        - widget: "agent:builder_agent:build_console"
          position: { col: 1, row: 6, width: 4, height: 3 }
          config: { auto_scroll: true }
        - widget: "agent:test_runner_agent:test_dashboard"
          position: { col: 5, row: 6, width: 4, height: 3 }
          config: { show_coverage: true }
        - widget: "agent:debugger_agent:debug_panel"
          position: { col: 9, row: 6, width: 4, height: 3 }
          config: { show_fix_history: true }
        - widget: "system:flow_tracker"
          position: { col: 1, row: 9, width: 12, height: 2 }
          config: { flow: "autonomous_system_lifecycle", show_cost_per_step: true }

    monitoring_view:
      title: "Rendszer Felügyelet"
      layout: { type: "grid", columns: 12, row_height: 80, gap: 16 }
      widgets:
        - widget: "agent:watchdog_agent:log_stream"
          position: { col: 1, row: 1, width: 8, height: 4 }
          config: { auto_scroll: true, highlight_errors: true, filterable: true }
        - widget: "agent:watchdog_agent:alert_panel"
          position: { col: 9, row: 1, width: 4, height: 4 }
          config: { group_by: "severity" }
        - widget: "tool:metric_collector:charts"
          position: { col: 1, row: 5, width: 6, height: 4 }
          config: { metrics: ["error_rate", "latency_p99", "cpu_utilization"], time_range: "1h" }
        - widget: "agent:diagnoser_agent:diagnosis_panel"
          position: { col: 7, row: 5, width: 6, height: 4 }
        - widget: "tool:deployment_manager:deploy_status"
          position: { col: 1, row: 9, width: 6, height: 3 }
          config: { show_canary_progress: true }
        - widget: "agent:incident_coordinator:incident_timeline"
          position: { col: 7, row: 9, width: 6, height: 3 }

    cost_center:
      title: "Költségek"
      layout: { type: "grid", columns: 12, row_height: 80, gap: 16 }
      widgets:
        - widget: "system:cost_breakdown"
          position: { col: 1, row: 1, width: 8, height: 4 }
          config: { group_by: "module", period: "7d", chart_type: "stacked_bar" }
        - widget: "system:cost_alerts"
          position: { col: 9, row: 1, width: 4, height: 4 }
        - widget: "system:token_usage"
          position: { col: 1, row: 5, width: 6, height: 3 }
          config: { show_cache_hits: true }
        - widget: "system:cost_optimizer"
          position: { col: 7, row: 5, width: 6, height: 3 }

  interaction_policy:
    display_mode: "widget_preferred"
    audio_notification: true
    critical_fullscreen: true
    auto_navigate: false
```

### 11.4 Widget manifest (modulonként)

```yaml
# modules/watchdog_agent/ui/widgets.yaml
widgets:
  - id: "log_stream"
    name: "Log Stream"
    description: "Valós idejű log stream CloudWatch-ból"
    component: "./log_stream/LogStreamWidget.tsx"
    icon: "terminal"
    min_size: { width: 4, height: 3 }
    default_size: { width: 8, height: 4 }
    config_schema:
      properties:
        auto_scroll: { type: "boolean", default: true }
        highlight_errors: { type: "boolean", default: true }
        filterable: { type: "boolean", default: true }
    subscriptions:
      - { event: "task_event", filter: { agent: "watchdog_agent" } }
      - { event: "log_entry", source: "cloudwatch_log_monitor" }
    emits:
      - { event: "log_selected", payload: { log_entry: "object" } }
      - { event: "error_highlighted", payload: { error_id: "string" } }
```

### 11.5 Widget SDK API

```typescript
interface WidgetSDK {
  // Események (widgetek közötti + backend)
  subscribe(event: string, handler: (payload: any) => void): () => void;
  emit(event: string, payload: any): void;

  // Backend kommunikáció
  connectionStatus: "connected" | "reconnecting" | "disconnected";
  sendAction(action: string, params: any): Promise<any>;

  // Megosztott állapot (oldalon belül)
  getSharedState(key: string): any;
  setSharedState(key: string, value: any): void;

  // Felhasználói interakció (flow kérdések)
  onInteractionRequired(handler: (interaction: InputRequiredPayload) => void): void;
  respondToInteraction(interactionId: string, response: any): void;

  // Költség
  costDisplay: React.ReactNode;

  // Beépített UI komponensek
  WidgetHeader: React.FC<WidgetHeaderProps>;
  WidgetFooter: React.FC<WidgetFooterProps>;
  FilterBar: React.FC<FilterBarProps>;
  ThinkingIndicator: React.FC<{ steps: string[] }>;
  InteractionDialog: React.FC<{ interaction: InputRequiredPayload }>;
}
```

### 11.6 Oldal szerkesztő mód (Layout Editor)

A felhasználó vizuálisan szerkesztheti az oldalakat: widget katalógusból drag & drop, átméretezés, konfigurálás, új oldal létrehozás, menü szerkesztés. A szerkesztés eredménye frissíti a workspace YAML-t.

---

## 12. Telepítési és üzemeltetési terv

### 12.1 Környezetek

| Környezet | Cél | Infrastruktúra |
|---|---|---|
| **local** | Fejlesztés, debug | Docker Compose, helyi MCP |
| **dev** | Integrációs tesztelés | GKE dev cluster |
| **staging** | Elfogadási tesztek | GKE + távoli MCP |
| **production** | Éles üzem | GKE / Cloud Run + multi-cloud MCP |

### 12.2 CI/CD pipeline

```
Git push → Lint & Type check → Unit tesztek → MCP szerver tesztek
  → Agent Card validáció → Widget build & tesztek → Konténer build
  → Integration tesztek → Költség-benchmark (regresszió ellenőrzés)
  → Deploy staging → Smoke tesztek → Deploy production (canary)
```

---

## 13. Ramp-up terv

### Fázis 1: Alapok (2-3 hét)
- [ ] Monorepo, Google ADK dev env
- [ ] Első ágens modul (coder_agent) helyi MCP eszközzel
- [ ] A2A kommunikáció: Root Agent ↔ 1 modul
- [ ] Cost tracking skeleton

### Fázis 2: Flow motor (2-3 hét)
- [ ] YAML DSL parser és validator
- [ ] Flow Engine: állapotgép + LLM döntési pontok
- [ ] Visszacsatolási hurkok, retry logic
- [ ] Párhuzamos ágak
- [ ] `flow.current_source_files` típusú flow-változók

### Fázis 3: Interakció és UI shell (2-3 hét)
- [ ] Frontend shell: menü, oldal-router, layout engine
- [ ] Widget SDK + első widgetek (build_console, code_editor)
- [ ] SSE stream → gondolkodás-menet vizualizáció
- [ ] Interaktív kérdés-válasz flow
- [ ] Layout editor (drag & drop)

### Fázis 4: Távoli MCP és monitoring (2-3 hét)
- [ ] Távoli MCP szerver sablonok (Cloud Run, Lambda)
- [ ] MCP Registry
- [ ] CloudWatch log monitor + metric collector
- [ ] Watchdog agent (persistent mode)
- [ ] Diagnoser agent + deployment_manager integráció

### Fázis 5: Teljes életciklus (2-3 hét)
- [ ] Egységes flow: build → deploy → monitor → heal
- [ ] Canary deploy + observation ciklus
- [ ] Rollback és eszkaláció
- [ ] Knowledge base (tanulás korábbi incidensekből)
- [ ] Költség pipeline (OTel → BigQuery → riportok)

### Fázis 6: Élesítés (1-2 hét)
- [ ] CI/CD pipeline
- [ ] Load testing, stabilizálás
- [ ] Dokumentáció, fejlesztői útmutató
- [ ] Production canary deploy

**Becsült teljes ramp-up: 11-17 hét**

---

## 14. Technológiai stack

| Réteg | Technológia |
|---|---|
| **Ágens keretrendszer** | Google ADK (Python SDK) |
| **Ágens kommunikáció** | A2A Protocol v0.3 (JSON-RPC / SSE / gRPC) |
| **Eszköz integráció** | MCP (2025-11-25 spec, stdio + SSE) |
| **Flow motor** | Temporal + Python engine |
| **LLM** | Gemini 2.0 Flash (elsődleges), Gemini 1.5 Pro (fallback) |
| **Frontend** | React 18+ / Next.js, TypeScript, Zustand |
| **Layout engine** | react-grid-layout |
| **Backend API** | Python FastAPI |
| **Konténerizálás** | Docker, Google Artifact Registry |
| **Orchestráció** | GKE (prod), Docker Compose (dev) |
| **Távoli MCP** | Cloud Run (GCP), Lambda (AWS), Docker (on-prem) |
| **Telemetria** | OpenTelemetry → BigQuery |
| **CI/CD** | GitHub Actions / Cloud Build |

---

## Függelék A: Példa — Teljes életciklus futás

**Trigger**: "Építs egy REST API-t felhasználókezeléshez, Node.js + PostgreSQL stack-kel"

1. `architect_agent` → rendszerterv (3 endpoint, DB séma, auth)
2. **LLM DECISION** → terv OK → tovább
3. `coder_agent` → forráskód generálás (Express.js, Prisma ORM)
4. `builder_agent` → `npm install` + `tsc` → **HIBA**: missing type definition
5. **LLM DECISION** → fix_build
6. `debugger_agent` → `@types/express` hozzáadása → fix
7. `builder_agent` → rebuild → **SIKER**
8. **PARALLEL**: `test_writer_agent` (Jest tesztek) + `runner_agent` (app indítás)
9. `test_runner_agent` → 14/15 teszt zöld, 1 fail (auth middleware)
10. `debugger_agent` → auth middleware javítás
11. `test_runner_agent` → 15/15 zöld ✅
12. `reviewer_agent` → kód review OK, README + API docs generálva
13. **LLM DECISION** → kezdeti deploy → auto
14. `incident_coordinator` → canary deploy (5% traffic)
15. `watchdog_agent` → 10 perc canary figyelés → healthy ✅
16. Promote to production → **ÉLES** 🚀
17. `watchdog_agent` → folyamatos figyelés...

*...3 nap múlva...*

18. `watchdog_agent` → **EVENT**: `TypeError: Cannot read property 'id' of null` (12 előfordulás)
19. **LLM DECISION** (triage) → kódhiba → diagnose
20. `diagnoser_agent` → root cause: nullable user a `/api/users/:id` endpoint-on
21. **LLM DECISION** → confidence 0.92, severity medium → auto_fix
22. `coder_agent` → hotfix: null check + 404 response
23. `builder_agent` → build OK
24. **PARALLEL**: meglévő tesztek + új regressziós teszt (null user eset)
25. 16/16 zöld ✅
26. `reviewer_agent` → hotfix review OK
27. Canary deploy → 10 perc figyelés → healthy ✅
28. Promote → **ÉLŐ JAVÍTÁS** 🔧
29. Knowledge base frissítve, notification küldve
30. Vissza monitoring-ra...

**Összköltség**: $0.18 (építés) + $0.04 (hotfix) = **$0.22**