from typing import AsyncGenerator
from typing import List
from src.agent.results import AgentEvent, AgentEventType
from src.client.llm_client import LLMClient
from src.client.response import StreamEventType, ToolCall
from src.context.data import ToolResultMessage
from src.context.manager import ContextManager
from src.tools.registry import create_default_registry, ToolRegistry
from pathlib import Path
from src.config.config import Config

class Agent:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = LLMClient(self._config)
        self._context_manager = ContextManager(self._config)
        self._tool_registry: ToolRegistry = create_default_registry(self._config)
        # keep track of session management
        # TODO: each session should have its own client


    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self._context_manager.add_user_message(message)
        async for event in self._agentic_loop():
            yield event
            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data['content']
        yield AgentEvent.agent_end(final_response)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        yield AgentEvent.loop_start()
        for step in range(self._config.max_turns):
            response_text = ''
            messages = self._context_manager.get_messages()
            tool_calls: List[ToolCall] = []

            async for event in self._client.chat_completion(messages=messages, stream=True):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta and event.text_delta.content:
                        content = event.text_delta.content
                        response_text += content
                        yield AgentEvent.text_delta(content)

                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_call:
                        tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(event.error if event.error else 'Unknown error', {})

            self._context_manager.add_assistant_message(response_text or "", tool_calls=[{"id": tool_call.call_id, "type": "function", "function": {"name": tool_call.name, "arguments": tool_call.arguments}} for tool_call in tool_calls])
            if response_text:
                yield AgentEvent.text_complete(response_text)
            
            if not tool_calls:
                yield AgentEvent.turn_end()
                yield AgentEvent.loop_end()
                return

            tool_results: List[ToolResultMessage] = []
            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(tool_call.call_id, tool_call.name, tool_call.arguments)
                result = await self._tool_registry.invoke(tool_call.name, tool_call.arguments, self._config.cwd)
                tool_results.append(ToolResultMessage(tool_call_id=tool_call.call_id, content=result.to_model_output(), is_error=not result.success))
                yield AgentEvent.tool_call_complete(tool_call.call_id, tool_call.name, result.success, result.output, result.metadata, result.truncated, result.error)
            
            for tool_result in tool_results:
                self._context_manager.add_tool_result(tool_result)
        
            yield AgentEvent.turn_end()
        yield AgentEvent.loop_end()
    async def __aenter__(self) -> 'Agent':
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None