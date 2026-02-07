import click
from src.client.llm_client import LLMClient



class CLI:
    def __init__(self) -> None:
        pass

    def run_single(self):
        pass


@click.command()
@click.option('--model', type=str, default='gpt-4o-mini', help='The model to use for the chat completion.')
@click.option('--stream', is_flag=True, help='Whether to stream the response.')
@click.option('--messages', type=str, help='The messages to send to the chat completion.')
async def command_entrypoint(model: str, stream: bool, messages: str) -> None:
    client = LLMClient()
    messages = [{"role": "user", "content": messages}] if messages else [{"role": "system", "content": "Hello, how are you?"}]
    async for event in client.chat_completion(messages=messages, stream=stream):
        print(event)
    await client.close()
