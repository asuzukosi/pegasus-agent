import click
import asyncio
from src.agent.agent import Agent
from src.agent.results import AgentEventType
from src.renderers.tui import TUI
import sys
from pathlib import Path
from src.config.config import Config
from src.config.loader import load_config
from src.security.approvals import ApprovalPolicy
from src.agent.persistence import PersistenceManager, SessionSnapshot
from src.session.session import Session
from src.context.manager import ContextManager
from src.context.loop_detector import LoopDetector


class CLI:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._agent | None = None
        self._tui = TUI(self._config)

    async def run_single(self, message: str) -> None:
        async with Agent(self._config, self._tui.handle_confirmation) as agent:
            self._agent = agent
            self._process_message(message)

    async def _run_interactive(self) -> None:
        self._tui.print_welcome(title="Pegasus CLI", lines=[
            f"model: {self._config.model_name}",
            f"cwd: {self._config.cwd}",
            "commands: /help /config /approval /model /exit"])
        
        async with Agent(self._config, self._tui.handle_confirmation) as agent:
            self._agent = agent
            while True:
                try:
                    user_input = self._tui._console.input("\n[user]> [/user]").strip()

                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = self._handle_command(user_input)
                        if not should_continue:
                            break
                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    self._tui._console.print("\n[dim] Use \\exit to quit[/dim]")
                except EOFError:
                    break
        self._tui._console.print("\n[dim] Goodbye![/dim]")


    def _handle_command(self, command: str) -> bool:
        command = command[1:].strip().lower()
        parts = command.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else None
        if cmd_name == "exit" or cmd_name == "quit":
            return False
        elif cmd_name == "help":
            self._tui.print_help()
            return True
        elif cmd_name == "clear":
            self._agent._session._context_manager.clear()
            self._agent._session._loop_detector.clear()
            return True
        elif cmd_name == "config":
            self._tui.print_config()
            return True
        elif cmd_name == "model":
            if cmd_args:
                self._config.model_name = cmd_args
                self._tui.print_config()
                return True
            else:
                self._tui._console.print(f"[error]Model name is required[/error]")
                return True
        elif cmd_name == "approval":
            if cmd_args:
                self._config.approval = ApprovalPolicy(cmd_args)
                self._tui.print_config()
                return True
            else:
                self._tui._console.print(f"[error]Approval status is required[/error]")
                return True
        elif cmd_name == "stats":
            self._tui.print_stats() # TODO: implement the function to print the ussage statistics
            return True
        elif cmd_name == "tools":
            self._tui.print_tools() # TODO: implement the function to call the tools
            return True
        elif cmd_name == "mcp":
            self._tui.print_mcp() # TODO: implement the function to print the MCP server information
            return True
        elif cmd_name == "save":
            persistence_manager = PersistenceManager(self._config)
            snapshot = SessionSnapshot(
                session_id=self._agent._session.session_id,
                created_at=self._agent._session.created_at,
                updated_at=self._agent._session.updated_at,
                turn_count=self._agent._session._turn_count,
                messages=self._agent._session._context_manager.get_messages(),
            )
            persistence_manager.save(snapshot)
            return True 
        
        elif cmd_name == "sessions":
            persistence_manager = PersistenceManager(self._config)
            sessions = persistence_manager.list_sessions()
            self._tui.print_sessions(sessions) # TODO: implement the function to print the sessions
            return True
        
        elif cmd_name == "resume":
            if not cmd_args:
                self._tui._console.print(f"[error]Session ID is required[/error]")
                return True
            persistence_manager = PersistenceManager(self._config)
            snapshot: SessionSnapshot | None = persistence_manager.load(cmd_args)
            if snapshot:
                self._agent._session = Session(self._config)
                self._agent._session.session_id = snapshot.session_id
                self._agent._session._context_manager = ContextManager(self._config)
                self._agent._session._loop_detector = LoopDetector()
                self._agent._session._turn_count = snapshot.turn_count
                # TODO: update the token usage informmation based on the new session snapshot
                self._agent._session._context_manager._messages = snapshot.messages
                # TODO: initiazlize the new session 
                return True
            else:
                self._tui._console.print(f"[error]Session not found[/error]")
                return True
            
        elif cmd_name == "checkpoint":
            if not cmd_args:
                self._tui._console.print(f"[error]Checkpoint timestamp is required[/error]")
                return True
            persistence_manager = PersistenceManager(self._config)
            persistence_manager.save_checkpoint(self._agent._session, cmd_args)
            return True
        elif cmd_name == "restore":
            if not cmd_args:
                self._tui._console.print(f"[error]Session ID and timestamp are required[/error]")
                return True
            persistence_manager = PersistenceManager(self._config)
            snapshot: SessionSnapshot | None = persistence_manager.load_checkpoint(cmd_args)
            if snapshot:
                return True
            else:
                self._tui._console.print(f"[error]Checkpoint not found[/error]")
                return True
        else:
            self._tui._console.print(f"[error]Unknown command: {cmd_name}[/error]")
        return True
    

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
                diff = event.data.get("diff", None)
                exit_code = event.data.get("exit_code", None)
                self._tui.tool_call_complete(call_id, tool_name, tool_kind, success, 
                                             output, error, metadata, truncated, diff, exit_code)
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