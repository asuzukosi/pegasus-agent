import os
from src.client.response import TextDelta, TokenUsage, StreamEvent, StreamEventType, ToolCallDelta, ToolCall, parse_tool_call_arguments
from typing import Any, Dict, List, AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai import RateLimitError, APIError
from retry import retry
from typing import Union

OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

class LLMClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None


    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, 
                                       model='', 
                                       base_url=OPENROUTER_BASE_URL)
        return self._client
    
    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _build_tools(self, tools: List[dict[str, Any]] | None) -> List[dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {
                    "type": "object",
                    "properties": {},
                }),
                
            }
        } for tool in tools]

    @retry(exceptions=RateLimitError, tries=3, delay=1, backoff=2)
    async def chat_completion(self, 
                              messages: List[Dict[str, Any]], 
                              tools: List[dict[str, Any]] | None = None,
                              stream: bool = False) -> AsyncGenerator[StreamEvent, None]:
        client: AsyncOpenAI = self._get_client()
        kwargs: Dict[str, Any] = {
            'model': 'gpt-4o-mini',
            'messages': messages,
            'stream': stream,
        }
        if tools is not None:
            kwargs['tools'] = self._build_tools(tools)
            kwargs['tool_choice'] = 'auto'
        try:
            if stream:
                async for event in self._stream_response(client, kwargs):
                    yield event
            else:
                yield await self._non_stream_response(client, kwargs)
        except RateLimitError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error='Rate limit exceeded',
                text_delta=None,
                finish_reason=None,
                usage=None,
            )
            raise RateLimitError
        except APIError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error='API error',
                text_delta=None,
                finish_reason=None,
                usage=None,
            )


    async def _stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
        response: ChatCompletion = await client.chat.completions.create(**kwargs)
        async for chunk in response:
            chunk: ChatCompletionChunk = chunk
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            usage = None
            if hasattr(choice, 'usage'):
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )
            finish_reason = None
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            text_delta = None
            if delta.content:
                text_delta = TextDelta(content=delta.content)
            if text_delta:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=text_delta,
                    error=None,
                    finish_reason=finish_reason,
                    usage=usage,
                )
            tool_calls = Dict[str, Any] = {}
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    idx = tool_call_delta.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tool_call_delta.id,
                            "name": "",
                            "arguments": "",
                        }
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                tool_calls[idx]["name"] = tool_call_delta.function.name
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL_START,
                                    tool_call_delta=ToolCallDelta(
                                        call_id=tool_calls[idx]["id"],
                                        name=tool_call_delta.function.name,
                                    )
                                )
                            if tool_call_delta.function.arguments:
                                tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_CALL_DELTA,
                                    tool_call_delta=ToolCallDelta(
                                        call_id=tool_calls[idx]["id"],
                                        name=tool_call_delta.function.name,
                                        arguments_delta=tool_call_delta.function.arguments,
                                    )
                                )

        for idx, tool_call in tool_calls.items():
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    call_id=tool_call["id"],
                    name=tool_call["name"],
                    arguments=parse_tool_call_arguments(tool_call["arguments"]),
                    usage=usage,
                )
            )
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            usage=usage,
            finish_reason=finish_reason,
        )
    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> Union[StreamEvent, None]:
        response: ChatCompletion = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # create the text delta
        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

        # create the tool calls
        tool_calls = List[ToolCall] = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append(ToolCall(
                    call_id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=parse_tool_call_arguments(tool_call.function.arguments),
                ))

        # calculate the usage
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        # get finish reason
        finish_reason = None
        if choice.finish_reason:
            finish_reason = choice.finish_reason

        # return the streaming event
        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            usage=usage,
            finish_reason=finish_reason,
            error=None,
        )