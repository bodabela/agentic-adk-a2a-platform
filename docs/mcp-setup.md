# MCP eszközök beállítási útmutató

Ez a dokumentum részletesen bemutatja, hogyan lehet MCP (Model Context Protocol) eszközöket konfigurálni és bekötni az ágens platformba. Minden konfiguráció deklaratívan, az ágens `agent.yaml` fájljában történik.

---

## 1. Áttekintés

Az MCP eszközök lehetővé teszik, hogy az ágensek külső toolokat használjanak — fájlkezelést, adatbázis-hozzáférést, API-integrációt, keresést, stb. A platform három MCP transzportot támogat:

| Transzport | Típus | Mikor használjuk |
|------------|-------|------------------|
| `stdio` (simple) | Lokális Python szerver | Saját fejlesztésű MCP toolok |
| `stdio` (advanced) | Tetszőleges parancs | npm/community MCP szerverek (npx, uvx) |
| `sse` | Távoli SSE szerver | Már futó MCP szervererekhez |
| `streamable_http` | Távoli HTTP szerver | Újabb MCP protokollt használó szerverek |

### Fájlstruktúra

```
agents/
  coder_agent/
    agent.yaml              # MCP konfiguráció itt
    prompts/
      system_prompt.md
  tools/                    # Megosztott MCP szerverek
    mcp_server.py
```

---

## 2. stdio — Lokális Python MCP szerver (simple mode)

A legegyszerűbb mód: egy Python fájl, amely `FastMCP`-vel definiálja a toolokat.

### 2.1 agent.yaml konfiguráció

```yaml
agent:
  name: "coder_agent"
  model: "gemini-2.5-flash"
  tools:
    mcp:
      - transport: "stdio"
        server: "../tools/mcp_server.py"    # Relatív útvonal az ágens könyvtárához
        workspace: "{{ workspace_dir }}"     # A platform workspace könyvtára
```

### 2.2 Mezők

| Mező | Típus | Kötelező | Leírás |
|------|-------|----------|--------|
| `transport` | string | igen | `"stdio"` |
| `server` | string | igen* | Python fájl relatív útvonala az ágens könyvtárához képest |
| `workspace` | string | nem | Workspace könyvtár, `--workspace` argumentumként átadva |
| `tool_filter` | list[string] | nem | Csak ezeket a toolokat expose-olja az ágensnek |

*Ha `server` van megadva (nem `command`), a platform a jelenlegi Python interpreterrel (`sys.executable`) indítja.

### 2.3 MCP szerver implementáció

```python
# agents/tools/mcp_server.py
import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Parse --workspace argument
_parser = argparse.ArgumentParser()
_parser.add_argument("--workspace", type=str, default=".")
_args, _ = _parser.parse_known_args()
WORKSPACE = Path(_args.workspace).resolve()

mcp = FastMCP("MyToolServer")

@mcp.tool()
def list_files() -> dict:
    """List all files in the workspace."""
    files = []
    for p in sorted(WORKSPACE.rglob("*")):
        if p.is_file():
            files.append({"path": str(p.relative_to(WORKSPACE)), "size": p.stat().st_size})
    return {"status": "success", "files": files}

@mcp.tool()
def read_file(file_path: str) -> dict:
    """Read a file's contents.

    Args:
        file_path: Relative path within the workspace.
    """
    p = (WORKSPACE / file_path).resolve()
    if not str(p).startswith(str(WORKSPACE)):
        return {"status": "error", "message": "Path escapes workspace"}
    if not p.exists():
        return {"status": "error", "message": f"Not found: {file_path}"}
    return {"status": "success", "content": p.read_text(encoding="utf-8")}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 2.4 Belső működés

```
AgentFactory._build_mcp_stdio()
    │
    ├── server_path = (agents_dir / agent_name / server).resolve()
    ├── workspace = _resolve_templates(workspace, workspace_dir)
    │
    └── McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,      # python.exe / python3
                    args=[server_path, "--workspace", workspace],
                )
            )
        )
