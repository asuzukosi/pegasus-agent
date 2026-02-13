from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from src.utils.paths import resolve_path, is_binary_file
import re
import os
from pathlib import Path
from typing import List


class GrepParams(BaseModel):
    path: str = Field(..., description="File or directory path to search in")
    pattern: str = Field(..., description="Regular expression pattern to search for")
    case_sensitive: bool = Field(False, description="Whether to match case sensitively (default is false)")

class GrepTool(Tool):
    name: str = "grep"
    description: str = "Grep the contents of a file"
    type: ToolType = ToolType.READ
    schema: GrepParams = GrepParams

    def __init__(self, config: Config) -> None:
        self._config = config


    def _find_files(self, path: Path) -> List[Path]:
        MAX_FILES = 500
        files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and not d in {".git", ".svn", ".hg", ".bzr", ".venv", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".vscode", ".idea", ".DS_Store", "node_modules"}] 
            for file in files:
                if file.startswith("."):
                    continue
                file_path = Path(root) / file
                if not is_binary_file(file_path):
                    files.append(file_path)
                    if len(files) >= MAX_FILES:
                        return files
        return files

    def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = GrepParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        if not path.exists():
            return ToolResult.error_result(f"Path does not exist or is not a file: {path}")
        try:
            pattern = re.compile(params.pattern, re.IGNORECASE if not params.case_sensitive else 0)
        except re.error as e:
            return ToolResult.error_result(f"Invalid regular expression pattern: {params.pattern} with error: {e}")
        
        if path.is_dir():
            files: List[Path] = self._find_files(path)
        else:
            files = [path]
        matches = []
        for file in files:
            try:
                content = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(content.splitlines()):
                if pattern.search(line):
                    matches.append(f"{file.as_posix()}:{i+1}:{line}")
        return ToolResult.success_result(output="\n".join(matches), metadata=dict(matches=matches, total_matches=len(matches), total_files=len(files), 
                                                                                  path=path.as_posix(), case_sensitive=params.case_sensitive))


    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error grepping file with error: {e}")