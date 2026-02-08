from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from typing import Dict, Any
from src.tools.data import ToolType

AGENT_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bright_red bold",
        "success": "green",
        "dim": "dim",
        "muted": "gray50",
        "border": "grey35", 
        "highlight": "bold cyan",
        # roles
        "user": "bright_blue bold",
        "assistant": "bright_white",
        # tools
        "tool": "bright_magenta bold",
        "tool.read": "cyan",
        "tool.write": "yellow",
        "tool.shell": "magenta",
        "tool.network": "bright_blue",
        "tool.memory": "green",
        "tool.mcp": "bright_cyan",
        # code / blocks
        "code": "white",
    }
)

_console: Console | None = None

def get_console() -> Console:
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=True)
    return _console

class TUI:
    def __init__(self, console: Console) -> None:
        self._console = console or get_console()
        self._assistant_stream_open = False
        self._tool_calls_by_call_id: Dict[str, Dict[str, Any]] = {}

    def _begin_assistant(self) -> None:
        self._console.print()
        self._console.print(Rule(Text("Assistant End", style="assistant")))
        self._assistant_stream_open = True

    def _end_assistant(self) -> None:
        self._console.print()
        self._console.print(Rule(Text("Assistant Start", style="assistant")))
        self._assistant_stream_open = False
    
    def stream_assistant_delta(self, content: str) -> None:
        self._console.print(content, end="", markup=False, style="assistant") 
    
    def stream_tool_call_start(self, call_id: str, name: str, arguments: dict[str, Any], tool_kind: ToolType) -> None:
        self._tool_calls_by_call_id[call_id] = {"name": name, "arguments": arguments}
        tool_kind_style = f"tool.{tool_kind}" if tool_kind else "tool"
        self._console.print(f"[{tool_kind_style}]Tool Call Start: {name}[/{tool_kind_style}]")
        self._console.print(f"[{tool_kind_style}]Call ID: {call_id}[/{tool_kind_style}]")
        self._console.print(f"[{tool_kind_style}]Arguments: {arguments}[/{tool_kind_style}]")