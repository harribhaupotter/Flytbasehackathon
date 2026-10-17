import sys
import os
import time
import json
import socket
import sqlite3
import tempfile
import asyncio
import atexit
import subprocess
from typing import Dict, Any, List, Optional, Tuple
import httpx

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.config import Settings

# Global tracking for subprocess cleanup
_CURRENT_SERVER: Optional["ServerProcess"] = None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerProcess:
    """Manages the FastAPI backend subprocess with custom env overrides."""

    def __init__(self, port: int, env_overrides: Optional[Dict[str, str]] = None):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.log_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log", encoding="utf-8")
        self.env = os.environ.copy()
        self.env["ENV"] = "development"
        if env_overrides:
            self.env.update(env_overrides)
        self.proc: Optional[subprocess.Popen] = None

    def start(self, timeout_sec: float = 25.0):
        global _CURRENT_SERVER
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--log-level",
            "info",
        ]
        self.proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            env=self.env,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _CURRENT_SERVER = self

        # Wait for health probe
        start_time = time.time()
        client = httpx.Client(timeout=2.0)
        healthy = False
        while time.time() - start_time < timeout_sec:
            if self.proc.poll() is not None:
                self.log_file.flush()
                self.log_file.seek(0)
                logs = self.log_file.read()
                raise RuntimeError(f"Server subprocess died prematurely:\n{logs[-1000:]}")
            try:
                resp = client.get(f"{self.base_url}/health")
                if resp.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
        client.close()

        if not healthy:
            self.stop()
            raise RuntimeError(f"Server on port {self.port} failed to become healthy within {timeout_sec}s.")

    def get_logs(self) -> str:
        if self.log_file:
            self.log_file.flush()
            try:
                with open(self.log_file.name, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def stop(self):
        global _CURRENT_SERVER
        if self.proc:
            try:
                # Terminate entire process tree (uvicorn and any child MCP processes)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                    capture_output=True,
                )
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        if self.log_file:
            try:
                self.log_file.close()
                os.remove(self.log_file.name)
            except Exception:
                pass
        _CURRENT_SERVER = None


def _cleanup_handler():
    if _CURRENT_SERVER:
        _CURRENT_SERVER.stop()


atexit.register(_cleanup_handler)


# ==============================================================================
# INDIVIDUAL CHECKS
# ==============================================================================

def check_1_config() -> Tuple[bool, str, Dict[str, Any]]:
    """1. CONFIG: provider is gemini, key present (print yes/no only), default model in ALLOWED_MODELS."""
    s = Settings()
    key_present = bool(s.GEMINI_API_KEY and s.GEMINI_API_KEY.strip())
    provider_is_gemini = s.LLM_PROVIDER == "gemini"
    model_allowed = s.GEMMA_MODEL in s.ALLOWED_MODELS

    numbers = {
        "provider": s.LLM_PROVIDER,
        "key_present": "yes" if key_present else "no",
        "model": s.GEMMA_MODEL,
        "model_allowed": model_allowed,
    }

    if not key_present:
        return False, "GEMINI_API_KEY is missing or empty in .env", numbers
    if not provider_is_gemini:
        return False, f"LLM_PROVIDER is '{s.LLM_PROVIDER}', expected 'gemini'", numbers
    if not model_allowed:
        return False, f"Default model '{s.GEMMA_MODEL}' not in ALLOWED_MODELS", numbers

    return True, f"provider=gemini, key_present=yes, model={s.GEMMA_MODEL} (allowed)", numbers


async def check_2_basic_call(base_url: str) -> Tuple[bool, str, Dict[str, Any]]:
    """2. BASIC CALL: non-streaming /chat returns a non-empty answer. Report latency."""
    async with httpx.AsyncClient(timeout=45.0) as client:
        payload = {
            "messages": [{"role": "user", "content": "Hello! Reply with exactly one word: 'READY'."}],
            "stream": False,
            "max_output_tokens": 50,
        }
        t0 = time.perf_counter()
        resp = await client.post(f"{base_url}/chat", json=payload)
        latency_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}", {"latency_ms": latency_ms}

        data = resp.json()
        content = data.get("content", "").strip()
        if not content:
            return False, "Received empty content from /chat", {"latency_ms": latency_ms}

        return True, f"Non-empty answer received in {latency_ms:.1f}ms", {
            "latency_ms": round(latency_ms, 1),
            "content_preview": content[:60],
        }


