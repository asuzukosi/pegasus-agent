import os
import asyncio
from typing import Any, Dict, List, AsyncGenerator
from openai import AsyncOpenAI

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

    async def chat_completion(self, 
                              messages: List[Dict[str, Any]], 
                              stream: bool = False):
        client: AsyncOpenAI = self._get_client()
        kwargs: Dict[str, Any] = {
            'model': 'gpt-4o-mini',
            'messages': messages,
            'stream': stream
        }
        if stream:
            return self._stream_response(client, kwargs)
        else:
            return await self._non_stream_response(client, kwargs)

    async def _stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> AsyncGenerator[str, None]:
        pass

    async def _non_stream_response(self, client: AsyncOpenAI, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content