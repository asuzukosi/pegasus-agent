from pegasus.config.config import Config
from pegasus.context.compaction import ChatCompressor
from pegasus.context.manager import ContextManager
from pegasus.client.llm_client import LLMClient
from pegasus.mcp.manager import MCPManager
from pegasus.tools.registry import create_default_registry, ToolRegistry
import uuid
from datetime import datetime

class Session:
    def __init__(self, config: Config, tool_registry: ToolRegistry | None = None) -> None:
        self.session_id = str(uuid.uuid4())
        self.config = config
        self.client = LLMClient(self.config)
        self.chat_compressor = ChatCompressor(self.client)
        self.context_manager: ContextManager | None = None
        self.tool_registry: ToolRegistry | None = tool_registry
        self.mcp_manager = MCPManager(self.config)
        self.config.mcp_manager = self.mcp_manager
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.turn_count = 0

    async def initialize(self) -> None:
        await self.mcp_manager.initialize()
        if self.tool_registry is None:
            self.tool_registry = create_default_registry(self.config)
        self.context_manager = ContextManager(self.config)

    async def increment_turn(self) -> None:
        self.turn_count += 1
        self.updated_at = datetime.now()
        return self.turn_count
    

    async def get_stats(self) -> dict[str, str]:
        return {
            "turn_count": self.turn_count,
            "updated_at": self.updated_at.isoformat(),
            "created_at": self.created_at.isoformat(),

        }

    async def cleanup(self) -> None:
        if self.tool_registry is not None:
            await self.tool_registry.cleanup()
        await self.mcp_manager.shutdown()
        self.config.mcp_manager = None
        await self.client.close()
    
    