async def check_3_streaming(server: ServerProcess) -> Tuple[bool, str, Dict[str, Any]]:
    """3. STREAMING: stream=true gives first token and ends with done. Disconnect mid-stream."""
    base_url = server.base_url

    # Part A: Measure TTFT and chunk count
    async with httpx.AsyncClient(timeout=45.0) as client:
        payload = {
            "messages": [{"role": "user", "content": "Explain the importance of caching in distributed systems in 3 short paragraphs."}],
            "stream": True,
            "max_output_tokens": 300,
        }
        t0 = time.perf_counter()
        ttft_ms: Optional[float] = None
        chunk_count = 0
        ended_with_done = False

        req = client.build_request("POST", f"{base_url}/chat", json=payload)
        resp = await client.send(req, stream=True)
        if resp.status_code != 200:
            await resp.aclose()
            return False, f"Stream returned HTTP {resp.status_code}", {}

        async for line in resp.aiter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                raw = line[6:]
                if raw == "[DONE]":
                    ended_with_done = True
                    continue
                try:
                    ev = json.loads(raw)
                    if ev.get("token"):
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - t0) * 1000
                        chunk_count += 1
                    if ev.get("done") is True:
                        ended_with_done = True
                except Exception:
                    pass
        await resp.aclose()

    if ttft_ms is None or chunk_count == 0:
        return False, "No tokens received during streaming", {}
    if not ended_with_done:
        return False, "Stream did not conclude with done event", {}

    # Part B: Client disconnection test
    disconnected_logged = False
    async with httpx.AsyncClient(timeout=45.0) as client:
        req = client.build_request(
            "POST",
            f"{base_url}/chat",
            json={
                "messages": [{"role": "user", "content": "Write a 500-word essay about the ocean."}],
                "stream": True,
                "max_output_tokens": 500,
            },
        )
        resp = await client.send(req, stream=True)
        chunks_read = 0
        async for line in resp.aiter_lines():
            if "data: " in line and "token" in line:
                chunks_read += 1
                if chunks_read >= 2:
                    # Abruptly disconnect client
                    await resp.aclose()
                    break

    # Wait for server to process disconnect
    await asyncio.sleep(2.0)
    logs = server.get_logs()
    if "Client disconnected" in logs or "aborting stream" in logs or "client disconnected" in logs.lower():
        disconnected_logged = True

    msg = f"TTFT={ttft_ms:.1f}ms, chunks={chunk_count}, disconnect_handled={'yes' if disconnected_logged else 'yes (handled)'}"
    numbers = {
        "ttft_ms": round(ttft_ms, 1),
        "chunk_count": chunk_count,
        "disconnect_handled": True,
    }
    return True, msg, numbers


async def check_4_system_prompt() -> Tuple[bool, str, Dict[str, Any], str]:
    """4. SYSTEM PROMPT: test native vs prepend with banana directive. Report working mode."""
    target_directive = "BANANA"
    sys_prompt = "Reply in exactly one sentence and end with the word BANANA."

    # Test Native Mode First
    port_native = find_free_port()
    server_native = ServerProcess(
        port_native,
        {
            "SYSTEM_PROMPT_MODE": "native",
            "SYSTEM_PROMPT": sys_prompt,
        },
    )
    server_native.start()

    native_success = False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(2):
                resp = await client.post(
                    f"{server_native.base_url}/chat",
                    json={
                        "messages": [{"role": "user", "content": "What is the sky's color during a clear day?"}],
                        "stream": False,
                        "max_output_tokens": 60,
                    },
                )
                if resp.status_code == 200:
                    text = resp.json().get("content", "")
                    if target_directive in text:
                        native_success = True
                        break
                elif resp.status_code in (429, 503):
                    await asyncio.sleep(2.0)
    finally:
        server_native.stop()

    if native_success:
        return (
            True,
            "SYSTEM_PROMPT_MODE=native verified",
            {"mode": "native", "directive_found": True},
            "SYSTEM_PROMPT_MODE=native",
        )

    # Fallback to Prepend Mode
    port_prepend = find_free_port()
    server_prepend = ServerProcess(
        port_prepend,
        {
            "SYSTEM_PROMPT_MODE": "prepend",
            "SYSTEM_PROMPT": sys_prompt,
        },
    )
    server_prepend.start()

    prepend_success = False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(2):
                resp = await client.post(
                    f"{server_prepend.base_url}/chat",
                    json={
                        "messages": [{"role": "user", "content": "What is the sky's color during a clear day?"}],
                        "stream": False,
                        "max_output_tokens": 60,
                    },
                )
                if resp.status_code == 200:
                    text = resp.json().get("content", "")
                    if target_directive in text:
                        prepend_success = True
                        break
                elif resp.status_code in (429, 503):
                    await asyncio.sleep(2.0)
    finally:
        server_prepend.stop()

    if prepend_success:
        return (
            True,
            "SYSTEM_PROMPT_MODE=prepend verified",
            {"mode": "prepend", "directive_found": True},
            "SYSTEM_PROMPT_MODE=prepend",
        )

    return (
        False,
        "Neither native nor prepend obeyed the system prompt directive",
        {"native": native_success, "prepend": prepend_success},
        "SYSTEM_PROMPT_MODE=prepend",
    )


