from pegasus.tools.base import Tool
from pegasus.tools.data import ToolType, ToolInvocation, ToolResult
from pegasus.config.config import Config
from pydantic import BaseModel, Field
from enum import Enum


class TodosAction(str, Enum):
    ADD = "add"
    ADD_MULTIPLE = "add_multiple" # TODO: implement this later
    REMOVE = "remove"
    LIST = "list"
    COMPLETE = "complete" 
    CLEAR = "clear"
    def __str__(self) -> str:
        return self.value

class TodosParams(BaseModel):
    action: str = Field(..., description="The action to perform on the todos. Actions are: add, remove, list, complete, clear")
    id: str | None = Field(..., description="The id of the todo to perform the action on. This is a unique identifier for the todo. If not provided, a new todo will be created.")
    content: str | None = Field(..., description="The content of the todo. This is the content that is entered when the action is add.")

class TodosTool(Tool):
    name: str = "todos"
    description: str = "Manage task list for the current session. ALWAYS use todos when asked to do more than one unit of work. Use this to track progress on complex tasks. When task complexity is exceeding a single operation use the todo list to track progress. Tasks should be modular and digestable so you will be able to execute them in isolation. Mark tasks as completed as you finish them. When neccessary verify a task is completed before marking as done."
    type: ToolType = ToolType.MEMORY
    schema: TodosParams = TodosParams

    def __init__(self, config: Config) -> None:
        self._config = config
        self._todos: dict[str, str] = {}
        self._next_id: int = 1

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = TodosParams(**invocation.params)
        
        if params.action == TodosAction.ADD:
            if not params.content:
                return ToolResult.error_result(f"Content is required when adding a todo")
            todo_id = str(self._next_id)
            self._todos[todo_id] = params.content
            self._next_id += 1
            return ToolResult.success_result(output=f"Added todo [{todo_id}]: {params.content}")
        if params.action == TodosAction.REMOVE:
            if not params.id:
                return ToolResult.error_result(f"ID is required when removing a todo")
            if params.id not in self._todos:
                return ToolResult.error_result(f"Todo with id: {params.id} not found")
            del self._todos[params.id]
            return ToolResult.success_result(output=f"Removed todo with id: {params.id}")
        if params.action == TodosAction.LIST:
            output_lines = []
            for id, content in self._todos.items():
                output_lines.append(f"[{id}]: {content}")
            if not output_lines:
                return ToolResult.success_result(output="No todos found. Use the add action to create a todo.")
            return ToolResult.success_result(output="\n".join(output_lines))
        if params.action == TodosAction.COMPLETE:
            if not params.id:
                return ToolResult.error_result(f"ID is required when completing a todo")
            if params.id not in self._todos:
                return ToolResult.error_result(f"Todo with id: {params.id} not found")
            self._todos[params.id] = f"{self._todos[params.id]}(completed)" # TODO: we may want to completely remove from the list instead of just marking as completed
            return ToolResult.success_result(output=f"Completed todo with id: {params.id}")
        if params.action == TodosAction.CLEAR:
            prev_len = len(self._todos)
            self._todos = {}
            self._next_id = 1
            return ToolResult.success_result(output=f"Cleared {prev_len} todos. There are now {len(self._todos)} todos left.")
        return ToolResult.error_result(f"Invalid action: {params.action} the valid actions are: {', '.join([action.value for action in TodosAction])}")

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error managing todos with error: {e}")