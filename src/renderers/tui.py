from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from typing import Dict, Any, List, Tuple, Set
from rich.table import Table
from rich import box
from rich.panel import Panel
from pathlib import Path
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.console import Group
import re
from src.utils.paths import display_path_rel_to_cwd
from src.config.config import Config
from src.utils.text import truncate_text
from src.tools.data import FileDiff, ToolConfirmation

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
            "write_file": ["path", "create_dirs", "content"],
            "edit_file": ["path", "replace_all", "old_string", "new_string"],
            "shell": ["command", "timeout", "cwd"],
            "list_dir": ["path", "include_hidden"],
            "grep": ["path", "pattern", "case_sensitive"],
            "glob": ["path", "pattern"],
            "memory": ["action", "key", "value"],
            "todos": ["action", "id", "content"],
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
            if isinstance(value, str) and key in { "content", "old_string", "new_string", "old_content", "new_content"}:
                line_count = len(value.splitlines()) or 0
                byte_count = len(value.encode("utf-8")) or 0
                value = f"<{line_count} lines - {byte_count} bytes>"
            if isinstance(value, bool):
                value = "true" if value else "false"
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
                diff: FileDiff | None,
                exit_code: int | None,
        ) -> None:
            border_style = f"tool.{tool_kind}" if tool_kind else "tool"
            status_icon = "✅" if success else "❌"
            status_style = "success" if success else "error"

            args = self._tool_arguments_by_call_id.get(call_id, {})

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
            elif name in ["write_file", "edit_file"] and success:
                output_line = output.strip() if output.strip() else "Completed"
                blocks.append(Text(output_line, style="success"))
                diff_text = diff.create_diff() if diff else ""
                diff_display = truncate_text(diff_text, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(diff_display, "diff", theme="monokai", line_numbers=True, word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))
            elif name == "shell":
                command = args.get("command")
                if isinstance(command, str) and command.strip():
                    blocks.append(Text(f"${command}", style="muted"))
                if exit_code is not None:
                    blocks.append(Text(f"exit code: {exit_code}", style="muted"))

                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
            
            elif name == "list_dir" and success:
                entries = metadata.get("entries")
                path = metadata.get("path")
                summary = []
                if isinstance(path, str):
                    summary.append(path)
                if isinstance(entries, int):
                    summary.append(f"{entries} entries")
                if summary:
                    blocks.append(Text(" ".join(summary), style="muted"))
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))

            elif name == "grep" and success:
                path = metadata.get("path")
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
            if truncated:
                blocks.append(Text("Output truncated", style="warning"))

            elif name == "glob" and success:
                path = metadata.get("path")
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))

            elif name == "websearch" and success:
                results = metadata.get("results")
                query = metadata.get("query")
                summary = []

                if isinstance(query, list):
                    summary.append(f"Search results for '{query}'")

                if isinstance(results, list):
                    summary.append(f"Total results: {len(results)}")
                if isinstance(results, int):
                    summary.append(f"{results} results")

                if summary:
                    blocks.append(Text(".".join(summary), style="muted"))
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))

            elif name == "webfetch" and success:
                status_code = metadata.get("status_code")
                content_length = metadata.get("content_length")
                url = metadata.get("url")
                summary = []
                if isinstance(status_code, int):
                    summary.append(f"Status code: {status_code}")
                if isinstance(content_length, int):
                    summary.append(f"Content length: {content_length}")
                if isinstance(url, str):
                    summary.append(f"URL: {url}")
                
                if summary:
                    blocks.append(Text(".".join(summary), style="muted"))
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))
            
            elif name == "todos" and success:
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                
            elif name == "memory" and success: # TODO: redo the representation of the memory as shown in the tui
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                if truncated:
                    blocks.append(Text("Output truncated", style="warning"))
                    
            if error and not success:
                blocks.append(Text(error, style="error"))
                output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
                if output_display.strip():
                    blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
                else:
                    blocks.append(Text("No output", style="error"))
            
            panel = Panel(Group(*blocks), title=title, title_align="left", subtitle=Text('completed' if success else 'failed', style="muted"), subtitle_align="right", box=box.ROUNDED, padding=(1, 2), border_style=border_style)
            self._console.print()
            self._console.print(panel)

    def handle_confirmation(self, confirmation: ToolConfirmation) -> None:
        output = [
            Text(confirmation.tool_name, style="tool"),
            Text(confirmation.description, style="code"),
        ]
        if confirmation.command:
            output.append(Text(f'$ {confirmation.command}', style="warning"))
        if confirmation.diff:
            diff_text = confirmation.diff.to_diff()
            output.append(Syntax(diff_text, "diff", theme="monokai", line_numbers=True, word_wrap=False))
        
        self._console.print()
        self._console.print(
            Panel(
                Group(*output),
                title=Text("Confirmation Required", style="warning"),
                title_align="left",
                box=box.ROUNDED,
                padding=(1, 2),
                border_style="warning",
            )
        )
        response = Prompt.ask("Do you approve this action? (y/n)", choices=["y", "n"])
        if response == "y":
            return True
        else:
            return False    



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
