import click
import asyncio
from src.agent.agent import Agent


class CLI:
    def __init__(self) -> None:
        self._agent | None = None

    async def run_single(self, message: str) -> None:
        async with Agent() as agent:
            self._agent = agent
            self._process_message(message)
            async for event in self._agent.run(message):
                print(event)

    async def _process_message(self, message: str) -> None:
        pass

@click.command()
@click.option('--message', type=str, help='The message to send to the chat completion.')
async def run_cli(message: str) -> None:
    print("message:", message)
    if message:
        cli = CLI()
        asyncio.run(cli.run_single(message))
    else:
        print("No message provided")