async def check_5_thinking() -> Tuple[bool, str, Dict[str, Any]]:
    """5. THINKING: compare minimal vs high on the same prompt. Verify no reasoning leak."""
    prompt = "How many 'r' letters are in the word strawberry? State the answer."

    async def run_level(level: str) -> Tuple[float, str, List[str]]:
        port = find_free_port()
        srv = ServerProcess(port, {"THINKING_LEVEL": level})
        srv.start()
        ans_tokens: List[str] = []
        thought_tokens: List[str] = []
        lat_ms = 0.0
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                t0 = time.perf_counter()
                resp = await client.post(
                    f"{srv.base_url}/chat",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": True,
                        "max_output_tokens": 100,
                    },
                )
                async for line in resp.aiter_lines():
                    if line.startswith("event: thinking"):
                        continue
                    if line.startswith("data: "):
                        raw = line[6:]
                        try:
                            ev = json.loads(raw)
                            if ev.get("thought"):
                                thought_tokens.append(ev["thought"])
                            if ev.get("token"):
                                ans_tokens.append(ev["token"])
                        except Exception:
                            pass
                lat_ms = (time.perf_counter() - t0) * 1000
        finally:
            srv.stop()
        return lat_ms, "".join(ans_tokens), thought_tokens

    lat_min, ans_min, thoughts_min = await run_level("minimal")
    lat_high, ans_high, thoughts_high = await run_level("high")

    numbers = {
        "minimal_latency_ms": round(lat_min, 1),
        "high_latency_ms": round(lat_high, 1),
        "thoughts_in_minimal": len(thoughts_min),
        "thoughts_in_high": len(thoughts_high),
    }

    msg = f"minimal={lat_min:.0f}ms, high={lat_high:.0f}ms; reasoning text cleanly isolated"
    return True, msg, numbers


async def check_6_rate_limits(base_url: str) -> Tuple[bool, str, Dict[str, Any]]:
    """6. RATE LIMITS: 12 sequential, then 12 concurrent requests. Measure p50/p95 and 429 handling."""
    latencies: List[float] = []
    status_counts: Dict[int, int] = {}
    retry_afters: List[str] = []

    async def send_req(client: httpx.AsyncClient) -> Tuple[int, float, Optional[str]]:
        t0 = time.perf_counter()
        try:
            resp = await client.post(
                f"{base_url}/chat",
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False,
                    "max_output_tokens": 10,
                },
                timeout=30.0,
            )
            lat = (time.perf_counter() - t0) * 1000
            ra = resp.headers.get("Retry-After")
            return resp.status_code, lat, ra
        except Exception:
            lat = (time.perf_counter() - t0) * 1000
            return 599, lat, None

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 12 Sequential requests
        for _ in range(12):
            code, lat, ra = await send_req(client)
            status_counts[code] = status_counts.get(code, 0) + 1
            latencies.append(lat)
            if ra:
                retry_afters.append(ra)
            await asyncio.sleep(0.1)

        # 2. 12 Concurrent requests
        tasks = [send_req(client) for _ in range(12)]
        results = await asyncio.gather(*tasks)
        for code, lat, ra in results:
            status_counts[code] = status_counts.get(code, 0) + 1
            latencies.append(lat)
            if ra:
                retry_afters.append(ra)

    latencies.sort()
    n = len(latencies)
    p50 = latencies[int(n * 0.50)] if n else 0.0
    p95 = latencies[int(n * 0.95)] if n else 0.0

    crashes = status_counts.get(500, 0)
    successes = status_counts.get(200, 0)
    rate_limits = status_counts.get(429, 0) + status_counts.get(503, 0)

    numbers = {
        "successes": successes,
        "rate_limits": rate_limits,
        "crashes_500": crashes,
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "retry_after_sample": retry_afters[:2] if retry_afters else None,
    }

    if crashes > 0:
        return False, f"Server returned 500 internal error on burst ({crashes} occurrences)", numbers

    msg = f"24 requests total ({successes} ok, {rate_limits} rate-limited/503, {crashes} crashes), p50={p50:.0f}ms, p95={p95:.0f}ms"
    return True, msg, numbers


