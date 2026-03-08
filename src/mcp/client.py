from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List
import os

from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport

from src.config.config import MCPServerConfig


class MCPClientStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""


class MCPClient:
    def __init__(self, name: str, mcp_config: MCPServerConfig, cwd: Path):
        self.name = name
        self.mcp_config = mcp_config
        self.cwd = cwd
        self.status = MCPClientStatus.DISCONNECTED
        self.client: Client | None = None
        self._tools: Dict[str, MCPToolInfo] = {}

    @property
    def tools(self) -> List[MCPToolInfo]:
        return [value for value in self._tools.values()]

    def _resolve_server_cwd(self) -> Path:
        if self.mcp_config.cwd is None:
            return self.cwd.resolve()
        if self.mcp_config.cwd.is_absolute():
            return self.mcp_config.cwd.resolve()
        return (self.cwd / self.mcp_config.cwd).resolve()

    def _create_transport(self) -> SSETransport | StdioTransport:
        if self.mcp_config.command:
            all_envs = os.environ.copy()
            all_envs.update(self.mcp_config.env)
            cwd = self._resolve_server_cwd().as_posix()
            return StdioTransport(self.mcp_config.command, self.mcp_config.args, all_envs, cwd)
        if self.mcp_config.url:
            return SSETransport(self.mcp_config.url)
        raise ValueError("No transport provided")

    async def connect(self) -> None:
        if self.status == MCPClientStatus.CONNECTED:
            return
        self.status = MCPClientStatus.CONNECTING
        try:
            self.client = Client(transport=self._create_transport())
            await self.client.__aenter__()
            tools = await self.client.list_tools()
            self._tools.clear()
            for tool in tools:
                self._tools[tool.name] = MCPToolInfo(
                    name=tool.name,
                    description=getattr(tool, "description", "") or "",
                    input_schema=getattr(tool, "inputSchema", {}) or {},
                    server_name=self.name,
                )
            self.status = MCPClientStatus.CONNECTED
        except Exception:
            self.status = MCPClientStatus.ERROR
            raise

    async def disconnect(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None
        self._tools.clear()
        self.status = MCPClientStatus.DISCONNECTED

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.client is None or self.status != MCPClientStatus.CONNECTED:
            raise RuntimeError("mcp server is not connected")
        if tool_name not in self._tools:
            raise ValueError(f"tool {tool_name} not found in mcp server {self.name}")
        result = await self.client.call_tool(tool_name, params)
        output: list[str] = []
        for item in getattr(result, "content", []) or []:
            if hasattr(item, "text") and item.text:
                output.append(item.text)
            elif hasattr(item, "data") and item.data is not None:
                output.append(str(item.data))
            else:
                output.append(str(item))
        return {
            "output": "\n".join(output).strip(),
            "is_error": getattr(result, "is_error", False),
            "raw_content": output,
        }
