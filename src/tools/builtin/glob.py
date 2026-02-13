from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from src.utils.paths import resolve_path


class GlobParams(BaseModel):
    path: str = Field(..., description="The path to search for files")
    pattern: str = Field(..., description="The glob pattern to match")

class GlobTool(Tool):
    name: str = "glob"
    description: str = "Find files matching a glob pattern. Support ** for recursive matching"
    type: ToolType = ToolType.READ
    schema: GlobParams = GlobParams

    def __init__(self, config: Config) -> None:
        self._config = config

    def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = GlobParams(**invocation.params)
        search_path = resolve_path(invocation.cwd, params.path)

        if not search_path.exists() or not search_path.is_dir():
            return ToolResult.error_result(f"Path does not exist or is not a directory: {search_path}")
        
        matches = []
        try:
            matches = search_path.glob(params.pattern)
            matches = [match for match in matches if match.is_file()]
        except Exception as e:
            return ToolResult.error_result(f"Error globbing files with error: {e}")
        
        output_lines = []
        for match in matches[:1000]:
            try:
                rel_path = match.relative_to(invocation.cwd)
                output_lines.append(f"{rel_path.as_posix()}")
            except Exception as e:
                output_lines.append(f"Error getting relative path for {match.as_posix()} with error: {e}")
        truncated = False
        if len(matches) > 1000:
            output_lines.append("...truncated to 1000 matches...")
            truncated = True
        return ToolResult.success_result(output="\n".join(output_lines), truncated=truncated, metadata=dict(path=search_path.as_posix(), pattern=params.pattern, 
                                                                                       matches=matches[:1000], total_matches=len(matches), total_files=len(matches), truncated=truncated), truncated=truncated)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error globbing files with error: {e}")