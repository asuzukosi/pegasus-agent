from src.config.config import MCPServerConfig
from pathlib import Path
import os
from src.utils.logger import logger
from enum import Enum
from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport
from typing import Dict, Any, List
from dataclasses import dataclass, field

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
    def __init__(self, name, mcp_config: MCPServerConfig, cwd: Path):
        self.name = name
        self.mcp_config = mcp_config
        self.cwd = cwd
        self.status = MCPClientStatus.DISCONNECTED
        self._client: Client | None = None
        self._tools: Dict[str, MCPToolInfo] = {}


    @property
    def tools(self) -> List[MCPToolInfo]:
        return [v for v in self._tools.values()]
    
    def _create_transport(self) -> SSETransport | StdioTransport:
        if self.mcp_config.command:
            all_envs = os.environ.copy()
            all_envs.update(self.mcp_config.env)
            cwd = self.cwd.as_posix() if self.cwd else self.mcp_config.cwd.as_posix()
            return StdioTransport(self.mcp_config.command, self.mcp_config.args, all_envs, cwd)
        elif self.mcp_config.url:
            return SSETransport(self.mcp_config.url)
        else:
            raise ValueError("No transport provided")
        
    async def connect(self) -> None:
        if self.status == MCPClientStatus.CONNECTED:
            logger.warning(f"MCP server {self.name} is already connected")
            return
        self.status = MCPClientStatus.CONNECTING
        try:
            self.client = Client(transport=self._create_transport()) 
            await self.client.__aenter__()
            # discover the tools from the mcp server
            tools = await self.client.list_tools()
            for tool in tools:
                self._tools[tool.name] = MCPToolInfo(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=self.name
                )
            self.status = MCPClientStatus.CONNECTED
            logger.info(f"MCP server {self.name} connected successfully")
        except Exception as e:
            self.status = MCPClientStatus.ERROR
            logger.error(f"Failed to connect to MCP server {self.name}: {e}")
            raise e
    
    async def disconnect(self) -> None:
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None
            self._tools.clear()
            self.status = MCPClientStatus.DISCONNECTED
            logger.info(f"MCP server {self.name} disconnected successfully")
        else:
            logger.warning(f"MCP server {self.name} is not connected")

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        if self.client is None or self.status != MCPClientStatus.CONNECTED:
            raise RuntimeError("MCP server is not connected")
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not found in MCP server {self.name}")
        result = await self.client.call_tool(tool_name, params)
        output = []
        for item in result.content:
            if hasattr(item, "text"):
                output.append(item.text)
            else:
                output.append(str(item))

        return {"output": "\n".join(output), "is_error": result.is_error}
        