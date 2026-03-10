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
from pegasus.utils.paths import display_path_rel_to_cwd
from pegasus.config.config import Config
from pegasus.utils.text import truncate_text
from pegasus.tools.data import FileDiff
from pegasus.utils.logger import logger
from art import text2art

_GREEN = "\033[32m"
_RESET = "\033[0m"

# flying horse (Pegasus) ascii art
FLYING_HORSE_ART = r"""
====================================================================================================
====================================================================================================
=====-:=====================================================================================-:-=====
=====-.:-===============================================-==================================-..-=====
======:..:-===============================:.===========- :===============================-:..:======
===--==:...:=============================.:=:=========-:*.:============================-:...:==--===
===:.:-=-:...:-========================== +#::========.+#::==========================-:...:---:.-===
====:...:-::...::-=======================::+:..........:-.-=======================--:...::-:...:====
=====:.....:::......-=====================.     ....     .=====================-.....::::....::=====
==-.::--::....:::.    .:--===============:    ........    :===============--:.    .:::....::--::.-==
===-....:::::....         .-=+++=========:   ..........   -=========+++=-.         ....:::::....-===
=====:::......:::             .-*#++======   ..........   ======+*#*-.             :::......:::=====
====------::::....               :+##+===-%* .......... +%-===+##+.               ....::::------====
=====:......::::::                 .=###+-=*: ........ .+=-+###=.                 ::::::......:=====
======--:::........                  .-*#++-   .......  :++#+-.                 .........:::--======
=======::::::::......                 .=+++-   ......   .+++=.                 ......::::::::=======
========-::.::::::::..              .-+++++:   ......   .+++++:               ..::::::::.::-========
============::.....:::...         .:+++++++.   ......    =+++++=.          ...:::.....::============
=============-:::::...::....     .=++++++++..  ......   .=+++++++-.     ....::...:::::-=============
===============-:..:::..::..::..=++++++++++..  ......  ..-++++++++=:..::..::..:::..:-===============
===================:..::...:::-+++++++++++=... ......  ..-++++++++++=:.::...::..:===================
====================-=...::::+++++++++++++-... ...... ...:++++++++++++:.:::..:=-====================
========================--:=++++++++++++++-....:....:=...:+++++++++++++=::--========================
=========================+++++++++++++++++:...=@+...#@:...+++++++++++++++===========================
=======================+++++++++++++++++++:...:%%..:@+....=++++++++++++++++=========================
======================++++++++++++++++++++....:-:..:=*:...=++++++++++++++++++=======================
====================+++++++++++++++++++++=.....:----::....-+++++++++++++++++++======================
==================+++++++++++++++++++++++=................:+++++++++++++++++++++====================
"""

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
        "reasoning": "bright_green",
        # roles
        "user": "bright_blue bold",
        "assistant": "blue bold",
        # tools
        "tool": "bright_magenta bold",
        "tool.read": "cyan",
        "tool.write": "yellow",
        "tool.edit": "bright_yellow",
        "tool.bash": "magenta",
        "tool.network": "bright_blue",
        "tool.memory": "green",
        "tool.mcp": "bright_cyan",
        "tool.sub_agent": "bright_magenta",
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
        self._reasoning_stream_open = False
        self._tool_arguments_by_call_id: Dict[str, Dict[str, Any]] = {}
        self._cwd: Path | None = config.cwd
        self._full_width: int | None = self._console.width

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
    
    def _begin_reasoning(self) -> None:
        self._console.print()
        self._console.print(Rule(Text("Reasoning Start", style="reasoning")))
        self._reasoning_stream_open = True

    def stream_reasoning_delta(self, content: str) -> None:
        self._console.print(content, end="", markup=False, style="reasoning")
    
    def _end_reasoning(self) -> None:
        self._console.print()
        self._console.print(Rule(Text("Reasoning End", style="reasoning")))
        self._reasoning_stream_open = False
    
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

    def _guess_lexer(self, path: str | None) -> str:
        if not path:
            return "text"
        suffix = Path(path).suffix.lower()
        if suffix in (".py", ".pyw", ".pyx", ".pyz"):
            return "python"
        if suffix in (".js", ".jsx", ".ts", ".tsx"):
            return "javascript"
        if suffix in (".html", ".htm", ".xhtml", ".xht"):
            return "html"
        if suffix == ".css":
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
        border_style = f"tool.{tool_kind.value}" if tool_kind else "tool"

        title = Text.assemble(("🤔 ", "muted"), (name, "tool"), (" ", "muted"), (f"#{call_id[:8]}", "muted"))
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

    def _render_read_file_complete(
        self,
        output: str,
        primary_path: str | None,
        shown_start: int | None,
        shown_end: int | None,
        total_lines: int | None,
    ) -> List[Any]:
        blocks = []
        parsed = self._extract_read_file_code(output)
        if not parsed:
            blocks.append(Syntax(output, "text", theme="monokai", word_wrap=False))
            return blocks
        start_line, code = parsed
        lexer = self._guess_lexer(primary_path)
        header_parts = [display_path_rel_to_cwd(primary_path, self._cwd) if primary_path else "unknown file"]
        header_parts.append(" . ")
        if shown_start is not None and shown_end is not None and total_lines is not None:
            header_parts.append(f"Showing lines {shown_start}-{shown_end} of {total_lines}")
        blocks.append(Text(" ".join(header_parts), style="muted"))
        blocks.append(Syntax(code, lexer, theme="monokai", line_numbers=True, start_line=start_line, word_wrap=False))
        return blocks

    def _render_write_edit_complete(self, output: str, diff: FileDiff | None, truncated: bool) -> List[Any]:
        blocks = []
        output_line = output.strip() if output.strip() else "Completed"
        blocks.append(Text(output_line, style="success"))
        diff_text = diff.create_diff() if diff else ""
        diff_display = truncate_text(diff_text, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(diff_display, "diff", theme="monokai", line_numbers=True, word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_shell_complete(
        self, args: dict[str, Any], output: str, exit_code: int | None, truncated: bool
    ) -> List[Any]:
        blocks = []
        command = args.get("command")
        if isinstance(command, str) and command.strip():
            blocks.append(Text(f"${command}", style="muted"))
        if exit_code is not None:
            blocks.append(Text(f"exit code: {exit_code}", style="muted"))
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_list_dir_complete(self, output: str, metadata: dict[str, Any], truncated: bool) -> List[Any]:
        blocks = []
        path = metadata.get("path")
        entries = metadata.get("entries")
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
        return blocks

    def _render_grep_complete(self, output: str, truncated: bool) -> List[Any]:
        blocks = []
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_glob_complete(self, output: str, truncated: bool) -> List[Any]:
        blocks = []
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_websearch_complete(self, output: str, metadata: dict[str, Any], truncated: bool) -> List[Any]:
        blocks = []
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
        return blocks

    def _render_todos_complete(self, output: str, truncated: bool) -> List[Any]:
        blocks = []
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_memory_complete(self, output: str, truncated: bool) -> List[Any]:
        blocks = []
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        if truncated:
            blocks.append(Text("Output truncated", style="warning"))
        return blocks

    def _render_error_blocks(self, error: str | None, output: str) -> List[Any]:
        blocks = []
        if error:
            blocks.append(Text(error, style="error"))
        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        if output_display.strip():
            blocks.append(Syntax(output_display, "text", theme="monokai", word_wrap=False))
        else:
            blocks.append(Text("No output", style="error"))
        return blocks

    def _render_tool_complete_blocks(
        self,
        name: str,
        call_id: str,
        success: bool,
        output: str,
        error: str | None,
        metadata: dict[str, Any],
        truncated: bool,
        diff: FileDiff | None,
        exit_code: int | None,
    ) -> List[Any]:
        args = self._tool_arguments_by_call_id.get(call_id, {})
        meta = metadata if isinstance(metadata, dict) else {}
        primary_path = meta.get("path") if isinstance(meta.get("path"), str) else None
        shown_start = meta.get("shown_start")
        shown_end = meta.get("shown_end")
        total_lines = meta.get("total_lines")

        if not success:
            return self._render_error_blocks(error, output)
        if name == "read_file":
            return self._render_read_file_complete(output, primary_path, shown_start, shown_end, total_lines)
        if name in ("write_file", "edit_file"):
            return self._render_write_edit_complete(output, diff, truncated)
        if name == "shell":
            return self._render_shell_complete(args, output, exit_code, truncated)
        if name == "list_dir":
            return self._render_list_dir_complete(output, meta, truncated)
        if name == "grep":
            return self._render_grep_complete(output, truncated)
        if name == "glob":
            return self._render_glob_complete(output, truncated)
        if name == "websearch":
            return self._render_websearch_complete(output, meta, truncated)
        if name == "todos":
            return self._render_todos_complete(output, truncated)
        if name == "memory":
            return self._render_memory_complete(output, truncated)

        output_display = truncate_text(output, self._config.model_name, self._config.max_tool_output_tokens)
        blocks = [Syntax(output_display, "text", theme="monokai", word_wrap=False)] if output_display.strip() else []
        image_paths = meta.get("image_paths")
        if isinstance(image_paths, list) and image_paths:
            blocks.insert(0, Text(f"images: {len(image_paths)}", style="muted"))
        return blocks

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
            border_style = f"tool.{tool_kind.value}" if tool_kind else "tool"
            status_icon = "😊" if success else "😭"
            status_style = "success" if success else "error"
            title = Text.assemble((f"{status_icon} ", status_style), (name, "tool"), (" ", "muted"), (f"#{call_id[:8]}", "muted"))
            blocks = self._render_tool_complete_blocks(name, call_id, success, output, error, metadata, truncated, diff, exit_code)
            panel = Panel(
                Group(*blocks),
                title=title,
                title_align="left",
                subtitle=Text("completed" if success else "failed", style="muted"),
                subtitle_align="right",
                box=box.ROUNDED,
                padding=(1, 2),
                border_style=border_style,
            )
            self._console.print()
            self._console.print(panel)

    def print_help(self) -> None:
        self._console.print(Panel(Text("Help", style="highlight"), title="Help", title_align="left", box=box.ROUNDED, padding=(1, 2), border_style="border"))
        self._console.print(Text("Commands:", style="muted"))
        self._console.print(Text("  /help - Show this help message", style="muted"))
        self._console.print(Text("  /exit - Exit the program", style="muted"))
        self._console.print(Text("  /quit - Exit the program", style="muted"))
        self._console.print(Text("  /config - Show the current configuration", style="muted"))
        self._console.print(Text("  /model - Show the current model", style="muted"))


    def print_welcome(self, title: str, lines: List[str]) -> None:
        # flying horse at top (green), no markup so brackets in art are preserved
        horse_text = Text.from_ansi(f"{_GREEN}{FLYING_HORSE_ART.strip()}{_RESET}")
        self._console.print(horse_text)
        self._console.print()
        # "Pegasus" in smaller font so it fits the console
        try:
            pegasus_art = text2art("Pegasus - Gives  you  wings!", font="medium")
        except Exception:
            pegasus_art = text2art("Pegasus - Gives  you  wings!")
        pegasus_text = Text.from_ansi(f"{_GREEN}{pegasus_art}{_RESET}")
        self._console.print(pegasus_text)
        self._console.print()
        body = "\n".join(lines)
        self._console.print(
            Panel(
                Text(body, style="code"),
                title=Text(title, style="highlight"),
                title_align="left",
                border_style="border",
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._full_width,
                style="on grey23",
            )
        )

    def print_config(self) -> None:
        self._console.print(Panel(Text("Configuration", style="highlight"), title="Configuration", title_align="left", box=box.ROUNDED, padding=(1, 2), border_style="border"))
        self._console.print(Text(f"model: {self._config.model_name}", style="muted"))
        self._console.print(Text(f"cwd: {self._config.cwd}", style="muted"))
        # self._console.print(Text(f"max_tool_output_tokens: {self._config.max_tool_output_tokens}", style="muted"))
        # self._console.print(Text(f"max_tool_output_tokens: {self._config.max_tool_output_tokens}", style="muted"))