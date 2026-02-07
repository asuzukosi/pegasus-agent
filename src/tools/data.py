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


@dataclass
class ToolConfirmation:
    tool_name: str
    params: dict[str, Any]
    description: str