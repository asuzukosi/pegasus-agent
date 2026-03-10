from pegasus.tools.base import Tool
from pegasus.tools.data import ToolType, ToolInvocation, ToolResult, FileDiff
from pegasus.config.config import Config
from pydantic import BaseModel, Field
from pegasus.utils.paths import resolve_path, ensure_parent_directory

class WriteFileParams(BaseModel):
    path: str = Field(..., description="The path to the file to write to (related to the working directory or absolute path)")
    create_dirs: bool = Field(True, description="Whether to create the parent directories if they do not exist")
    content: str = Field(..., description="The contents to write to the file")

class WriteFileTool(Tool):
    name: str = "write_file"
    description: str = "Write the contents of a text file. Create the file if it does not exist, "\
                        "overwrite the file if it exists. Parent directories are created automatically."\
                        "Use this for creating new files or completely replacing file contents"\
                        "For partial modifications, use the edit_file tool instead"
    type: ToolType = ToolType.WRITE
    schema: WriteFileParams = WriteFileParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WriteFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        is_new_file = not path.exists()
        old_content = None
        if not is_new_file:
            try:
                old_content = path.read_text(encoding="utf-8")
            except Exception as e:
                pass
        
        if is_new_file:
            if params.create_dirs:
                ensure_parent_directory(path)
            elif not path.parent.exists():
                return ToolResult.error_result(f"Parent directory does not exist: {path.parent.as_posix()}")
            path.touch()
        try:
            path.write_text(params.content)
        except Exception as e:
            return ToolResult.error_result(f"Error writing file with error: {e}")
        action = "created" if is_new_file else "overwrote"
        line_count = len(params.content.splitlines())
        diff = FileDiff(path=path, old_content=old_content, new_content=params.content, is_new_file=is_new_file, is_deletion=False)
        return ToolResult.success_result(output=f"{action} {path} {line_count} lines", metadata=dict(path=str(path.as_posix()), is_new_file=is_new_file, lines=line_count, bytes=len(params.content.encode("utf-8"))), diff=diff)
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error writing file with error: {e}")