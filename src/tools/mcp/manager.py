from src.config.config import Config
from src.tools.mcp.client import MCPClient, MCPClientStatus
from typing import Dict
import asyncio
from src.utils.logger import logger
from src.tools.registry import ToolRegistry
from src.tools.mcp.tool import MCPTool

class MCPManager:
    def __init__(self, config: Config):
        self._config = config
        self._clients: Dict[str, MCPClient] = {}
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        mcp_configs = self._config.mcp_servers
        if not mcp_configs:
            return
        for name, server_config in mcp_configs.items():
            if not server_config.enabled:
                continue
            self._clients[name] = MCPClient(name, server_config, self._config.cwd)
        asyncio.gather(*[asyncio.wait_for(client.connect(), timeout=server_config.startup_timeout_sec) for client in self._clients.values()], return_exceptions=True)
        self._initialized = True
        logger.info(f"MCP servers initialized successfully")

    def register_tools(self, registry: ToolRegistry) -> None:
        if not self._initialized:
            raise ValueError("MCP servers not initialized")
        count = 0
        for client in self._clients.values():
            if client.status != MCPClientStatus.CONNECTED:
                continue
            for tool_info in client.tools:
                tool = MCPTool(
                    config=self._config,
                    name="client_" + tool_info.server_name + "_tool_" + tool_info.name,
                    tool_info=tool_info,
                    client=client
                )
                registry.register_mcp_tool(tool)
                count += 1
        logger.info(f"Registered {count} MCP tools")


    async def shutdown(self) -> None:
        await asyncio.gather(*[asyncio.wait_for(client.disconnect(), timeout=10.0) for client in self._clients.values()], return_exceptions=True)
        self._clients.clear()
        self._initialized = False