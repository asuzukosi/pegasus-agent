from __future__ import annotations

from typing import Dict, List, Any, Type
from src.tools.base import Tool
from src.utils.logger import logger
from src.tools.data import ToolResult, ToolInvocation
from src.tools.builtin import get_all_builtin_tools
from src.config.config import Config
from pathlib import Path


class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: Dict[str, Tool] = {}
        self._config = config

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"[tool registry] tool {tool.name} already registered. overwriting...")
        self._tools[tool.name] = tool
        logger.info(f"[tool registry] tool {tool.name} activated🔥")


    def unregister(self, tool_name: str) -> bool:
        if tool_name not in self._tools:
            logger.warning(f"tool {tool_name} not found in registry")
            return False
        del self._tools[tool_name]
        logger.debug(f"tool {tool_name} unregistered successfully")
        return True
    
    def get_schemas(self) -> List[dict[str, Any]]:
        tools = self.get_all()
        return [tool.to_openai_schema() for tool in tools]

    def get(self, tool_name: str) -> Tool | None:
        if tool_name in self._tools:
            return self._tools[tool_name]
        return None
    
    def get_all(self) -> List[Tool]:
        return list(self._tools.values())
    
    async def invoke(self, name: str, params: Dict[str, Any], cwd: Path) -> ToolResult:
        tool: Tool | None = self.get(name)
        if tool is None:
            return ToolResult.error_result(f"tool {name} not found in registry")

        validation_errors = tool.validate_params(params)
        if validation_errors:
            return ToolResult.error_result(f"validation errors: {'; '.join(validation_errors)}", metadata=dict(tool_name=name, validation_errors=validation_errors))
        tool_invocation = ToolInvocation(cwd=cwd, params=params)
        try:
            result = await tool.execute(tool_invocation)
            return result
        except Exception as e:
            logger.exception(f"error invoking tool {name} with error: {e}")
            return ToolResult.error_result(f"internal error while invoking tool {name}: {e}")

    async def cleanup(self) -> None:
        seen_ids: set[int] = set()
        for tool in self.get_all():
            tool_id = id(tool)
            if tool_id in seen_ids:
                continue
            seen_ids.add(tool_id)
            close = getattr(tool, "close", None)
            if close is None:
                continue
            try:
                await close()
            except Exception as e:
                logger.warning(f"error cleaning up tool {tool.name}: {e}")
        

def create_default_registry(config: Config) -> ToolRegistry:
    registry = ToolRegistry(config)
    BUILTIN_TOOLS: List[Type[Tool]] = get_all_builtin_tools()
    for tool in BUILTIN_TOOLS:
        registry.register(tool(config))
    return registry
    
