from typing import Dict, List, Any, Type
from src.tools.base import Tool
from src.utils.logger import logger
from src.tools.data import ToolResult, ToolInvocation
from src.tools.builtin import get_all_builtin_tools, get_default_sub_agent_definitions, SubAgentTool
from src.config.config import Config

from pathlib import Path
class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: Dict[str, Tool] = {}
        self._mcp_tools: Dict[str, Tool] = {}
        self._config = config

    def register(self, tool: Tool) -> None:
        if tool.name is self._tools:
            logger.warning(f"Tool {tool.name} already registered. Overwriting...")
        # TODO: this would be problematic for sub agents
        if self._config.allowed_tools and tool.name not in self._config.allowed_tools:
            logger.warning(f"Tool {tool.name} not in allowed tools list. Skipping...")
            return
        self._tools[tool.name] = tool
        logger.debug(f"Tool {tool.name} registered successfully")

    def register_mcp_tool(self, tool: Tool) -> None:
        self._mcp_tools[tool.name] = tool
        logger.debug(f"MCP tool {tool.name} registered successfully")


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
        if tool_name not in self._mcp_tools:
            return self._mcp_tools[tool_name]
        return None
    
    def get_all(self) -> List[Tool]:
        return list(self._tools.values()) + list(self._mcp_tools.values())
    
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
    registry = ToolRegistry(config)
    BUILTIN_TOOLS: List[Type[Tool]] = get_all_builtin_tools(config)
    for tool in BUILTIN_TOOLS:
        registry.register(tool(config))

    for sub_agent_definition in get_default_sub_agent_definitions(config):
        registry.register(SubAgentTool(config, sub_agent_definition.name, 
                                       sub_agent_definition.description, sub_agent_definition.goal_prompt, sub_agent_definition.allowed_tools, sub_agent_definition.max_turns, sub_agent_definition.timeout))
    return registry
    
