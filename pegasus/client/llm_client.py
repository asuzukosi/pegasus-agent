from typing import Any, Dict, List, AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai import RateLimitError, APIError
from retry import retry
from typing import Union
import time
from pegasus.client.response import StreamEvent, StreamEventType, TextDelta, ReasoningDelta, ToolCall, TokenUsage, parse_tool_call_arguments
from pegasus.config.config import Config
from pegasus.utils.logger import logger


class LLMClient:
    def __init__(self, config: Config) -> None:
        self._client: AsyncOpenAI | None = None
        self._config = config


    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._config.api_key, 
                                       base_url=self._config.base_url)
        return self._client
    
    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _build_tools(self, tools: List[dict[str, Any]] | None) -> List[dict[str, Any]]:
        """
        example tool:
        {
            "type": "function",
            "function": {
                "name": "search_gutenberg_books",
                "description": "Search for books in the Project Gutenberg library",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of search terms to find books"
                        }
                    },
                    "required": ["search_terms"]
                }
            }
        }
        """
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
                              stream: bool = False
                              ) -> AsyncGenerator[StreamEvent, None]:
        """ 
        example message:
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
        """
        client: AsyncOpenAI = self._get_client()
        kwargs: Dict[str, Any] = {
            'model': self._config.model_name,
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
                error='Rate limit exceeded ensure your API_KEY is set and valid from (https://openrouter.ai/keys) or set it in the .env file',
                text_delta=None,
                finish_reason=None,
                usage=None,
            )
            raise RateLimitError
        except APIError:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                error='API error ensure your API_KEY is set and valid from (https://openrouter.ai/keys) or set it in the .env file',
                text_delta=None,
                finish_reason=None,
                usage=None,
            )


    async def _stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
        t_start = time.perf_counter()
        response: ChatCompletion = await client.chat.completions.create(**kwargs)

        usage = None
        tool_calls: Dict[str, Any] = {}

        async for chunk in response:
            chunk: ChatCompletionChunk = chunk
            if chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
            if not chunk.choices:
                # if no choices then just continue and wait for next chunk
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            finish_reason = None
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            text_delta = None
            reasoning_delta = None
            refusal = None
            if delta.refusal:
                refusal = delta.refusal
            if hasattr(delta, "reasoning") and delta.reasoning:
                reasoning_delta = ReasoningDelta(reasoning=delta.reasoning)
            if delta.content:
                text_delta = TextDelta(content=delta.content)
            if text_delta or reasoning_delta or refusal:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=text_delta,
                    reasoning_delta=reasoning_delta,
                    refusal=refusal,
                    error=None,
                    finish_reason=finish_reason,
                    usage=usage,
                )
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
                        if tool_call_delta.function.arguments:
                            tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
        t_end = time.perf_counter()
        total_time = t_end - t_start if (t_end - t_start) > 0 else None
        if usage and total_time is not None:
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                total_time=total_time,
            )
        _tool_calls: List[ToolCall] = []
        for idx, tool_call in tool_calls.items():
            _tool_calls.append(ToolCall(
                call_id=tool_call["id"],
                name=tool_call["name"],
                arguments=parse_tool_call_arguments(tool_call["arguments"]),
            ))
        yield StreamEvent(
            type=StreamEventType.TOOL_CALL_COMPLETE,
            tool_calls=_tool_calls,
        )
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            usage=usage,
            finish_reason=finish_reason,
        )
        
    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> Union[StreamEvent, None]:
        t_start = time.perf_counter()
        response: ChatCompletion = await client.chat.completions.create(**kwargs)
        t_end = time.perf_counter()
        completion_tokens = None
        prompt_tokens = None
        total_tokens = None
        if hasattr(response, "usage"):
            usage = response.usage
            completion_tokens = usage.completion_tokens
            prompt_tokens = usage.prompt_tokens
            total_tokens = usage.total_tokens

        # select choice
        choice = response.choices[0]
        # get message of the choice
        message = choice.message
        # get content of the message
        content = message.content
        # get refusal of the message
        refusal = message.refusal
        # get annotations of the message
        annotations = message.annotations
        # get tool calls of the message
        tool_calls = message.tool_calls
        # get reasoning of the message
        reasoning = None
        if hasattr(message, "reasoning"):
            reasoning = message.reasoning

        # get finish reason
        finish_reason = None
        if choice.finish_reason:
            finish_reason = choice.finish_reason

        # create the text delta
        text_delta = None
        if content:
            text_delta = TextDelta(content=content)

        # create the reasoning delta
        if reasoning:
            reasoning_delta = ReasoningDelta(reasoning=reasoning)


        # create the tool calls
        tool_calls: List[ToolCall] = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append(ToolCall(
                    call_id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=parse_tool_call_arguments(tool_call.function.arguments),
                ))

        total_time = (t_end - t_start) if (t_end - t_start) > 0 else None
        usage = TokenUsage(
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total_tokens or 0,
            total_time=total_time,
        )

        # return the streaming event
        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            reasoning_delta=reasoning_delta,
            usage=usage,
            finish_reason=finish_reason,
            refusal=refusal,
            annotations=annotations,
            error=None,
            tool_calls=tool_calls,
        )