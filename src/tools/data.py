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


@dataclass
class ToolInvocation:
    cwd: Path
    params: dict[str, Any]

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False

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