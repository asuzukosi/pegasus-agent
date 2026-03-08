import asyncio
from typing import Dict

from src.config.config import Config
from src.mcp.client import MCPClient, MCPClientStatus
from src.utils.logger import logger


class MCPManager:
    def __init__(self, config: Config):
        self._config = config
        self._clients: Dict[str, MCPClient] = {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def connected_clients(self) -> Dict[str, MCPClient]:
        return {
            name: client
            for name, client in self._clients.items()
            if client.status == MCPClientStatus.CONNECTED
        }

    async def initialize(self) -> None:
        if self._initialized:
            return
        mcp_configs = self._config.mcp_servers
        if not mcp_configs:
            logger.info("[mcp manager] no mcp servers configured🤔")
            self._initialized = True
            return
        for name, server_config in mcp_configs.items():
            if not server_config.enabled:
                logger.info(f"[mcp manager] mcp server {name} disabled, skipping startup🚀")
                continue
            self._clients[name] = MCPClient(name, server_config, self._config.cwd)
        if not self._clients:
            logger.info("[mcp manager] no enabled mcp servers to start🚀")
            self._initialized = True
            return

        client_names = list(self._clients.keys())
        connect_tasks = [
            asyncio.wait_for(
                self._clients[name].connect(),
                timeout=mcp_configs[name].startup_timeout_sec,
            )
            for name in client_names
        ]
        results = await asyncio.gather(*connect_tasks, return_exceptions=True)
        connected_count = 0
        failed_count = 0
        for name, result in zip(client_names, results, strict=False):
            client = self._clients[name]
            if isinstance(result, Exception):
                failed_count += 1
                logger.error(f"[mcp manager] mcp server {name} failed to initialize💣: {result}")
                continue
            if client.status == MCPClientStatus.CONNECTED:
                connected_count += 1
                logger.info(f"[mcp manager] {name} mcp initialized with {len(client.tools)} tools🚀")
                continue
            failed_count += 1
            logger.warning(f"[mcp manager] mcp server {name} finished startup with status {client.status}💣")
        self._initialized = True
        summary_emoji = "💣" if failed_count else "🚀"
        logger.info(f"[mcp manager] startup complete: {connected_count} connected, {failed_count} failed{summary_emoji}")

    async def shutdown(self) -> None:
        await asyncio.gather(
            *[asyncio.wait_for(client.disconnect(), timeout=10.0) for client in self._clients.values()],
            return_exceptions=True,
        )
        self._clients.clear()
        self._initialized = False
