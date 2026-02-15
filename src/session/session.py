from src.config.config import Config
from src.context.manager import ContextManager
from src.client.llm_client import LLMClient
from src.tools.registry import create_default_registry, ToolRegistry
import uuid
from datetime import datetime
from src.tools.discovery import ToolDiscoveryManager

class Session:
    def __init__(self, config: Config) -> None:
        self.session_id = str(uuid.uuid4())
        self._config = config
        self._client = LLMClient(self._config)
        self._context_manager = ContextManager(self._config)
        self._tool_registry: ToolRegistry = create_default_registry(self._config)
        self._tool_discovery_manager = ToolDiscoveryManager(self._config, self._tool_registry)
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self._turn_count = 0


        self._tool_discovery_manager.discover()

    async def increment_turn(self) -> None:
        self._turn_count += 1
        self.updated_at = datetime.now()
        # return updated turn count
        return self._turn_count