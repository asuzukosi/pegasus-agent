from src.client.llm_client import LLMClient
from src.client.response import TokenUsage, StreamEventType
from src.context.manager import ContextManager
from src.utils.logger import logger
from typing import Any

class ChatCompressor:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def _format_history_for_compaction(self, messages: list[dict[str, Any]]) -> str:
        # TODO: clean this up to have a better implementation 
        # TODO: add proper tool compaction logic
        # TODO: add proper message compaction
        return "\n".join([f"{message['role']}: {message['content']}" for message in messages])
    
    async def compress(self, context_manager: ContextManager) -> tuple[ str | None, TokenUsage | None]:
        messages = context_manager.get_messages()

        if len(messages) < 3:
            return None, None
        
        compression_message = [
            {
                "role": "system",
                # TODO: add a better system prompt for the chat compressor
                "content": "You are a helpful assistant that compresses context messages into a summary."
            },
            {
                "role": "user",
                # TODO: add a better prompt for efficiently compress the previous data
                "content": "Compress the following context messages into a summary: " + self._format_history_for_compaction(messages)
            }
        ]
        
        try:
            summary = ""
            usage = None
            async for event in self._client.chat_completion(messages=compression_message, 
                                         stream=False):
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
                    summary += event.text_delta.content
            if not summary or not usage:
                logger.error(f"Failed to compress context: {e}")
                return None, None
            return summary, usage
        except Exception as e:
            return None, None
