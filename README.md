# Aether AI — Modern AI Chat Interface & FastAPI Backend

A production-minded AI chat application featuring a sleek React + Tailwind frontend paired with a high-performance, low-idle-resource Python FastAPI backend. Native support for **Gemma 4 models via Google Gemini API**, **local Gemma instances via Ollama/vLLM**, and an immediate zero-key **Mock provider**.

---

## ⚡ Quickstart

### 1. Backend Setup & Run (Python 3.11+)

```bash
# Install backend dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run FastAPI backend with hot-reload
uvicorn app.main:app --reload --port 8000
```

The backend starts at `http://localhost:8000`.
- Liveness check: `http://localhost:8000/health`
- Models list: `http://localhost:8000/models`

### 2. Frontend Setup & Run (React + Vite)

```bash
# Install frontend dependencies
npm install

# Run frontend development server
npm run dev
```

The frontend interface starts at `http://localhost:5173`.

---

## ⚙️ Environment Variables Reference

All backend configuration is managed through environment variables (`.env`).

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENV` | `string` | `development` | Environment mode (`development` or `production`). |
| `APP_VERSION` | `string` | `1.0.0` | Application version echoed by `/health`. |
| `AUTH_TOKEN` | `string` | *(unset)* | Optional bearer token. When unset, auth is disabled. When set, requests must provide `Authorization: Bearer <AUTH_TOKEN>`. |
| `CORS_ORIGINS` | `csv` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed frontend origins. |
| `MAX_REQUEST_BODY_BYTES` | `int` | `10485760` (10 MB) | Pure ASGI request body size limit; requests exceeding this are rejected with `413`. |
| `LLM_PROVIDER` | `string` | `mock` | Active model provider: `gemini`, `openai_compat`, or `mock`. Defaults to `mock` if `GEMINI_API_KEY` is unset. |
| `GEMINI_API_KEY` | `string` | *(unset)* | Google AI Studio API key for native Gemini Gemma access. |
| `GEMMA_MODEL` | `string` | `gemma-4-26b-a4b-it` | Default model identifier. |
| `ALLOWED_MODELS` | `csv` | `gemma-4-31b-it,gemma-4-26b-a4b-it,mock` | Allowlist of models client requests can target. |
| `SYSTEM_PROMPT_MODE` | `string` | `prepend` | `native` (uses API `systemInstruction`) or `prepend` (prepends to first user turn). |
| `THINKING_LEVEL` | `string` | `minimal` | `minimal` or `high`. When thinking tokens arrive, they are isolated from answer text. |
| `LLM_BASE_URL` | `string` | `http://localhost:11434/v1` | Base URL for local Ollama / vLLM / LocalAI instances. |
| `LLM_API_KEY` | `string` | `ollama` | API key for local OpenAI-compatible endpoints. |
| `LLM_MODEL` | `string` | `gemma-4-26b-a4b-it` | Model name to pass to local OpenAI-compatible endpoints. |
| `MAX_MESSAGES` | `int` | `100` | Max messages allowed per `/chat` request. |
| `MAX_CHARS_PER_MESSAGE` | `int` | `20000` | Max character length for individual messages. |
| `MAX_TOTAL_CHARS` | `int` | `120000` | Max combined character length across all messages. |
| `DEFAULT_MAX_OUTPUT_TOKENS`| `int` | `2048` | Default token generation limit. |
| `UPSTREAM_TIMEOUT_SECONDS` | `float` | `45.0` | Upstream provider timeout before returning 504. |
| `MCP_ENABLED` | `bool` | `false` | Enable Model Context Protocol (MCP) tool calling and client integration. |
| `MCP_CONFIG_PATH` | `string` | `mcp_servers.json` | Path to JSON config defining MCP servers. |
| `TOOL_TIMEOUT_SECONDS` | `float` | `15.0` | Timeout per external MCP tool execution. |
| `MAX_TOOL_RESULT_CHARS` | `int` | `8000` | Max characters retained from tool output before truncation. |
| `MAX_TOOL_ITERATIONS` | `int` | `5` | Maximum autonomous tool execution rounds per turn. |
| `MCP_ALLOWED_TOOLS` | `csv` | *(unset)* | Comma-separated allowlist of tools (e.g. `builtin__fetch_url`). Unset enables all discovered tools. |
| `TOOL_CALL_MODE` | `string` | `native` | Function calling mechanism: `native` (API declarations) or `prompted` (JSON markdown format). |
| `SQLITE_DB_PATH` | `string` | `storage/local.db` | Target SQLite database file for the built-in MCP server. |
| `SQLITE_ALLOW_WRITE` | `bool` | `false` | Permit write/schema-altering SQL operations via `builtin__execute_write`. |