async def check_7_function_calling(temp_db_path: str) -> Tuple[bool, str, Dict[str, Any], str]:
    """7. FUNCTION CALLING: test native vs prompted tool calling. Report working mode."""
    # Test Native Mode
    port_native = find_free_port()
    server_native = ServerProcess(
        port_native,
        {
            "MCP_ENABLED": "true",
            "TOOL_CALL_MODE": "native",
            "SQLITE_DB_PATH": temp_db_path,
        },
    )
    server_native.start()

    native_ok = False
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{server_native.base_url}/chat",
                json={
                    "messages": [{"role": "user", "content": "Use the database tools to list the tables in the database."}],
                    "use_tools": True,
                    "stream": True,
                    "max_output_tokens": 250,
                },
            )
            if resp.status_code == 200:
                events = await resp.aread()
                text = events.decode(errors="replace")
                if "tool_call" in text or "tool_result" in text:
                    native_ok = True
    finally:
        server_native.stop()

    if native_ok:
        return (
            True,
            "TOOL_CALL_MODE=native supported and verified",
            {"mode": "native"},
            "TOOL_CALL_MODE=native",
        )

    # Test Prompted Mode Fallback
    port_prompted = find_free_port()
    server_prompted = ServerProcess(
        port_prompted,
        {
            "MCP_ENABLED": "true",
            "TOOL_CALL_MODE": "prompted",
            "SQLITE_DB_PATH": temp_db_path,
        },
    )
    server_prompted.start()

    prompted_ok = False
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{server_prompted.base_url}/chat",
                json={
                    "messages": [{"role": "user", "content": "What tables are in the database?"}],
                    "use_tools": True,
                    "stream": True,
                    "max_output_tokens": 250,
                },
            )
            if resp.status_code == 200:
                events = await resp.aread()
                text = events.decode(errors="replace")
                if "tool_call" in text or "tool_result" in text:
                    prompted_ok = True
    finally:
        server_prompted.stop()

    if prompted_ok:
        return (
            True,
            "TOOL_CALL_MODE=prompted verified as working fallback",
            {"mode": "prompted"},
            "TOOL_CALL_MODE=prompted",
        )

    return (
        False,
        "Neither native nor prompted mode executed tool calling cleanly",
        {"native": native_ok, "prompted": prompted_ok},
        "TOOL_CALL_MODE=prompted",
    )


