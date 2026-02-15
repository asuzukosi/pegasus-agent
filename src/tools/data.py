from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from enum import Enum


class ToolType(str, Enum):
    READ = "read"
    WRITE = "write"
    BASH = "bash"
    NETWORK = "network"
    MEMORY = "memory"
    MCP = "mcp"
    SUB_AGENT = "sub_agent"

@dataclass
class FileDiff:
    path: Path
    old_content: str
    new_content: str
    is_new_file: bool
    is_deletion: bool

    def create_diff(self) -> str:
        import difflib
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        old_name = "/dev/null" if self.is_new_file else self.path.as_posix()
        new_name = "/dev/null" if self.is_deletion else self.path.as_posix()
        deltas = difflib.unified_diff(old_lines, new_lines, fromfile=old_name, tofile=new_name)
        return "\n".join(deltas)


@dataclass
class ToolInvocation:
    cwd: Path
    params: dict[str, Any]

@dataclass
class ToolResult:
    success: bool
    output: str
    exit_code: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False
    diff: FileDiff | None = None

    @classmethod
    def error_result(cls, error: str, output: str = "") -> 'ToolResult':
        return cls(success=False, output=output, error=error)
    
    @classmethod
    def success_result(cls, output: str, **kwargs) -> 'ToolResult':
        return cls(success=True, output=output, **kwargs)

    def to_model_output(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error}\n\nOutput: {self.output}"

@dataclass
class ToolConfirmation:
    tool_name: str
    params: dict[str, Any]
    description: str