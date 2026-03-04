# Cost Tracking — Technikai dokumentáció

## Áttekintés

A platform valós időben követi az LLM hívások és tool használatok költségét.
A költségadatok a backend-en keletkeznek, SSE-n keresztül jutnak el a frontend-re,
ahol hierarchikusan aggregálva jelennek meg (task → module → agent → event).

```
 ┌─────────────┐    ┌──────────────┐    ┌───────────┐    ┌────────────┐
 │ LLM Provider│───>│ CostTracker  │───>│ EventBus  │───>│ SSE Stream │
 │ / A2A Agent │    │ (pricing +   │    │ (in-mem)  │    │ /api/events│
 └─────────────┘    │  aggregation)│    └───────────┘    └─────┬──────┘
                    └──────────────┘                           │
                                                          ┌────▼──────┐
                                                          │ Frontend  │
                                                          │ costStore │
                                                          │ → UI      │
                                                          └───────────┘
```

---

## 1. Költségszámítási képlet

```
total_cost_usd = (input_tokens × cost_per_input_token)
               + (output_tokens × cost_per_output_token)
```

A token-árak a `config/llm_providers.yaml` fájlból származnak:

| Provider  | Model                    | Input $/token | Output $/token |
|-----------|--------------------------|---------------|----------------|
| Google    | gemini-2.5-flash         | 0.00000015    | 0.0000006      |
| Google    | gemini-2.5-pro           | 0.00000125    | 0.000005       |
| Google    | gemini-3.1-pro-preview   | 0.00000125    | 0.000005       |
| Anthropic | claude-sonnet-4-20250514 | 0.000003      | 0.000015       |
| Anthropic | claude-haiku-3-20250414  | 0.0000008     | 0.000004       |
| OpenAI    | gpt-4o                   | 0.0000025     | 0.00001        |
| OpenAI    | gpt-4o-mini              | 0.00000015    | 0.0000006      |

Az árak keresése: `LLMProvidersConfig.get_pricing(provider, model) → ModelPricing`.
Ha a provider/model nem található, az ár 0.0 (nincs költség számítva).

---

## 2. Token számolás — pontos vs. becsült

### Pontos token-szám (LLM Decision hívások)

A flow engine `_handle_llm_decision` metódusa közvetlenül hívja a `call_llm()` függvényt
(`backend/src/llm/provider.py`), amely az LLM SDK-ból kapja az exact token-számot:

| Provider  | Input tokens forrás             | Output tokens forrás              |
|-----------|---------------------------------|-----------------------------------|
| Google    | `usage_metadata.prompt_token_count`    | `usage_metadata.candidates_token_count` |
| Anthropic | `message.usage.input_tokens`    | `message.usage.output_tokens`     |
| OpenAI    | `usage.prompt_tokens`           | `usage.completion_tokens`         |

Ezek a számok **pontosak**, közvetlenül a provider API-ból származnak.

### Becsült token-szám (Agent A2A hívások)

Az agent modulok (pl. `coder_agent`) a Google ADK Runner-en keresztül futnak,
amely nem teszi közvetlenül elérhetővé a token-számokat az Event objektumon.
Ezért a `serve_a2a.py` **karakterszám-alapú becslést** alkalmaz:

```python
input_tokens_est  = max(len(user_text) // 4, 1)
output_tokens_est = max(total_output_chars // 4, 1)
```

- **~4 karakter/token** heurisztika (angol szövegre és kódra átlagos)
- Minimum 1 token, hogy ne legyen nulla-költségű esemény
- Az `input_tokens_est` **alulbecsül**: csak a user prompt szövegét számolja,
  a system prompt-ot és a konverzáció-történetet nem
- Az `output_tokens_est` az összes generált szöveget számolja
  (streaming text + thinking + final response)

---

## 3. Költségkeletkezési pontok

### 3.1. LLM Decision (pontos)

**Fájl:** `backend/src/flow_engine/engine.py` — `_handle_llm_decision()`

Amikor a flow egy `llm_decision` állapotba lép, a flow engine közvetlenül
hívja a `call_llm()` függvényt, amely visszaadja az exact token-számot.