```

### 2.5 Hibaelhárítás

| Hiba | Ok | Megoldás |
|------|-----|---------|
| `mcp_server_not_found` | A `server` útvonal nem létezik | Ellenőrizd a relatív útvonalat (kiindulópont: `agents/<agent_name>/`) |
| `mcp_missing_server_or_command` | Sem `server`, sem `command` nincs megadva | Add meg az egyiket |
| Timeout indításnál | A Python szerver lassú (dependency import) | Használd a `_prewarm_mcp_deps()` mechanizmust a `main.py`-ban |

---

## 3. stdio — Tetszőleges parancs (advanced mode)

Bármilyen MCP-kompatibilis szerver indítható: npm csomagok, node scriptek, Go binárisok, Docker konténerek, stb.

### 3.1 agent.yaml konfiguráció

```yaml
agent:
  name: "research_agent"
  model: "gemini-2.5-flash"
  tools:
    mcp:
      # Filesystem szerver npx-szel
      - transport: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-filesystem", "{{ workspace_dir }}"]

      # GitHub szerver
      - transport: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: "{{ env.GITHUB_TOKEN }}"

      # Python szerver uvx-szel (nincs telepítve, futáskor letölti)
      - transport: "stdio"
        command: "uvx"
        args: ["mcp-server-sqlite", "--db-path", "{{ workspace_dir }}/data.db"]
```

### 3.2 Mezők

| Mező | Típus | Kötelező | Leírás |
|------|-------|----------|--------|
| `transport` | string | igen | `"stdio"` |
| `command` | string | igen* | A futtatandó parancs (pl. `"npx"`, `"node"`, `"uvx"`, `"docker"`) |
| `args` | list[string] | nem | Parancssori argumentumok |
| `env` | dict[string, string] | nem | Extra környezeti változók (a meglévőkhöz adja) |
| `tool_filter` | list[string] | nem | Tool név whitelist |

*Ha `command` van megadva, a `server` mezőt ignorálja.

### 3.3 Gyakori npm MCP szerverek

```yaml
# Filesystem (fájl olvasás/írás/keresés)
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{{ workspace_dir }}"]

# GitHub (issue, PR, keresés)
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-github"]
  env:
    GITHUB_PERSONAL_ACCESS_TOKEN: "{{ env.GITHUB_TOKEN }}"

# Brave Search (webes keresés)
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-brave-search"]
  env:
    BRAVE_API_KEY: "{{ env.BRAVE_API_KEY }}"

# PostgreSQL (adatbázis)
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-postgres", "{{ env.DATABASE_URL }}"]

# Google Drive
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-gdrive"]
  env:
    GDRIVE_CREDENTIALS: "{{ env.GDRIVE_CREDENTIALS }}"

# Slack
- transport: "stdio"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-slack"]
  env:
    SLACK_BOT_TOKEN: "{{ env.SLACK_BOT_TOKEN }}"
```

### 3.4 Belső működés

```
AgentFactory._build_mcp_stdio()  (command ág)
    │
    ├── args = [_resolve_templates(a) for a in mcp_conf.args]
    ├── env = {k: _resolve_templates(v) for k, v in mcp_conf.env}
    │
    └── McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
                    env={"NODE_ENV": "production"},
                )
            )
        )
```

### 3.5 Hibaelhárítás

| Hiba | Ok | Megoldás |
|------|-----|---------|
| `command not found` | A parancs nincs telepítve | Telepítsd: `npm install -g npx` vagy `pip install uvx` |
| npx timeout | Első futásnál letölti a csomagot | Használd a `-y` flag-et és várj türelemmel |
| Env var üres | `{{ env.VAR }}` nem létezik | Add hozzá a `.env` fájlhoz vagy a rendszer env-hez |

---

## 4. sse — SSE MCP szerver

Távoli vagy lokálisan külön futó MCP szerverekhez, amelyek SSE (Server-Sent Events) protokollon kommunikálnak.

### 4.1 agent.yaml konfiguráció

```yaml
agent:
  name: "api_agent"
  model: "gemini-2.5-flash"
  tools:
    mcp:
      - transport: "sse"
        url: "http://localhost:8080/sse"
        headers:
          Authorization: "Bearer {{ env.MCP_API_KEY }}"
          X-Custom-Header: "my-value"
        timeout: 10.0              # Kapcsolat timeout (másodperc)
        sse_read_timeout: 600.0    # Olvasási timeout (másodperc)
        tool_filter: ["search", "create"]   # Opcionális
```

### 4.2 Mezők

| Mező | Típus | Kötelező | Default | Leírás |
|------|-------|----------|---------|--------|
| `transport` | string | igen | — | `"sse"` |
| `url` | string | igen | — | A szerver SSE végpontjának URL-je |
| `headers` | dict[string, string] | nem | `{}` | HTTP headers (autentikáció, API kulcsok) |
| `timeout` | float | nem | `5.0` | Kapcsolódási timeout másodpercben |
| `sse_read_timeout` | float | nem | `300.0` | SSE olvasási timeout másodpercben |
| `tool_filter` | list[string] | nem | `null` | Tool név whitelist |

### 4.3 SSE MCP szerver indítása (Python példa)

```python
# Lokális SSE szerver indítása teszteléshez
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MySSEServer")

