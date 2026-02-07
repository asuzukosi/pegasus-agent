import os
import asyncio
from src.client.response import TextDelta, TokenUsage, StreamEvent, EventType
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

    @retry(exceptions=RateLimitError, tries=3, delay=1, backoff=2)
    async def chat_completion(self, 
                              messages: List[Dict[str, Any]], 
                              stream: bool = False) -> AsyncGenerator[StreamEvent, None]:
        client: AsyncOpenAI = self._get_client()
        kwargs: Dict[str, Any] = {
            'model': 'gpt-4o-mini',
            'messages': messages,
            'stream': stream
        }
        try:
            if stream:
                async for event in self._stream_response(client, kwargs):
                    yield event
            else:
                yield await self._non_stream_response(client, kwargs)
        except RateLimitError:
            yield StreamEvent(
                type=EventType.ERROR,
                error='Rate limit exceeded',
                text_delta=None,
                finish_reason=None,
                usage=None,
            )
            raise RateLimitError
        except APIError:
            yield StreamEvent(
                type=EventType.ERROR,
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
            if choice.delta.content:
                text_delta = TextDelta(content=choice.delta.content)
            if text_delta is not None:
                yield StreamEvent(
                    type=EventType.TEXT_DELTA,
                    text_delta=text_delta,
                    error=None,
                    finish_reason=finish_reason,
                    usage=usage,
                )

    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> Union[StreamEvent, None]:
        response: ChatCompletion = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # create the text delta
        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

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
            type=EventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            usage=usage,
            finish_reason=finish_reason,
            error=None,
        )