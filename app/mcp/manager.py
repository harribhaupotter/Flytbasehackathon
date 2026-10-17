import os
import sys
import re
import json
import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, Any, List, Optional

from app.config import settings

logger = logging.getLogger("aether.mcp.manager")


class McpManager:
    """
    Manages connections to external MCP servers, tool discovery, and tool execution.
    Lifecycle is tied to the FastAPI lifespan using a shared AsyncExitStack.
    """

    def __init__(self, exit_stack: AsyncExitStack, config_path: Optional[str] = None):
        self.exit_stack = exit_stack
        self.config_path = config_path or settings.MCP_CONFIG_PATH
        # Mapping: namespaced_name -> dict(session, original_name, description, input_schema)
        self._tools: Dict[str, Dict[str, Any]] = {}
        self.connected_servers = 0
        self.failed_servers = 0

    def _interpolate_value(self, val: Any, settings_dict: Dict[str, Any]) -> Any:
        if not isinstance(val, str):
            return val

        def replacer(match):
            var_name = match.group(1) or match.group(2)
            if var_name in settings_dict:
                return str(settings_dict[var_name])
            return os.environ.get(var_name, "")

        return re.sub(r"\$\{([A-Za-z0-9_]+)\}|\$([A-Za-z0-9_]+)", replacer, val)

    async def start(self) -> None:
        """Reads configuration and connects to all configured MCP servers."""
        if not os.path.exists(self.config_path):
            logger.warning(f"MCP configuration file not found at: {self.config_path}")
            logger.info("MCP startup: 0/0 servers connected, 0 tools discovered.")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as err:
            logger.error(f"Failed to load MCP config {self.config_path}: {err}")
            return

        servers: Dict[str, Any] = config_data.get("servers", {})
        total_servers = len(servers)
        settings_dict = settings.model_dump()

        # Lazy imports of MCP client libraries inside the enabled branch
        from mcp.client.session import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.sse import sse_client

        for server_name, srv_config in servers.items():
            transport = srv_config.get("transport", "stdio").lower()
            try:
                # Enforce 10s connect timeout per server
                async def _connect_server():
                    if transport == "stdio":
                        cmd = srv_config.get("command", "python")
                        if cmd in ("python", "${PYTHON}", "$PYTHON"):
                            cmd = sys.executable

                        args = [
                            self._interpolate_value(arg, settings_dict)
                            for arg in srv_config.get("args", [])
                        ]
                        raw_env = srv_config.get("env", {})
                        server_env = {
                            k: self._interpolate_value(v, settings_dict)
                            for k, v in raw_env.items()
                        }
                        # Include existing PATH and environment variables
                        full_env = {**os.environ, **server_env}
                        cwd = os.path.abspath(os.getcwd())

                        params = StdioServerParameters(
                            command=cmd,
                            args=args,
                            env=full_env,
                            cwd=cwd,
                        )

                        read_stream, write_stream = await self.exit_stack.enter_async_context(
                            stdio_client(params)
                        )
                        session = await self.exit_stack.enter_async_context(
                            ClientSession(read_stream, write_stream)
                        )
                        await session.initialize()
                        return session

                    elif transport in ("sse", "http"):
                        url = self._interpolate_value(srv_config.get("url", ""), settings_dict)
                        headers = {
                            k: self._interpolate_value(v, settings_dict)
                            for k, v in srv_config.get("headers", {}).items()
                        }
                        read_stream, write_stream = await self.exit_stack.enter_async_context(
                            sse_client(url=url, headers=headers)
                        )
                        session = await self.exit_stack.enter_async_context(
                            ClientSession(read_stream, write_stream)
                        )
                        await session.initialize()
                        return session
                    else:
                        raise ValueError(f"Unsupported transport: {transport}")

                session = await asyncio.wait_for(_connect_server(), timeout=10.0)

                # Discover and namespace tools
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    # Sanitize server and tool names: [A-Za-z0-9_-] and cap to 64 chars
                    raw_namespaced = f"{server_name}__{tool.name}"
                    namespaced_name = re.sub(r"[^A-Za-z0-9_-]", "_", raw_namespaced)[:64]

                    # Filter through MCP_ALLOWED_TOOLS if configured
                    if settings.MCP_ALLOWED_TOOLS:
                        allowed = (
                            namespaced_name in settings.MCP_ALLOWED_TOOLS
                            or tool.name in settings.MCP_ALLOWED_TOOLS
                        )
                        if not allowed:
                            continue

                    self._tools[namespaced_name] = {
                        "session": session,
                        "original_name": tool.name,
                        "description": tool.description or "",
                        "input_schema": getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {},
                    }

                self.connected_servers += 1

            except Exception as err:
                self.failed_servers += 1
                logger.warning(f"MCP server '{server_name}' failed to start or connect: {err}")

        # Log one clean startup summary line
        logger.info(
            f"MCP startup: {self.connected_servers}/{total_servers} servers connected, "
            f"{len(self._tools)} tools discovered."
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        """Returns discovered tool definitions."""
        return [
            {
                "name": name,
                "description": info["description"],
                "input_schema": info["input_schema"],
            }
            for name, info in self._tools.items()
        ]

    async def call_tool(self, namespaced_name: str, arguments: Dict[str, Any]) -> str:
        """
        Invokes an MCP tool with a timeout cap.
        Catches exceptions and returns error text to the model rather than raising.
        """
        tool_entry = self._tools.get(namespaced_name)
        if not tool_entry:
            for entry in self._tools.values():
                if entry["original_name"] == namespaced_name:
                    tool_entry = entry
                    break
        if not tool_entry:
            for k, entry in self._tools.items():
                if k.endswith(f"__{namespaced_name}"):
                    tool_entry = entry
                    break
        if not tool_entry:
            return f"Error: Tool '{namespaced_name}' is not recognized."

        session: Any = tool_entry["session"]
        original_name: str = tool_entry["original_name"]

        try:
            result = await asyncio.wait_for(
                session.call_tool(original_name, arguments=arguments),
                timeout=settings.TOOL_TIMEOUT_SECONDS,
            )

            text_pieces = []
            if hasattr(result, "content"):
                for block in result.content:
                    if hasattr(block, "text"):
                        text_pieces.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        text_pieces.append(block["text"])
                    else:
                        text_pieces.append(str(block))
            else:
                text_pieces.append(str(result))

            full_result = "\n".join(text_pieces)
            if len(full_result) > settings.MAX_TOOL_RESULT_CHARS:
                full_result = full_result[: settings.MAX_TOOL_RESULT_CHARS] + "\n...[truncated]"

            return full_result or "Tool executed with no output."

        except asyncio.TimeoutError:
            logger.warning(f"Tool call {namespaced_name} timed out after {settings.TOOL_TIMEOUT_SECONDS}s")
            return f"Error: Tool '{namespaced_name}' timed out after {settings.TOOL_TIMEOUT_SECONDS}s."
        except Exception as exc:
            logger.warning(f"Tool call {namespaced_name} failed: {exc}")
            return f"Error executing tool '{namespaced_name}': {exc}"
