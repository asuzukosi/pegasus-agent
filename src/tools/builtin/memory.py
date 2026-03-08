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
    description: str = "Manage memory for the current session. Use this to store and retrieve important information that you want to remember. "\
                       "The memory tool can have information from previous sessions."\
                       " If asked about user specific information or need specific user information to perform tasks check if it is available in the memory."\
                       "When not certain list out all the keys in the memory to help you decide which key to use."
    type: ToolType = ToolType.MEMORY
    schema: MemoryParams = MemoryParams

    def __init__(self, config: Config) -> None:
        self._config = config
        self.memory_file = Path(self._config.cwd / "pegasus_memory.json") # TODO: this should be stored in the platformdir config directory to make it persistent across sessions
        self._memory: dict[str, str] = {}
        if not self.memory_file.exists():
            self.memory_file.touch()
            with open(self.memory_file, "w") as f:
                json.dump({}, f)
        else:
            with open(self.memory_file, "r") as f:
                self._memory = json.load(f)

    def _persist(self) -> None:
        with open(self.memory_file, "w") as f:
            json.dump(self._memory, f, indent=4)

    def _execute_set(self, params: MemoryParams) -> ToolResult:
        if not params.key or not params.value:
            return ToolResult.error_result("memory key and value are required for the set action")
        self._memory[params.key] = params.value
        self._persist()
        return ToolResult.success_result(output=f"memory stored: {params.key} = {params.value}")

    def _execute_get(self, params: MemoryParams) -> ToolResult:
        if not params.key:
            return ToolResult.error_result("key is required for the get action")
        if params.key not in self._memory:
            return ToolResult.error_result(f"memory with key: {params.key} not found")
        return ToolResult.success_result(output=f"memory retrieved: {self._memory[params.key]}")

    def _execute_list(self, params: MemoryParams) -> ToolResult:
        output_lines = [f"[{k}]: {v}" for k, v in self._memory.items()]
        if not output_lines:
            return ToolResult.success_result(output="no memory found. use the set action to create memory.")
        return ToolResult.success_result(output="\n".join(output_lines))

    def _execute_delete(self, params: MemoryParams) -> ToolResult:
        if not params.key:
            return ToolResult.error_result("key is required for the delete action")
        if params.key not in self._memory:
            return ToolResult.error_result(f"memory with key: {params.key} not found")
        del self._memory[params.key]
        self._persist()
        return ToolResult.success_result(output=f"memory deleted: {params.key}")

    def _execute_clear(self, params: MemoryParams) -> ToolResult:
        self._memory = {}
        self._persist()
        return ToolResult.success_result(output="cleared all memory")

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = MemoryParams(**invocation.params)
        if params.action == MemoryAction.SET:
            return self._execute_set(params)
        if params.action == MemoryAction.GET:
            return self._execute_get(params)
        if params.action == MemoryAction.LIST:
            return self._execute_list(params)
        if params.action == MemoryAction.DELETE:
            return self._execute_delete(params)
        if params.action == MemoryAction.CLEAR:
            return self._execute_clear(params)
        return ToolResult.error_result(
            f"invalid action: {params.action}. valid actions are: {', '.join(a.value for a in MemoryAction)}"
        )


    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error managing memory with error: {e}")