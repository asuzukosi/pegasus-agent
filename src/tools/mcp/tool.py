from src.tools.base import Tool
from typing import Any
from src.tools.base import ToolType
from src.tools.data import ToolInvocation, ToolResult
from src.config.config import Config
from src.tools.mcp.client import MCPToolInfo, MCPClient

class MCPTool(Tool):
    type: ToolType = ToolType.MCP

    def __init__(self, config: Config, name: str, tool_info: MCPToolInfo, client: MCPClient):
        self._config = config
        self.name = name
        self.description = tool_info.description
        self._input_schema = tool_info.input_schema
        self._tool_info = tool_info
        self._client = client # used for calling the tool

    @property
    def schema(self) -> dict[str, Any]:
        return  {
            "type": "object",
            "properties": self._input_schema.get("properties", {}),
            "required": self._input_schema.get("required", []),
        }
        

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return True

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        result = await self._client.call_tool(self.name, invocation.params)
        if result["is_error"]:
            return ToolResult.error_result(result["output"])
        return ToolResult.success_result(result["output"])

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error executing MCP tool with error: {e}")
