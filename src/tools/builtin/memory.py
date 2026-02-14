from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from enum import Enum
from pathlib import Path
import json

class MemoryAction(str, Enum):
    SET = "set"
    GET = "get"
    LIST = "list"
    DELETE = "delete"
    CLEAR = "clear"
    def __str__(self) -> str:
        return self.value

class MemoryParams(BaseModel):
    action: str = Field(..., description="The action to perform on the memory. Actions are: set, get, list, delete, clear")
    key: str = Field(..., description="The key of the memory to store and retrieve. Used in the set and get actions")
    value: str = Field(..., description="The value of the memory to store and retrieve. Used in the set action")

class MemoryTool(Tool):
    name: str = "memory"
    description: str = "Manage memory for the current session. Use this to store important information that you want to remember"
    type: ToolType = ToolType.MEMORY
    schema: MemoryParams = MemoryParams

    def __init__(self, config: Config) -> None:
        self._config = config
        self.memory_file = Path(self._config.cwd / "memory.json") # TODO: this should be stored in the platformdir config directory to make it persistent across sessions
        self._memory: dict[str, str] = {}
        if not self.memory_file.parent.exists():
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.memory_file, "w") as f:
                json.dump({}, f)
        else:
            with open(self.memory_file, "r") as f:
                self._memory = json.load(f)
    
    def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = MemoryParams(**invocation.params)
        if params.action == MemoryAction.SET:
            if not params.key or not params.value:
                return ToolResult.error_result(f"Memory is required")
            self._memory[params.key] = params.value
            with open(self.memory_file, "w") as f:
                json.dump(self._memory, f, indent=4)
            return ToolResult.success_result(output=f"Memory stored: {params.key} = {params.value}")
        if params.action == MemoryAction.GET:
            if not params.key:
                return ToolResult.error_result(f"Key is required")
            if params.key not in self._memory:
                return ToolResult.error_result(f"Memory with key: {params.key} not found")
            return ToolResult.success_result(output=f"Memory retrieved: {self._memory[params.key]}")
        if params.action == MemoryAction.LIST:
            output_lines = []
            for key, value in self._memory.items():
                output_lines.append(f"[{key}]: {value}")
            if not output_lines:
                return ToolResult.success_result(output="No memory found. Use the set action to create memory.")
            return ToolResult.success_result(output="\n".join(output_lines))
        if params.action == MemoryAction.DELETE:
            if not params.key:
                return ToolResult.error_result(f"Key is required")
            if params.key not in self._memory:
                return ToolResult.error_result(f"Memory with key: {params.key} not found")
            del self._memory[params.key]
            with open(self.memory_file, "w") as f:
                json.dump(self._memory, f, indent=4)
            return ToolResult.success_result(output=f"Memory deleted: {params.key}")
        if params.action == MemoryAction.CLEAR:
            self._memory = {}
            with open(self.memory_file, "w") as f:
                json.dump({}, f, indent=4)
            return ToolResult.success_result(output=f"Cleared all memory")
        return ToolResult.error_result(f"Invalid action: {params.action} the valid actions are: {', '.join([action.value for action in MemoryAction])}")


    def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error managing memory with error: {e}")