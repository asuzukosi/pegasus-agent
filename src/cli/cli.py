import click
import asyncio
from src.agent.agent import Agent
from src.agent.results import AgentEventType
from src.renderers.tui import TUI
import sys


class CLI:
    def __init__(self) -> None:
        self._agent | None = None
        self._tui = TUI()

    async def run_single(self, message: str) -> None:
        async with Agent() as agent:
            self._agent = agent
            self._process_message(message)

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
                tool = self._agent._tool_registry.get(tool_name)
                tool_kind = None
                if not tool:
                    tool_kind = None
                else:
                    tool_kind = tool.type
                self._tui.stream_tool_call_start(call_id, tool_name, arguments, tool_kind)
        return final_response

@click.command()
@click.option('--message', type=str, help='The message to send to the chat completion.')
async def run_cli(message: str) -> None:
    print("message:", message)
    if message:
        cli = CLI()
        result = asyncio.run(cli.run_single(message))
        if result is None:
            print("No response from agent")
            sys.exit(1)
    else:
        print("No message provided")