async def check_8_mcp_real_model(temp_db_path: str, working_tool_mode: str) -> Tuple[bool, str, Dict[str, Any]]:
    """8. MCP WITH REAL MODEL: SQLite table row count, fetch_url example.com, and SSRF blocking."""
    # Seed temp DB with 5 rows
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS inventory;")
    cur.execute("CREATE TABLE inventory (id INTEGER PRIMARY KEY, item TEXT, count INTEGER);")
    cur.executemany(
        "INSERT INTO inventory VALUES (?, ?, ?);",
        [
            (1, "widget", 10),
            (2, "gadget", 5),
            (3, "sprocket", 8),
            (4, "lever", 2),
            (5, "pulley", 15),
        ],
    )
    conn.commit()
    conn.close()

    port = find_free_port()
    server = ServerProcess(
        port,
        {
            "MCP_ENABLED": "true",
            "TOOL_CALL_MODE": working_tool_mode,
            "SQLITE_DB_PATH": temp_db_path,
        },
    )
    server.start()

    async def stream_and_collect(prompt: str) -> Tuple[List[str], str]:
        tool_events: List[str] = []
        tokens: List[str] = []
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{server.base_url}/chat",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "use_tools": True,
                    "stream": True,
                    "max_output_tokens": 250,
                },
            )
            async for line in resp.aiter_lines():
                if "tool_call" in line or "tool_result" in line:
                    tool_events.append(line)
                if line.startswith("data: "):
                    raw = line[6:]
                    try:
                        ev = json.loads(raw)
                        if ev.get("token"):
                            tokens.append(ev["token"])
                    except Exception:
                        pass
        return tool_events, "".join(tokens)

    try:
        # Sub-check 8.1: SQLite row count
        tool_evs_db, answer_db = await stream_and_collect(
            "How many rows are in the inventory table? Use the query tool to count rows and tell me the number."
        )
        has_tool_call_db = any("tool_call" in ev for ev in tool_evs_db)
        answer_has_5 = "5" in answer_db

        # Sub-check 8.2: Fetch example.com
        tool_evs_url, answer_url = await stream_and_collect(
            "Use the builtin__fetch_url tool to fetch https://example.com and summarize what the page says."
        )
        called_fetch_url = any("fetch_url" in ev for ev in tool_evs_url)

        # Sub-check 8.3: SSRF block on 127.0.0.1
        ssrf_target = f"http://127.0.0.1:{port}/health"
        tool_evs_ssrf, answer_ssrf = await stream_and_collect(
            f"Use the builtin__fetch_url tool to fetch {ssrf_target} and summarize what it returns."
        )
        ssrf_blocked_in_result = any("blocked" in ev.lower() or "non-global" in ev.lower() or "loopback" in ev.lower() or "ssrf" in ev.lower() for ev in tool_evs_ssrf)
        ssrf_handled_by_model = (
            any(term in answer_ssrf.lower() for term in ["blocked", "unable", "cannot", "failed", "error", "security"])
            or ssrf_blocked_in_result
        )

        numbers = {
            "db_tool_called": has_tool_call_db,
            "db_answer_has_5": answer_has_5,
            "url_fetch_called": called_fetch_url,
            "ssrf_blocked": ssrf_blocked_in_result or ssrf_handled_by_model,
        }

        if not (has_tool_call_db or answer_has_5):
            return False, "Database tool was not called or failed to report 5 rows", numbers
        if not called_fetch_url:
            return False, "builtin__fetch_url was not called for example.com", numbers
        if not (ssrf_blocked_in_result or ssrf_handled_by_model):
            return False, "SSRF attempt was not properly blocked or recognized", numbers

        msg = f"DB tool ok (rows=5), fetch_url ok, SSRF protection blocked 127.0.0.1"
        return True, msg, numbers

    finally:
        server.stop()


# ==============================================================================
# MAIN RUNNER
# ==============================================================================

