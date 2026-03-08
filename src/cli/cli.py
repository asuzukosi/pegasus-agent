import click
import asyncio
from src.agent.agent import Agent
from src.agent.results import AgentEventType
from src.renderers.tui import TUI
import sys
from pathlib import Path
from src.config.config import Config
from src.config.loader import load_config


class CLI:
    def __init__(self, config: Config) -> None:
        self._config = config
        self.agent: Agent | None = None
        self.tui = TUI(self._config)

    async def startup(self) -> None:
        self.agent = Agent(self._config)
        await self.agent.startup()
        self.tui.print_welcome(title="Pegasus CLI", lines=[
            f"Model: {self._config.model_name}",
            f"CWD: {self._config.cwd}",
            "Commands: /help /config /model /exit"])

    async def run_single(self, message: str) -> None:
        await self._process_message(message)

    async def run_interactive(self) -> bool:
        while True:
            try:
                user_input = self.tui._console.input("\n[user]> [/user]").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    should_continue = self._handle_command(user_input)
                    if not should_continue:
                        break
                else:
                    await self._process_message(user_input)
            except KeyboardInterrupt:
                self.tui._console.print("\n[dim] Use \\exit to quit[/dim]")
                break
            except EOFError:
                break
        self.tui._console.print("\n[dim] Goodbye Ol Friend![/dim]")
        return True

    def _handle_command(self, command: str) -> bool:
        command = command[1:].strip().lower()
        parts = command.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else None
        if cmd_name == "exit" or cmd_name == "quit":
            return False
        elif cmd_name == "help":
            self.tui.print_help()
            return True
        elif cmd_name == "clear":
            self.agent.session.context_manager.clear()
            return True
        elif cmd_name == "config":
            self.tui.print_config()
            return True
        elif cmd_name == "model":
            if cmd_args:
                self._config.model_name = cmd_args
                self.tui.print_config()
                return True
            else:
                self.tui._console.print(f"[error]Model name is required[/error]")
                return True
    

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            tool_kind = None
        tool_kind = tool.type
        return tool_kind

    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None
        assistant_streaming = False
        reasoning_streaming = False
        assistant_started = False
        reasoning_started = False
        final_response: str | None = None
        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get('content', '')
                if not assistant_streaming:
                    assistant_started = True
                    self.tui._begin_assistant()
                    assistant_streaming = True
                self.tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.REASONING_DELTA:
                content = event.data.get('reasoning', '')
                if not reasoning_streaming:
                    reasoning_started = True
                    self.tui._begin_reasoning()
                    reasoning_streaming = True
                self.tui.stream_reasoning_delta(content)
            elif event.type == AgentEventType.REASONING_COMPLETE:
                if reasoning_streaming and reasoning_started:
                    reasoning_streaming = False
                    self.tui._end_reasoning()
            elif event.type == AgentEventType.TEXT_COMPLETE:
                if assistant_streaming and assistant_started:
                    assistant_streaming = False
                    self.tui._end_assistant()
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                self.tui._console.print(f"[error]Error: {error}[/error]")
            elif event.type == AgentEventType.TOOL_CALL_START:
                if reasoning_streaming and reasoning_started:
                    reasoning_streaming = False
                    self.tui._end_reasoning()
                tool_name = event.data.get("name", "")
                call_id = event.data.get("call_id", "")
                arguments = event.data.get("arguments", {})
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_start(call_id, tool_name, tool_kind, arguments)
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "")
                call_id = event.data.get("call_id", "")
                tool_kind = self._get_tool_kind(tool_name)
                success = event.data.get("success", False)
                output = event.data.get("output", "")
                metadata = event.data.get("metadata", {})
                truncated = event.data.get("truncated", False)
                error = event.data.get("error", None)
                diff = event.data.get("diff", None)
                exit_code = event.data.get("exit_code", None)
                self.tui.tool_call_complete(call_id, tool_name, tool_kind, success, 
                                             output, error, metadata, truncated, diff, exit_code)
        return final_response

async def _run_cli(message: str | None = None, cwd: Path = Path.cwd()) -> None:
    try:
        config = load_config(cwd)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)
    cli = CLI(config)
    await cli.startup()
    if message:
        result = await cli.run_single(message)
    else:
        result = await cli.run_interactive()
    if result is None:
        click.echo("No response from agent", err=True)
        sys.exit(1)


@click.command()
@click.option('--message', type=str, help='The message to send to the chat completion.')
@click.option('--cwd', type=click.Path(exists=True, file_okay=False, path_type=Path), help='The current working directory.' , default=Path.cwd())
def run_cli(message: str | None = None, cwd: Path = Path.cwd()) -> None:
    """sync entry point that runs the async _run_cli."""
    asyncio.run(_run_cli(message=message, cwd=cwd))