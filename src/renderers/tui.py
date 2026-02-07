from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text

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