---

## 🧠 Provider Setup Guides

### 1. Using Google Gemini API (Gemma 4)
1. Generate an API key in [Google AI Studio](https://aistudio.google.com/).
2. In `.env`:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_actual_api_key_here
   GEMMA_MODEL=gemma-4-26b-a4b-it
   SYSTEM_PROMPT_MODE=prepend
   THINKING_LEVEL=minimal
   ```
3. Restart Uvicorn. Client calls to `/chat` now stream directly from Gemma 4 via Gemini API with automatic role mapping (`assistant` $\rightarrow$ `model`) and thinking token isolation.

### 2. Using Local Gemma via Ollama
1. Start Ollama with Gemma:
   ```bash
   ollama run gemma:2b # or your local Gemma model tag
   ```
2. In `.env`:
   ```env
   LLM_PROVIDER=openai_compat
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_API_KEY=ollama
   LLM_MODEL=gemma:2b
   ```
3. Restart Uvicorn. All requests route to your local GPU/CPU engine with zero outbound internet traffic.

### 3. Using Offline Mock Mode (Zero Keys Required)
Leave `LLM_PROVIDER=mock` (or unset `GEMINI_API_KEY`). The backend immediately runs offline, emitting realistic word-by-word streaming tokens with simulated cadence.

---

## 🛠️ Model Context Protocol (MCP) Integration

The backend acts as an **MCP Client**: at startup, it reads `mcp_servers.json`, connects to external or built-in tool servers, discovers their tools, and executes a multi-turn tool-calling loop inside `/chat`.

### 1. Off-by-Default Architecture
- By default, `MCP_ENABLED=false`. When disabled, the `mcp` library is **never imported**, no background subprocesses or network connections start, `GET /tools` is unmounted, and `/chat` incurs zero tool-checking overhead.
- When `MCP_ENABLED=true`, tool management runs inside the FastAPI lifespan using a unified `AsyncExitStack`.

### 2. Built-in Tool Server
A production-hardened MCP server is included in [`app/mcp_tools/server.py`](file:///c:/Users/Win/Desktop/prep%20for%20hackathon/app/mcp_tools/server.py) providing:
- **`builtin__fetch_url`**: SSRF-safe web page content fetcher.
  - Enforces public-IP validation (`ip.is_global`) on every DNS resolution and follow-up redirect (up to 3 hops).
  - Unwraps IPv4-mapped IPv6 addresses (`::ffff:127.0.0.1`).
  - Blocks loopback, link-local, cloud metadata (`169.254.169.254`), and embedded URL credentials (`http://user:pass@host`).
  - Extracts clean article text and top 20 hyperlinks using `BeautifulSoup4`.
- **`builtin__read_query`**: Safe read-only SQLite runner with `mode=ro`, `PRAGMA query_only = ON;`, 5-second progress-handler interrupt timeout, and capped 100-row results.
- **`builtin__describe_table`**: SQL schema and column inspector validated against `sqlite_master`.
- **`builtin__execute_write`**: Write tool strictly mounted only when `SQLITE_ALLOW_WRITE=true`.

### 3. Server Configuration (`mcp_servers.json`)
You can attach any stdio, http, or sse MCP server without altering code:

```json
{
  "servers": {
    "builtin": {
      "transport": "stdio",
      "command": "${PYTHON}",
      "args": ["-m", "app.mcp_tools.server"],
      "env": {
        "SQLITE_DB_PATH": "${SQLITE_DB_PATH}",
        "SQLITE_ALLOW_WRITE": "${SQLITE_ALLOW_WRITE}"
      }
    },
    "remote_weather": {
      "transport": "http",
      "url": "https://mcp.example.com/weather",
      "headers": {
        "Authorization": "Bearer YOUR_REMOTE_TOKEN"
      }
    }
  }
}
```

### 4. SSE Stream Events with Tools
When a client sets `"use_tools": true` in `POST /chat`, the backend executes the model's requested tools and emits real-time event updates:

```http
event: tool_call
data: {"id": "call_7a1b", "name": "builtin__fetch_url", "arguments": {"url": "https://example.com"}}

event: tool_result
data: {"id": "call_7a1b", "name": "builtin__fetch_url", "preview": "Example Domain: This domain is for use in illustrative examples in documents."}

data: {"token": "Based on the page content, example.com is used for documentation."}
data: {"done": true}
```

### 5. Example `curl` Request

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is on https://example.com?"}
    ],
    "use_tools": true,
    "stream": true
  }'
