from pydantic import BaseModel, Field
from typing import Any
from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.utils.paths import resolve_path, is_binary_file
from src.utils.text import estimate_tokens, truncate_text
from src.config.config import Config
from src.utils.logger import logger

MAX_FILE_SIZE = 1024 * 1024 * 10 # 10MB

class ReadFileParams(BaseModel):
    path: str = Field(..., description="The path to the file to read (related to the working directory or absolute path)")
    offset: int = Field(1, ge=1, description="The offset to read from the file")
    limit: int | None = Field(None, ge=1, description="The maximum number of bytes to read from the file")


class ReadFileTool(Tool):
    name: str = "read_file"
    description: str = "Read the contents of a text file. Returns the file content wiht the line numbers"\
                        "For large files, use offset and limit to read specific portions" \
                        "Cannot read binary files (images, executables, etc.)"
    type: ToolType = ToolType.READ
    schema: ReadFileParams = ReadFileParams

    def __init__(self, config: Config) -> None:
        self._config = config
        self._max_output_tokens = config.max_tool_output_tokens

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ReadFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        if not path.exists():
            return ToolResult.error_result(f"File not found: {path}")
        
        if not path.is_file():
            return ToolResult.error_result(f"Path is not a file: {path}")
        
        # handle management of large files
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return ToolResult.error_result(f"File is too large to read: {file_size / (1024 * 1024): .2f} MB. Maximum allowed size is {MAX_FILE_SIZE / (1024 * 1024): .2f} MB")
        
        if is_binary_file(path):
            return ToolResult.error_result(f"Cannot read binary files: {path}")
        
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        lines = content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return ToolResult.success_result(output="File is empty", metadata=dict(total_lines=0), truncated=False)
        
        start_idx = max(0, params.offset - 1)
        if params.limit is not None:
            end_idx = min(start_idx + params.limit, total_lines)
        else:
            end_idx = total_lines
        
        selected_lines = lines[start_idx:end_idx]
        formated_lines = [f"{i+start_idx+1: >6} | {line}" for i, line in enumerate(selected_lines)]

        output = "\n".join(formated_lines)
        token_count = estimate_tokens(output)
        truncated = False

        if token_count > self._max_output_tokens:
           output = truncate_text(output, self._config.model_name, self._max_output_tokens)
           truncated = True

        metadata_lines = []
        if start_idx > 0 or end_idx < total_lines:
            metadata_lines.append(
                f"Showing {end_idx - start_idx} of {total_lines} lines"
            )
        if metadata_lines:
            header = " | ".join(metadata_lines) + "\n\n"
            output = header + output
        
        return ToolResult.success_result(
            output=output,
            truncated = truncated,
            metadata=dict(path=path.as_posix(), total_lines=total_lines, shown_start=start_idx + 1, shown_end=end_idx)
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            result = await self._execute(invocation)
            return result
        except Exception as e:
            return ToolResult.error_result(f"Error reading file with error: {e}")