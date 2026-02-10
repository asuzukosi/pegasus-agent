from typing import Dict, List, Any, Type
from src.tools.base import Tool
from src.utils.logger import logger
from src.tools.data import ToolResult, ToolInvocation
from src.tools.builtin import get_all_builtin_tools
from src.config.config import Config

from pathlib import Path
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name is self._tools:
            logger.warning(f"Tool {tool.name} already registered. Overwriting...")
        self._tools[tool.name] = tool
        logger.debug(f"Tool {tool.name} registered successfully")

    def unregister(self, tool_name: str) -> bool:
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} not found in registry")
            return False
        del self._tools[tool_name]
        logger.debug(f"Tool {tool_name} unregistered successfully")
        return True
    
    def get_schemas(self) -> List[dict[str, Any]]:
        tools = self.get_all()
        return [tool.to_openai_schema() for tool in tools]

    def get(self, tool_name: str) -> Tool | None:
        if tool_name not in self._tools:
            return self._tools[tool_name]
        return None
    
    def get_all(self) -> List[Tool]:
        return list(self._tools.values())
    
    async def invoke(self, name: str, params: Dict[str, Any], cwd: Path) -> ToolResult:
        tool: Tool | None = self.get(name)
        if tool is None:
            return ToolResult.error_result(f"Tool {name} not found in registry")
        validation_errors = tool.validate_params(params)
        if validation_errors:
            return ToolResult.error_result(f"Validation errors: {'; '.join(validation_errors)}", metadata=dict(tool_name=name, validation_errors=validation_errors))
        tool_invocation = ToolInvocation(cwd=cwd, params=params)
        try:
            result = await tool.execute(tool_invocation)
            return result
        except Exception as e:
            logger.exception(f"Error invoking tool {name} with error: {e}")
            return ToolResult.error_result(f"internal error while invoking tool {name}: {e}")
        

def create_default_registry(config: Config) -> ToolRegistry:
    registry = ToolRegistry()
    BUILTIN_TOOLS: List[Type[Tool]] = get_all_builtin_tools(config)
    for tool in BUILTIN_TOOLS:
        registry.register(tool(config))
    return registry
    
