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
        self._agent | None = None
        self._tui = TUI(self._config)

    async def run_single(self, message: str) -> None:
        async with Agent(self._config) as agent:
            self._agent = agent
            self._process_message(message)

    async def _run_interactive(self) -> None:
        self._tui.print_welcome(title="Pegasus CLI", lines=[
            f"model: {self._config.model_name}",
            f"cwd: {self._config.cwd}",
            "commands: /help /config /approval /model /exit"])
        
        async with Agent(self._config) as agent:
            self._agent = agent
            while True:
                try:
                    user_input = self._tui._console.input("\n[user]> [/user]").strip()
                    if not user_input:
                        continue
                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    self._tui._console.print("\n[dim] Use \\exit to quit[/dim]")
                except EOFError:
                    break
        self._tui._console.print("\n[dim] Goodbye![/dim]")

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None
        tool = self._agent._session._tool_registry.get(tool_name)
        if not tool:
            tool_kind = None
        tool_kind = tool.type
        return tool_kind

    async def _process_message(self, message: str) -> str | None:
        if not self._agent:
            return None
        
        assistant_streaming = False
        final_response: str | None = None
        async for event in self._agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get('content', '')
                if not assistant_streaming:
                    self._tui._begin_assistant()
                    assistant_streaming = True
                self._tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                if assistant_streaming:
                    assistant_streaming = False
                    self._tui._end_assistant()

            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                self._tui._console.print(f"[error]Error: {error}[/error]")

            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "")
                call_id = event.data.get("call_id", "")
                arguments = event.data.get("arguments", {})
                tool_kind = self._get_tool_kind(tool_name)
                self._tui.tool_call_start(call_id, tool_name, tool_kind, arguments)
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "")
                call_id = event.data.get("call_id", "")
                tool_kind = self._get_tool_kind(tool_name)
                success = event.data.get("success", False)
                output = event.data.get("output", "")
                metadata = event.data.get("metadata", {})
                truncated = event.data.get("truncated", False)
                error = event.data.get("error", None)
                self._tui.tool_call_complete(call_id, tool_name, tool_kind, success, 
                                             output, metadata, truncated, error)
        return final_response

@click.command()
@click.option('--message', type=str, help='The message to send to the chat completion.')
@click.option('--cwd', type=click.Path(exists=True, file_okay=False, path_type=Path), help='The current working directory.' , default=Path.cwd())
async def run_cli(message: str | None = None, cwd: Path = Path.cwd()) -> None:
    
    cli = CLI(config)
    try:
        config = load_config(cwd)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)
    errors = config.validate()
    if errors:
        for error in errors:
            click.echo(f"Error: {error}", err=True)
        sys.exit(1)
    if message:
        result = asyncio.run(cli.run_single(message))
    else:
        result = asyncio.run(cli._run_interactive())
    if result is None:
        click.echo("No response from agent", err=True)
        sys.exit(1)