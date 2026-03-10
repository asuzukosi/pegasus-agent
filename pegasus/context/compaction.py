from pegasus.client.llm_client import LLMClient
from pegasus.client.response import TokenUsage, StreamEventType
from pegasus.context.manager import ContextManager
from pegasus.utils.logger import logger
from typing import Any

class ChatCompressor:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def _render_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    parts.append(str(item))
                    continue
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return " ".join(part for part in parts if part).strip()
        return str(content)

    def _format_history_for_compaction(self, messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for message in messages:
            rendered_content = self._render_content(message.get("content", ""))
            if not rendered_content:
                continue
            tool_call_id = message.get("tool_call_id")
            prefix = message.get("role", "unknown")
            if tool_call_id:
                prefix = f"{prefix}({tool_call_id})"
            lines.append(f"{prefix}: {rendered_content}")
        return "\n".join(lines)
    
    async def compress(self, context_manager: ContextManager) -> tuple[ str | None, TokenUsage | None]:
        messages = context_manager.get_messages()[1:]

        if len(messages) < 3:
            return None, None
        
        compression_message = [
            {
                "role": "system",
                "content": (
                    "You compress long assistant conversations into a concise working summary. "
                    "Preserve trajectory, semantics, and instructional information with high fidelity. "
                    "Keep user goals, task progress, key constraints, decisions, important facts, relevant tool outputs, "
                    "open questions, pending work, and anything the agent must remember to continue correctly."
                ),
            },
            {
                "role": "user",
                "content": (
                    "compress the following conversation history into a compact but high-signal summary "
                    "that can replace older context while preserving continuity. "
                    "the summary must retain: "
                    "1. trajectory: what has already been tried, discovered, changed, or decided. "
                    "2. semantics: the actual meaning of prior observations, results, errors, and tool outputs. "
                    "3. instructional information: user requirements, constraints, preferences, and explicit do or do not rules.\n\n"
                    + self._format_history_for_compaction(messages)
                ),
            }
        ]
        
        try:
            summary = ""
            usage = None
            async for event in self._client.chat_completion(messages=compression_message, stream=False):
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
                    if event.text_delta and event.text_delta.content:
                        summary += event.text_delta.content
            summary = summary.strip()
            if not summary or not usage:
                logger.error("failed to compress context: missing summary or usage")
                return None, None
            return summary, usage
        except Exception as e:
            logger.error(f"failed to compress context: {e}")
            return None, None
