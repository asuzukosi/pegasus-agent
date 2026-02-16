from src.config.config import Config
from src.context.manager import ContextManager
from src.client.llm_client import LLMClient
from src.tools.registry import create_default_registry, ToolRegistry
import uuid
from datetime import datetime
from src.tools.discovery import ToolDiscoveryManager
from src.tools.mcp.manager import MCPManager
from src.context.compaction import ChatCompressor
from src.security.approvals import ApprovalManager
from src.tools.data import ToolConfirmation
from typing import Callable, Awaitable
from src.hooks.hooks_system import HookSystem
from src.context.loop_detector import LoopDetector

class Session:
    def __init__(self, config: Config, confirmation_callback: Callable[[ToolConfirmation], Awaitable[bool]] | None = None) -> None:
        self.session_id = str(uuid.uuid4())
        self._config = config
        self._client = LLMClient(self._config)
        self._context_manager: ContextManager | None = None
        self._tool_registry: ToolRegistry = create_default_registry(self._config)
        self._tool_discovery_manager = ToolDiscoveryManager(self._config, self._tool_registry)
        self._mcp_manager = MCPManager(self._config)
        self._chat_compressor = ChatCompressor(self._client)
        self._approval_manager = ApprovalManager(self._config, confirmation_callback)
        self._hooks_system = HookSystem(self._config)
        self._loop_detector = LoopDetector()
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self._turn_count = 0

    async def initialize(self) -> None:
        await self._mcp_manager.initialize()
        self._tool_discovery_manager.discover()
        self._mcp_manager.register_tools(self._tool_registry)
        self._context_manager = ContextManager(self._config)

    async def increment_turn(self) -> None:
        self._turn_count += 1
        self.updated_at = datetime.now()
        # return updated turn count
        return self._turn_count
    

    async def get_stats(self) -> dict[str, str]:
        return {
            "turn_count": self._turn_count,
            "updated_at": self.updated_at.isoformat(),
            "created_at": self.created_at.isoformat(),

        }
    
    