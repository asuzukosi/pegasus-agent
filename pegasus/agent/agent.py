from typing import AsyncGenerator
from typing import List, Dict, Any
import json
from pegasus.agent.results import AgentEvent, AgentEventType
from pegasus.context.data import ToolResultMessage
from pegasus.client.response import TokenUsage, ToolCall, StreamEventType
from pegasus.session.session import Session
from pegasus.config.config import Config
from pegasus.utils.logger import logger
from uuid import uuid4


def _assistant_message_tool_calls(tool_calls: List[ToolCall]) -> List[Dict[str, Any]]:
    return [
        {
            "id": tc.call_id,
            "type": "function",
            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else (tc.arguments or "{}")},
        }
        for tc in tool_calls
    ]

class Agent:
    def __init__(self, config: Config) -> None:
        self.id = str(uuid4())
        self._config = config
        self.session: Session | None = None

    def __str__(self) -> str:
        return f"Agent(config={self._config})"
    
    def __repr__(self) -> str:
        return self.__str__()

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        yield AgentEvent.agent_start(message)
        self.session.context_manager.add_user_message(message)
        final_response: str | None = None
        usage: TokenUsage | None = None
        async for event in self._agentic_loop():
            yield event
            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data['content']
        yield AgentEvent.agent_end(final_response, usage)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        # an agentic loop is a full execution cycle of a react agentic loop
        yield AgentEvent.loop_start()
        for turn in range(self._config.max_turns):
            # each turn is a single llm action
            await self.session.increment_turn()
            yield AgentEvent.turn_start()
            if self.session.context_manager.needs_compression():
                current_tokens = self.session.context_manager.current_context_tokens()
                context_limit = self._config.model.context_window or 0
                logger.info(
                    f"compressing context at {current_tokens} tokens with limit {context_limit}"
                )
                summary, compression_usage = await self.session.chat_compressor.compress(self.session.context_manager)
                if summary:
                    self.session.context_manager.replace_with_compressed_summary(summary)
                if compression_usage:
                    self.session.context_manager.set_usage(compression_usage)
            response_text = ''
            messages = self.session.context_manager.get_messages()
            tool_calls: List[ToolCall] = []
            usage: TokenUsage | None = None
            is_reasoning = False

            async for event in self.session.client.chat_completion(messages=messages, tools=self.session.tool_registry.get_schemas(), stream=True):
                if event.type == StreamEventType.TEXT_DELTA:
                    if event.text_delta and event.text_delta.content:
                        content = event.text_delta.content
                        response_text += content
                        if is_reasoning:
                            is_reasoning = False
                            yield AgentEvent.reasoning_complete()
                        yield AgentEvent.text_delta(content)
                    if event.reasoning_delta and event.reasoning_delta.reasoning:
                        reasoning = event.reasoning_delta.reasoning
                        is_reasoning = True
                        yield AgentEvent.reasoning_delta(reasoning)

                elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                    if event.tool_calls:
                        tool_calls.extend(event.tool_calls)
                elif event.type == StreamEventType.ERROR:
                    yield AgentEvent.agent_error(event.error if event.error else 'Unknown error', {})
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
            self.session.context_manager.add_assistant_message(response_text or "", tool_calls=_assistant_message_tool_calls(tool_calls))
            if response_text:
                yield AgentEvent.text_complete(response_text)
            
            if not tool_calls:
                if usage:
                    self.session.context_manager.set_usage(usage)
                # self.session.context_manager.prune_tool_outputs() # TODO: add context pruning later
                yield AgentEvent.turn_end()
                yield AgentEvent.loop_end()
                return

            tool_results: List[ToolResultMessage] = []
            for tool_call in tool_calls:
                yield AgentEvent.tool_call_start(tool_call.call_id, tool_call.name, tool_call.arguments)
                result = await self.session.tool_registry.invoke(tool_call.name, tool_call.arguments, self._config.cwd)
                tool_results.append(
                    ToolResultMessage(
                        tool_call_id=tool_call.call_id,
                        content=result.to_model_output(),
                        is_error=not result.success,
                        images=result.images,
                        metadata=result.metadata,
                    )
                )
                yield AgentEvent.tool_call_complete(
                    tool_call.call_id,
                    tool_call.name,
                    result.success,
                    result.output,
                    result.metadata,
                    result.truncated,
                    result.error,
                    result.diff,
                    result.exit_code,
                    result.images,
                )
            
            for tool_result in tool_results:
                self.session.context_manager.add_tool_result(tool_result)
            followup_images = [image for tool_result in tool_results for image in tool_result.images]
            if followup_images:
                followup_messages: list[str] = []
                for tool_call, tool_result in zip(tool_calls, tool_results, strict=False):
                    visual_context_message = tool_result.metadata.get("visual_context_message")
                    if visual_context_message:
                        followup_messages.append(f"{tool_call.name}: {visual_context_message}")
                followup_content = (
                    "\n".join(followup_messages)
                    if followup_messages
                    else "visual context from the previous tool call is attached. inspect these images before deciding the next action."
                )
                self.session.context_manager.add_user_message(
                    followup_content,
                    images=followup_images,
                )

            if usage:
                self.session.context_manager.set_usage(usage)            
            # self._session._context_manager.prune_tool_outputs() # TODO: add context pruning later
            yield AgentEvent.turn_end()
        yield AgentEvent.loop_end()
    
    async def startup(self) -> None:
        # initialize session if not already initialized
        logger.info(f"starting up agent")
        if self.session is None:
            self.session = Session(self._config)
            await self.session.initialize()

    async def cleanup(self) -> None:
        logger.info(f"cleaning up agent")
        if self.session is not None:
            await self.session.cleanup()
            self.session = None


if __name__ == "__main__":
    import asyncio

    async def main():
        config = Config()
        agent = Agent(config)
        await agent.startup()
        async for event in agent.run("Hello, how are you?"):
            logger.info(f"Event: {event}")
        await agent.cleanup()
        logger.info(f"Agent cleaned up")
    asyncio.run(main())