from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from src.utils.paths import resolve_path

class ListDirParams(BaseModel):
    path: str = Field(".", description="The path to list")
    include_hidden: bool = Field(False, description="Whether to include hidden files and directories")

class ListDirTool(Tool):
    name: str = "list_dir"
    description: str = "List the contents of a directory"
    type: ToolType = ToolType.READ
    schema: ListDirParams = ListDirParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ListDirParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        if not path.exists() or not path.is_dir():
            return ToolResult.error_result(f"Path does not exist or is not a directory: {path}")
        try:
            sorted_contents = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception as e:
            return ToolResult.error_result(f"Error listing directory with error: {e}")
        contents = []
        # filter out hidden files and directories
        if not params.include_hidden:
            contents = [p for p in sorted_contents if not p.name.startswith(".")]
        if not contents:
            return ToolResult.success_result(output="Directory is empty", metadata=dict(path=path.as_posix(), entries=0))
        for content in contents:
            if content.is_dir():
                contents.append(f"{content.name}/")
            else:
                contents.append(f"{content.name}")
        output = "\n".join(contents)
        return ToolResult.success_result(output=output, metadata=dict(path=path.as_posix(), entries=len(contents)))


    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error listing directory with error: {e}")