```python
await self.cost_tracker.record_llm_call(
    task_id=flow_id,
    module="flow_engine",
    agent="llm_decision",
    model=model,                    # pl. "gemini-2.5-flash"
    input_tokens=response.input_tokens,    # PONTOS
    output_tokens=response.output_tokens,  # PONTOS
    latency_ms=response.latency_ms,
    provider=provider,              # pl. "google"
)
```

### 3.2. Agent Task (becsült)

**Fájlok:**
- `modules/coder_agent/agent/serve_a2a.py` — usage becslés
- `backend/src/flow_engine/engine.py` — `_handle_agent_task()`

Az A2A szerver a futás végén egy `usage` blokkot csatol a válaszhoz:

```json
{
  "usage": {
    "input_tokens_est": 250,
    "output_tokens_est": 1200,
    "model": "gemini-2.5-flash",
    "provider": "google",
    "latency_ms": 15000
  }
}
```

A flow engine kiolvassa és rögzíti:

```python
usage = output.pop("_usage", None)
if usage:
    await self.cost_tracker.record_llm_call(
        task_id=flow_id,
        module=node.agent,          # pl. "coder_agent"
        agent=node.agent,
        model=usage["model"],
        input_tokens=usage["input_tokens_est"],    # BECSÜLT
        output_tokens=usage["output_tokens_est"],  # BECSÜLT
        latency_ms=usage["latency_ms"],
        provider=usage["provider"],
    )
```

### 3.3. Tool Invocation (nulla költség, latency méréssel)

**Fájl:** `backend/src/flow_engine/engine.py` — `_call_agent_a2a_streaming()`

Az MCP tool-ok használata közvetlenül nem jár pénzügyi költséggel,
de a platform nyomon követi őket:

```python
await self.cost_tracker.record_tool_invocation(
    task_id=flow_id,
    module=agent_name,
    agent=author,
    tool_id=tool_name,              # pl. "write_file", "read_file"
    tool_source="mcp",
    latency_ms=tool_latency,        # tool_call → tool_result közti idő
)
```

A latency mérése a `tool_call` és `tool_result` SSE események közötti idő.

---

## 4. Adatfolyam részletesen

### 4.1. Backend: CostTracker

**Fájl:** `backend/src/cost/tracker.py`

A `CostTracker` két fő metódusa:

| Metódus                    | Mikor hívódik                  | Eredmény                     |
|----------------------------|--------------------------------|------------------------------|
| `record_llm_call()`        | LLM decision, agent task végén | CostEvent + pricing számítás |
| `record_tool_invocation()` | tool_result SSE event érkezik  | CostEvent (0 USD költség)    |

Mindkét metódus:
1. Kikeresi az árat a `LLMProvidersConfig`-ból (ha LLM hívás)
2. Kiszámítja a `total_cost_usd`-t
3. Frissíti a `TaskCostReport` kumulatív összesítőt
4. Létrehoz egy `CostEvent`-et
5. Az `EventBus`-on keresztül sugározza: `emit("cost_event", event.model_dump())`

### 4.2. Backend: Adatmodell

**Fájl:** `backend/src/cost/models.py`

```
CostEvent
├── event_id: str (UUID)
├── task_id: str (flow_id vagy task_id)
├── timestamp: datetime
├── module: str ("flow_engine" | "coder_agent" | ...)
├── agent: str ("llm_decision" | "coder_agent" | ...)
├── operation_type: OperationType
│   ├── llm_call
│   ├── tool_invocation
│   ├── a2a_delegation
│   └── ... (egyéb típusok)
├── llm: LLMCostDetail | None
│   ├── provider, model
│   ├── input_tokens, output_tokens
│   ├── cached_tokens, thinking_tokens
│   ├── cost_per_input_token, cost_per_output_token
│   ├── total_cost_usd
│   └── latency_ms
├── tool: ToolCostDetail | None
│   ├── tool_id, tool_source
│   ├── invocation_cost_usd (általában 0.0)
│   └── latency_ms
└── cumulative_task_cost_usd: float
```

### 4.3. SSE sugárzás