@mcp.tool()
def search(query: str) -> dict:
    """Search for information."""
    return {"results": [f"Result for: {query}"]}

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8080)
```

Indítás:
```bash
python my_sse_server.py
# Server elérhető: http://localhost:8080/sse
```

### 4.4 Belső működés

```
AgentFactory._build_mcp_sse()
    │
    ├── url = _resolve_templates(mcp_conf.url)
    ├── headers = {k: _resolve_templates(v) for k, v in mcp_conf.headers}
    │
    └── McpToolset(
            connection_params=SseConnectionParams(
                url="http://localhost:8080/sse",
                headers={"Authorization": "Bearer sk-..."},
                timeout=10.0,
                sse_read_timeout=600.0,
            )
        )
```

### 4.5 Hibaelhárítás

| Hiba | Ok | Megoldás |
|------|-----|---------|
| `mcp_sse_missing_url` | Nincs `url` megadva | Add meg az `url` mezőt |
| Connection refused | A szerver nem fut | Indítsd el a szervert, ellenőrizd a portot |
| 401 Unauthorized | Hibás vagy hiányzó token | Ellenőrizd a `headers` és az env változót |
| SSE read timeout | A szerver túl lassan válaszol | Növeld az `sse_read_timeout` értékét |

---

## 5. streamable_http — Streamable HTTP MCP szerver

Az MCP protokoll legújabb transzportja, HTTP kérés-válasz alapú, streaming támogatással.

### 5.1 agent.yaml konfiguráció

```yaml
agent:
  name: "prod_agent"
  model: "gemini-2.5-flash"
  tools:
    mcp:
      - transport: "streamable_http"
        url: "https://mcp.example.com/mcp"
        headers:
          Authorization: "Bearer {{ env.MCP_API_KEY }}"
        timeout: 5.0
        sse_read_timeout: 300.0
```

### 5.2 Mezők

Ugyanazok mint az SSE-nél:

| Mező | Típus | Kötelező | Default | Leírás |
|------|-------|----------|---------|--------|
| `transport` | string | igen | — | `"streamable_http"` |
| `url` | string | igen | — | A szerver HTTP végpontjának URL-je |
| `headers` | dict[string, string] | nem | `{}` | HTTP headers |
| `timeout` | float | nem | `5.0` | Kapcsolódási timeout |
| `sse_read_timeout` | float | nem | `300.0` | Olvasási timeout |
| `tool_filter` | list[string] | nem | `null` | Tool név whitelist |

### 5.3 Streamable HTTP szerver indítása (Python példa)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MyHTTPServer")

@mcp.tool()
def create_ticket(title: str, description: str) -> dict:
    """Create a support ticket."""
    return {"ticket_id": "TICK-123", "status": "created"}

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=3000)
```

### 5.4 Belső működés

```
AgentFactory._build_mcp_streamable_http()
    │
    ├── url = _resolve_templates(mcp_conf.url)
    ├── headers = {k: _resolve_templates(v) for k, v in mcp_conf.headers}
    │
    └── McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://mcp.example.com/mcp",
                headers={"Authorization": "Bearer sk-..."},
                timeout=5.0,
                sse_read_timeout=300.0,
            )
        )
```

### 5.5 SSE vs Streamable HTTP

| Szempont | SSE | Streamable HTTP |
|----------|-----|-----------------|
| Protokoll | Server-Sent Events (egyirányú stream) | HTTP kérés-válasz + stream |
| Kompatibilitás | Régebbi MCP szerverek | Újabb MCP szerverek (2024+) |
| Tűzfal | Szükséges nyitott SSE kapcsolat | Standard HTTP(S), tűzfal-barát |
| Proxy | Nem minden proxy támogatja az SSE-t | HTTP proxy kompatibilis |
| Ajánlott | Fejlesztés, legacy szerverek | Produkció, cloud deployment |

---

## 6. Template változók

Minden MCP konfiguráció mezőben használhatók template változók. A feloldás az `AgentFactory._resolve_templates()` metódusban történik.

### 6.1 Elérhető template-ek

| Template | Leírás | Forrás |
|----------|--------|--------|
| `{{ workspace_dir }}` | A platform workspace könyvtára | `APP_WORKSPACE_DIR` env var vagy config |
| `{{ env.VAR_NAME }}` | Tetszőleges környezeti változó | `os.environ` |