```

---

## 🔌 Connecting Frontend `sendMessage()` to FastAPI

To connect the React frontend to the FastAPI `/chat` endpoint, update `sendMessage()` in [`src/services/aiService.ts`](file:///c:/Users/Win/Desktop/prep%20for%20hackathon/src/services/aiService.ts):

```typescript
import { SendMessageOptions } from '../types';

export async function sendMessage(options: SendMessageOptions): Promise<string> {
  const { prompt, modelId, conversationHistory, onThinking, onToken, signal } = options;

  // Signal pre-generation thinking state
  if (onThinking) onThinking();

  // Filter messages to strict user/assistant roles (server injects system prompt)
  const messages = [
    ...conversationHistory
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content })),
    { role: 'user', content: prompt },
  ];

  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      // If AUTH_TOKEN is enabled in backend .env, uncomment:
      // 'Authorization': 'Bearer YOUR_AUTH_TOKEN',
    },
    body: JSON.stringify({
      messages,
      model: modelId === 'mock-gpt-4o' ? 'mock' : modelId,
      stream: true,
      temperature: 0.7,
      max_output_tokens: 2048,
    }),
    signal,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('Response body is not readable.');

  const decoder = new TextDecoder('utf-8');
  let accumulated = '';
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('event:')) continue;
      if (trimmed.startsWith('data: ')) {
        const rawJson = trimmed.slice(6);
        try {
          const parsed = JSON.parse(rawJson);
          if (parsed.token) {
            accumulated += parsed.token;
            onToken(parsed.token, accumulated);
          }
          if (parsed.done) {
            return accumulated;
          }
        } catch {
          // ignore partial JSON chunk boundaries
        }
      }
    }
  }

  return accumulated;
}
```

---

## 🧪 Running Automated Tests

Run the test suite with pytest:

```bash
python -m pytest -v
```

All 28 automated tests across 8 test suites verify:
- Liveness check (`/health`) and models listing (`/models`)
- Streaming SSE concluding with `{"done": true}` and non-streaming JSON completion
- Client role restriction (rejecting `role: "system"`, `role: "tool"`, or `tool_calls` with `422`)
- Optional `AUTH_TOKEN` validation and disallowed model rejection
- Message character limits and request body size enforcement (`413`)
- Outermost `CORSMiddleware` ordering ensuring error responses (`413`, `429`, `500`) retain CORS headers
- Gemini provider role mapping (`assistant` $\rightarrow$ `model`), prompt modes (`prepend`/`native`), and thinking level isolation
- MCP client disabled zero-overhead guarantee and dynamic `GET /tools` discovery
- Multi-turn tool execution loop with concurrent tool resolution and iteration capping
- SSRF prevention (DNS checking, loopback/private IP blocking, IPv4-mapped IPv6 unwrapping, redirect tracking)
- SQLite tool security (`mode=ro`, timeout interruption, and write capability gating)
- Gemini native function call declarations and prompted JSON parsing mode
#   H a c k a t h o n P r e p  
 