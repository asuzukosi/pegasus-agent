from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from typing import Dict, Any, List, Tuple, Set
from rich.table import Table
from rich import box
from rich.panel import Panel
from pathlib import Path
from rich.syntax import Syntax
from rich.console import Group
import re
from src.utils.paths import display_path_rel_to_cwd
from src.config.config import Config

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
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=True)
    return _console

class TUI:
    def __init__(self, config: Config, console: Console | None = None) -> None:
        self._console = console or get_console()
        self._config = config
        self._assistant_stream_open = False
        self._tool_arguments_by_call_id: Dict[str, Dict[str, Any]] = {}
        self._cwd: Path | None = config.cwd
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
    
    def _order_args(self, tool_name:str, args: dict[str, Any]) -> list[str]:
        _PREFERRED_ORDER= {
            "read_file": ["path", "offset", "limit"],
        }
        preferred_order = _PREFERRED_ORDER.get(tool_name, [])
        ordered: List[Tuple[str, Any]] = []
        seen: Set[str] = set()
        for key in preferred_order:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
        remaining_keys = set(args.keys() - seen)
        ordered.extend((key, args[key]) for key in remaining_keys)
        return ordered



    def _render_arguments_table(self, tool_name: str, arguments: dict[str, Any]) -> str:
        table = Table.grid(padding=(0, 1))
        table.add_column(style='muted', justify='right', no_wrap=True)
        table.add_column(style='code', overflow='fold')
        for key, value in self._order_args(tool_name, arguments):
            table.add_row(key, str(value))
        return table
    
    def _guess_lexer(path: str | None) -> str:
        if not path:
            return "text"
        suffix = Path(path).suffix.lower()
        if suffix in (".py", ".pyw", ".pyx", ".pyz"):
            return "python"
        if suffix in (".js", ".jsx", ".ts", ".tsx"):
            return "javascript"
        if suffix in (".html", ".htm", ".xhtml", ".xht"):
            return "html"
        if suffix in (".css"):
            return "css"
        return "text"
    

    def tool_call_start(
            self,
            call_id: str,
            name: str, 
            tool_kind: str | None, 
            arguments: dict[str, Any]
    ) -> None:
        self._tool_arguments_by_call_id[call_id] = arguments
        border_style = f"tool.{tool_kind}" if tool_kind else "tool"

        title = Text.assemble((". ", "muted"), (name, "tool"), (" ", "muted"), )(f"#{call_id[:8]}", "muted")
        display_args = dict(arguments)
        for key in ('pwd', 'cwd'):
            val = display_args.get(key)
            if isinstance(val, str) and self._cwd:
                display_args[key] = str(display_path_rel_to_cwd(val, self._cwd))
        panel = Panel(self._render_arguments_table(name, arguments) if display_args else Text("No arguments", style="muted"), 
                      title=title, 
                      title_align="left",
                      subtitle=Text('running...', style="muted"),
                      subtitle_align="right",
                      box=box.ROUNDED,
                      padding=(1, 2),
                      border_style=border_style)
        self._console.print()
        self._console.print(panel)

    def _extract_read_file_code(self, text: str) -> tuple[int, str] | None:
        body = text
        header_match = re.match(r"^Showing lines (\d+)-(\d+) of (\d+)\n\n", body)
        if header_match:
            body = text[header_match.end():]

        code_lines: list[str] = []
        start_line: int | None = None
        for line in body.splitlines():
            m = re.match(r"^\s*(\d+)\|(.*)$", line)
            if not m:
                return None
            line_number = int(m.group(1))
            if start_line is None:
                start_line = line_number
            code_line = m.group(2)
            code_lines.append(code_line)
        if start_line is None:
            return None
        return start_line, "\n".join(code_lines)


    def tool_call_complete(
                self,
                call_id: str,
                name: str, 
                tool_kind: str | None, 
                success: bool,
                output: str,
                error: str | None,
                metadata: dict[str, Any],
                truncated: bool,
        ) -> None:
            border_style = f"tool.{tool_kind}" if tool_kind else "tool"
            status_icon = "✅" if success else "❌"
            status_style = "success" if success else "error"

            title = Text.assemble((f"{status_icon}", status_style), (name, "tool"), (" ", "muted"), )(f"#{call_id[:8]}", "muted")
            primary_path = None
            shown_start = None
            shown_end = None
            total_lines = None
            blocks = []
            if isinstance(metadata, dict) and isinstance(metadata.get("path"), str):
                primary_path = metadata.get("path")
                shown_start = metadata.get("shown_start")
                shown_end = metadata.get("shown_end")
                total_lines = metadata.get("total_lines")
            if name == "read_file" and success:
                start_line, code = self._extract_read_file_code(output)
                pl = self._guess_lexer(primary_path)
                blocks.append(Text())
                header_parts = [display_path_rel_to_cwd(primary_path, self._cwd) if primary_path else "unknown file"]
                header_parts.append(" . ")
                if shown_start and shown_end and total_lines:
                    header_parts.append(f"Showing lines {shown_start}-{shown_end} of {total_lines}")
                header = " ".join(header_parts)
                blocks.append(Text(header, style="muted"))
                blocks.append(Syntax(code, pl, theme="monokai", line_numbers=True, start_line=start_line, word_wrap=False))

            if truncated:
                blocks.append(Text("Output truncated", style="warning"))
            panel = Panel(Group(*blocks), title=title, title_align="left", subtitle=Text('completed' if success else 'failed', style="muted"), subtitle_align="right", box=box.ROUNDED, padding=(1, 2), border_style=border_style)
            self._console.print()
            self._console.print(panel)

    def print_welcome(self, title:str, lines: List[str]) -> None:
        body = "\n".join(lines)
        self._console.print(
            Panel(
                Text(body, style="code"),
                title=Text(title, style="highlight"),
                title_align="left",
                border_style="border",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