**Fájlok:**
- `backend/src/events/bus.py` — in-memory EventBus (maxsize=100/subscriber)
- `backend/src/api/events.py` — SSE endpoint: `GET /api/events/stream`

Az EventBus az összes csatlakozott SSE kliensnek sugározza az eseményt:

```
event: cost_event
data: {"event_id": "...", "task_id": "...", "llm": {...}, ...}
```

### 4.4. Frontend: SSE fogadás

**Fájl:** `frontend/src/hooks/useSSE.ts`

```typescript
es.addEventListener('cost_event', (e) => {
    const data = JSON.parse(e.data);
    const costUsd = (data.llm?.total_cost_usd || 0)
                  + (data.tool?.invocation_cost_usd || 0);
    addCostEvent({
        event_id, task_id, timestamp,
        module, agent, operation_type,
        llm: { provider, model, input_tokens, ... },
        tool: { tool_id, tool_source, ... },
        cost_usd: costUsd,
        cumulative_task_cost_usd,
    });
});
```

### 4.5. Frontend: Zustand Store

**Fájl:** `frontend/src/stores/costStore.ts`

A store tárolja:
- `totalCostUsd` — összes költség (gördülő összeg)
- `costByTask` — task_id szerinti bontás
- `recentEvents` — utolsó 100 esemény (FIFO puffer)
- `granularity` — aktuális nézet szintje

Aggregációs függvények (pure, `useMemo`-val hívva a komponensben):
- `aggregateByTask()` — task_id szerint csoportosít
- `aggregateByModule()` — task → module hierarchia
- `aggregateByAgent()` — task → module → agent hierarchia

### 4.6. Frontend: Megjelenítés

**Fájl:** `frontend/src/pages/CostsPage.tsx`

Granularitás szintek:

| Szint    | Mit mutat                                      |
|----------|-------------------------------------------------|
| Total    | Egyetlen összesítő kártya                      |
| Task     | Task-onkénti bontás (kibontható sorok)          |
| Module   | Task → Module hierarchia                        |
| Agent    | Task → Module → Agent hierarchia                |
| Event    | Egyedi események részletes listája              |

---

## 5. Ismert korlátozások

1. **Token becslés pontossága**: Az A2A agent hívások ~4 karakter/token
   heurisztikát használnak. Ez kódnál ~3.5, angol szövegnél ~4-5 char/token
   között változik. A tényleges költség ±30%-kal eltérhet.

2. **Input token alulbecslés**: Az agent hívások input_tokens_est értéke
   csak a user prompt szövegét tartalmazza. A system prompt (~2000-5000 token)
   és a korábbi conversation history nincs benne.

3. **In-memory tárolás**: A `CostTracker` és a frontend `costStore` is memóriában
   tárolja az adatokat. Szerver újraindításkor elvesznek. A frontend 100 eseményt
   tart meg.

4. **Több LLM hívás per agent task**: Egy agent task (pl. `coder_agent`) belül
   több LLM round-trip is lehet (thinking → tool call → thinking → response).
   Jelenleg ezek egyetlen összesített költségeseményként jelennek meg, nem
   egyenként.

5. **Tool költség**: Az MCP tool-ok invocation_cost_usd értéke mindig 0.0.
   Ha külső fizetős API-kat hívunk tool-ként, azt manuálisan kell konfigurálni.

---

## 6. Konfigurálás

### Új modell árának hozzáadása

Szerkeszd a `config/llm_providers.yaml` fájlt:

```yaml
providers:
  google:
    models:
      gemini-new-model:
        display_name: "Gemini New"
        pricing:
          input_per_token: 0.000001
          output_per_token: 0.000004
        max_tokens: 65536
```

A `CostTracker` automatikusan kikeresi az árat a config-ból
a `provider` + `model` kulcsok alapján.

### Új agent modul költségkövetése

Ha új agent modult adsz hozzá A2A interfésszel:
1. A `serve_a2a.py` végpontokban add hozzá a `usage` blokkot a válaszhoz
2. A flow engine `_parse_a2a_result` automatikusan kiolvassa a `usage` mezőt
3. A `_handle_agent_task` automatikusan rögzíti a költséget