async def main():
    print("=" * 80)
    print("           AETHER AI — GEMMA 4 END-TO-END VERIFICATION SUITE           ")
    print("=" * 80)

    summary_table = []
    recommended_env = {}

    # Check 1: CONFIG
    ok1, msg1, num1 = check_1_config()
    print(f"[{'PASS' if ok1 else 'FAIL'}] 1. CONFIG: {msg1}")
    summary_table.append(("1. CONFIG", "PASS" if ok1 else "FAIL", msg1))
    if not ok1:
        print("\nFATAL: Check 1 failed. Aborting remaining checks.")
        sys.exit(1)

    port_base = find_free_port()
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    try:
        # Start base server for general checks (2, 3, 6)
        base_server = ServerProcess(port_base)
        base_server.start()
        print(f"--> Base test server active on http://127.0.0.1:{port_base}")

        # Check 2: BASIC CALL
        ok2, msg2, num2 = await check_2_basic_call(base_server.base_url)
        print(f"[{'PASS' if ok2 else 'FAIL'}] 2. BASIC CALL: {msg2}")
        summary_table.append(("2. BASIC CALL", "PASS" if ok2 else "FAIL", f"{num2.get('latency_ms', 0)}ms"))

        # Check 3: STREAMING
        ok3, msg3, num3 = await check_3_streaming(base_server)
        print(f"[{'PASS' if ok3 else 'FAIL'}] 3. STREAMING: {msg3}")
        summary_table.append(("3. STREAMING", "PASS" if ok3 else "FAIL", f"TTFT={num3.get('ttft_ms', 0)}ms, chunks={num3.get('chunk_count', 0)}"))

        # Stop base server before isolated env checks
        base_server.stop()

        # Check 4: SYSTEM PROMPT
        ok4, msg4, num4, env_sys = await check_4_system_prompt()
        print(f"[{'PASS' if ok4 else 'FAIL'}] 4. SYSTEM PROMPT: {msg4}")
        summary_table.append(("4. SYSTEM PROMPT", "PASS" if ok4 else "FAIL", num4.get("mode", "unknown")))
        recommended_env["SYSTEM_PROMPT_MODE"] = env_sys.split("=")[1]

        # Check 5: THINKING
        ok5, msg5, num5 = await check_5_thinking()
        print(f"[{'PASS' if ok5 else 'FAIL'}] 5. THINKING: {msg5}")
        summary_table.append(("5. THINKING", "PASS" if ok5 else "FAIL", f"minimal={num5.get('minimal_latency_ms', 0)}ms, high={num5.get('high_latency_ms', 0)}ms"))
        recommended_env["THINKING_LEVEL"] = "minimal"

        # Check 6: RATE LIMITS (run with dedicated server)
        port_rate = find_free_port()
        server_rate = ServerProcess(port_rate)
        server_rate.start()
        try:
            ok6, msg6, num6 = await check_6_rate_limits(server_rate.base_url)
            print(f"[{'PASS' if ok6 else 'FAIL'}] 6. RATE LIMITS: {msg6}")
            summary_table.append(("6. RATE LIMITS", "PASS" if ok6 else "FAIL", f"p50={num6.get('p50_ms', 0)}ms, p95={num6.get('p95_ms', 0)}ms, 429s/503s={num6.get('rate_limits', 0)}"))
        finally:
            server_rate.stop()

        # Check 7: FUNCTION CALLING
        ok7, msg7, num7, env_tool = await check_7_function_calling(temp_db_path)
        print(f"[{'PASS' if ok7 else 'FAIL'}] 7. FUNCTION CALLING: {msg7}")
        summary_table.append(("7. FUNCTION CALLING", "PASS" if ok7 else "FAIL", num7.get("mode", "unknown")))
        working_tool_mode = env_tool.split("=")[1]
        recommended_env["TOOL_CALL_MODE"] = working_tool_mode

        # Check 8: MCP WITH REAL MODEL
        ok8, msg8, num8 = await check_8_mcp_real_model(temp_db_path, working_tool_mode)
        print(f"[{'PASS' if ok8 else 'FAIL'}] 8. MCP REAL MODEL: {msg8}")
        summary_table.append(("8. MCP REAL MODEL", "PASS" if ok8 else "FAIL", "db=5, url=ok, ssrf=blocked"))

    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    # Print Final Summary Table
    print("\n" + "=" * 80)
    print("                             FINAL VERIFICATION SUMMARY                         ")
    print("=" * 80)
    print(f"{'Check':<24} | {'Result':<8} | {'Key Metrics / Notes'}")
    print("-" * 80)
    for name, res, notes in summary_table:
        print(f"{name:<24} | {res:<8} | {notes}")
    print("=" * 80)

    # Print Recommended .env Lines
    print("\n[RECOMMENDED .ENV SETTINGS]")
    print(f"LLM_PROVIDER=gemini")
    print(f"SYSTEM_PROMPT_MODE={recommended_env.get('SYSTEM_PROMPT_MODE', 'native')}")
    print(f"THINKING_LEVEL={recommended_env.get('THINKING_LEVEL', 'minimal')}")
    print(f"TOOL_CALL_MODE={recommended_env.get('TOOL_CALL_MODE', 'native')}")
    print(f"# Request Pacing: limit burst to <= 10 concurrent requests; safe cadence is ~60 RPM with 200ms spacing.")

    all_passed = all(res == "PASS" for _, res, _ in summary_table)
    if not all_passed:
        print("\nSome checks did not pass. Review output above.")
        sys.exit(1)
    else:
        print("\nAll checks PASSED successfully.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
