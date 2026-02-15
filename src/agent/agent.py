from typing import AsyncGenerator
from typing import List
from src.agent.results import AgentEvent, AgentEventType
from src.client.response import StreamEventType, ToolCall, TokenUsage
from src.context.data import ToolResultMessage
from src.session.session import Session
from src.config.config import Config

class Agent:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._session: Session | None = None


    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self._session._context_manager.add_user_message(message)
        async for event in self._agentic_loop():
            yield event
            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data['content']
        yield AgentEvent.agent_end(final_response)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        yield AgentEvent.loop_start()
        for step in range(self._config.max_turns):
            self._session.increment_turn()
            yield AgentEvent.turn_start()
            response_text = ''
            messages = self._session._context_manager.get_messages()
            tool_calls: List[ToolCall] = []
            usage: TokenUsage | None = None

            if self._session._context_manager.needs_compression():
                summary, usage = await self._session._chat_compressor.compress(self._session._context_manager)
                if summary:
                    self._session._context_manager.set_latest_usage(usage)
                    self._session._context_manager.add_usage(usage)
                    self._session._context_manager.replace_with_compressed_summary(summary)

            async for event in self._session._client.chat_completion(messages=messages, stream=True):
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
                
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
            self._session._context_manager.add_assistant_message(response_text or "", tool_calls=[{"id": tool_call.call_id, "type": "function", "function": {"name": tool_call.name, "arguments": tool_call.arguments}} for tool_call in tool_calls])
            if response_text:
                yield AgentEvent.text_complete(response_text)
            
            if not tool_calls:
                if usage:
                    self._session._context_manager.set_latest_usage(usage)
                    self._session._context_manager.add_usage(usage)
                self._session._context_manager.prune_tool_outputs()
                yield AgentEvent.turn_end()
                yield AgentEvent.loop_end()
                return

            tool_results: List[ToolResultMessage] = []
            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(tool_call.call_id, tool_call.name, tool_call.arguments)
                result = await self._session._tool_registry.invoke(tool_call.name, tool_call.arguments, self._config.cwd)
                tool_results.append(ToolResultMessage(tool_call_id=tool_call.call_id, content=result.to_model_output(), is_error=not result.success))
                yield AgentEvent.tool_call_complete(tool_call.call_id, tool_call.name, result.success, result.output, result.metadata, result.truncated, result.error, result.diff)
            
            for tool_result in tool_results:
                self._session._context_manager.add_tool_result(tool_result)

            if usage:
                self._session._context_manager.set_latest_usage(usage)
                self._session._context_manager.add_usage(usage)
            
            self._session._context_manager.prune_tool_outputs()
        
            yield AgentEvent.turn_end()
        yield AgentEvent.loop_end()
    async def __aenter__(self) -> 'Agent':
        # initialize session if not already initialized
        if self._session is None:
            self._session = Session(self._config)
            await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._session._client is not None:
            await self._session._client.close()
            if self._session._mcp_manager is not None:
                await self._session._mcp_manager.shutdown()
            self._session = None