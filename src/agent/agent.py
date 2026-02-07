from typing import AsyncGenerator
from src.agent.results import AgentEvent, AgentEventType
from src.client.llm_client import LLMClient
from src.client.response import StreamEventType

class Agent:
    def __init__(self) -> None:
        self._client = LLMClient()
        # keep track of session management
        # TODO: each session should have its own client


    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        # TODO: add user message to context as the agent uses the context to generate the responses
        async for event in self._agentic_loop():
            yield event
            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data['content']
        yield AgentEvent.agent_end(final_response)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        messages = [{"role": "user", "content": "Hello, how are you?"}]
        response_text = ''
        async for event in self._client.chat_completion(messages=messages, stream=True):
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta.content:
                    content = event.text_delta.content
                    response_text += content
                    yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error if event.error else 'Unknown error', {})
        if response_text:
            yield AgentEvent.text_complete(response_text)


    async def __aenter__(self) -> 'Agent':
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None