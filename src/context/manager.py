from typing import List, Dict, Any
from src.context.data import MessageItem, MessageRole, ToolResultMessage
from src.prompts.system import get_system_prompt
from src.utils.text import count_tokens
from src.config.config import Config
from src.client.response import TokenUsage
from src.tools.data import ToolImage


class ContextManager:
    PRUNE_PROTECT_TOKENS = 40_000
    PRUNE_MINIMUM_TOKENS = 20_000
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.system_prompt = get_system_prompt(config)
        self._messages: List[MessageItem] = []
        self.model_name: str | None = config.model_name
        self.current_usage: TokenUsage = TokenUsage()
        self.latest_usage: TokenUsage = TokenUsage()
        self.total_usage: TokenUsage = TokenUsage()

    def _message_token_count(self, content: str) -> int:
        return count_tokens(content or "", self.model_name or "")

    def _refresh_current_usage(self) -> None:
        total_tokens = self._message_token_count(self.system_prompt or "")
        for message in self._messages:
            if message.token_count is None:
                message.token_count = self._message_token_count(message.content or "")
            total_tokens += message.token_count
        self.current_usage = TokenUsage(total_tokens=total_tokens)

    def add_user_message(
        self,
        content: str,
        tool_calls: List[Dict[str, Any]] | None = None,
        images: List[ToolImage] | None = None,
    ) -> None:
        item = MessageItem(
            role=MessageRole.USER,
            content=content or "", 
            token_count=self._message_token_count(content or ""),
            tool_calls=tool_calls or [],
            images=images or [],
        )
        self._messages.append(item)
        self._refresh_current_usage()
 
    def add_assistant_message(self, content: str, tool_calls: List[Dict[str, Any]] | None = None) -> None:
        item = MessageItem(
            role=MessageRole.ASSISTANT,
            content=content or "", 
            token_count=self._message_token_count(content or ""),
            tool_calls=tool_calls or []
        )
        self._messages.append(item)
        self._refresh_current_usage()
 
    def get_messages(self) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        for item in self._messages:
            messages.append(item.to_dict())
        return messages
    
    def add_tool_result(self, tool_result: ToolResultMessage) -> None:
        item = MessageItem(
            role=MessageRole.TOOL,
            content=tool_result.content or "",
            token_count=self._message_token_count(tool_result.content or ""),
            tool_call_id=tool_result.tool_call_id,
        )
        self._messages.append(item)
        self._refresh_current_usage()

    def set_usage(self, usage: TokenUsage) -> None:
        self.total_usage += usage
        self.latest_usage = usage
        self._refresh_current_usage()

    def current_context_tokens(self) -> int:
        self._refresh_current_usage()
        return self.current_usage.total_tokens

    def needs_compression(self) -> bool:
        context_limit = self.config.model.context_window
        if not context_limit:
            return False
        return self.current_context_tokens() > int(context_limit * 0.8)

    def replace_with_compressed_summary(self, summary: str, preserve_last_n: int = 2) -> None:
        preserved_messages = self._messages[-preserve_last_n:] if preserve_last_n > 0 else []
        self._messages = []
        self.add_user_message(
            "compressed summary of previous context:\n" + summary,
        )
        self.add_assistant_message(
            "understood. i will use this compressed summary together with the preserved recent context."
        )
        self._messages.extend(preserved_messages)
        self._refresh_current_usage()

   
    def clear(self) -> None:
        self._messages = []
        self.current_usage = TokenUsage()
        self.latest_usage = TokenUsage()
        self.total_usage = TokenUsage()