### 6.2 Hol használhatók

| Mező | Példa |
|------|-------|
| `url` | `"http://{{ env.MCP_HOST }}:8080/sse"` |
| `args[]` | `["--db", "{{ env.DATABASE_URL }}"]` |
| `headers{}` | `Authorization: "Bearer {{ env.API_KEY }}"` |
| `env{}` | `TOKEN: "{{ env.MASTER_TOKEN }}"` |
| `workspace` | `"{{ workspace_dir }}/project"` |

### 6.3 .env fájl

A platform a `backend/.env` fájlt tölti be induláskor (dotenv). Az MCP konfigurációkban hivatkozott env változókat itt érdemes definiálni:

```env
# backend/.env
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
MCP_API_KEY=sk-xxxxxxxxxxxx
BRAVE_API_KEY=BSA-xxxxxxxxxxxx
DATABASE_URL=postgresql://user:pass@localhost/db
```

---

## 7. Tool filter

A `tool_filter` mező lehetővé teszi, hogy egy MCP szervernek csak bizonyos tooljai legyenek elérhetők az ágens számára.

### Használat

```yaml
tools:
  mcp:
    # Egy nagy MCP szerverből csak 2 toolt használunk
    - transport: "sse"
      url: "http://github-mcp.example.com/sse"
      tool_filter: ["search_issues", "create_issue"]

    # Másik ágens ugyanahhoz a szerverhez, más toolokkal
    # (másik agent.yaml-ben)
    - transport: "sse"
      url: "http://github-mcp.example.com/sse"
      tool_filter: ["list_repos", "get_repo"]
```

### Működés

A `tool_filter` a Google ADK `McpToolset` `tool_filter` paraméterére képeződik le. Az MCP szerver összes toolja betöltődik, de az ágens számára csak a listában szereplők lesznek elérhetők.

---

## 8. Több MCP szerver egy ágensben

Egy ágens tetszőleges számú MCP szervert használhat, akár különböző transzportokkal:

```yaml
agent:
  name: "full_stack_agent"
  model: "gemini-2.5-flash"
  tools:
    mcp:
      # 1. Lokális fájlkezelés
      - transport: "stdio"
        server: "../tools/mcp_server.py"
        workspace: "{{ workspace_dir }}"

      # 2. GitHub integráció (npx)
      - transport: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: "{{ env.GITHUB_TOKEN }}"

      # 3. Távoli keresés (SSE)
      - transport: "sse"
        url: "http://search-mcp.internal:8080/sse"
        tool_filter: ["semantic_search"]

    builtin:
      - "send_notification"
```

Minden MCP szerver külön process-ként / kapcsolatként működik. Az összes tool egy közös névtérben lesz elérhető az ágens számára.

---

## 9. Tools oldal (UI)

A platform **Tools** menüpontja (`/tools`) automatikusan felsorolja az összes elérhető toolt:

- **MCP stdio (Python):** AST-elemzéssel kinyeri a tool neveket, docstringeket és paramétereket a forrásból
- **MCP stdio (command) / SSE / HTTP:** Runtime-ban felfedezett toolokként jelzi (a pontos lista futáskor derül ki MCP protokollon)
- **Builtin toolok:** Statikus séma (ask_user, send_notification, exit_loop, list_channels)

Minden toolnál látható:
- Név, leírás, paraméterek (név, típus, required, default)
- Melyik ágensek használják
- Transzport típus és szerver azonosító

---

## 10. Teljes MCPToolConfig séma referencia

```yaml
# Minden mező és default érték
- transport: "stdio"              # "stdio" | "sse" | "streamable_http"

  # stdio simple mode
  server: null                    # Relatív Python fájl útvonal
  workspace: null                 # "{{ workspace_dir }}"

  # stdio advanced mode
  command: null                   # "npx", "node", "uvx", "docker", stb.
  args: []                        # Parancssori argumentumok
  env: {}                         # Extra környezeti változók

  # sse / streamable_http
  url: null                       # Szerver URL
  headers: {}                     # HTTP headers
  timeout: 5.0                    # Kapcsolat timeout (másodperc)
  sse_read_timeout: 300.0         # Olvasási timeout (másodperc)

  # Közös
  tool_filter: null               # Tool név whitelist (null = összes)
```

**Pydantic modell:** `backend/src/agents/schema.py` → `MCPToolConfig`

**Factory implementáció:** `backend/src/agents/factory.py` → `_build_mcp_tool()`, `_build_mcp_stdio()`, `_build_mcp_sse()`, `_build_mcp_streamable_http()`
