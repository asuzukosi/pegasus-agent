from typing import List, Dict, Any
from src.context.data import MessageItem, MessageRole, ToolResultMessage
from src.prompts.system import get_system_prompt
from src.utils.text import count_tokens
from src.config.config import Config
from src.client.response import TokenUsage


class ContextManager:
    PRUNE_PROTECT_TOKENS = 40_000
    PRUNE_MINIMUM_TOKENS = 20_000
    
    def __init__(self, config: Config) -> None:
        self._config = config
        self._system_prompt = get_system_prompt()
        self._messages: List[MessageItem] = []
        self._model_name: str | None = None
        self._latest_usage: TokenUsage | None = TokenUsage()
        self._total_usage: TokenUsage | None = TokenUsage()

    def add_user_message(self, content: str, tool_calls: List[Dict[str, Any]] | None = None) -> None:
        item = MessageItem(
            role=MessageRole.USER,
            content=content or "", 
            token_count=count_tokens(content or "", self._model_name or ""),
            tool_calls=tool_calls or []
        )
        self._messages.append(item)
 
    def add_assistant_message(self, content: str) -> None:
        item = MessageItem(
            role=MessageRole.ASSISTANT,
            content=content or "", 
            token_count=count_tokens(content or "", self._model_name or "")
        )
        self._messages.append(item)
 
    def get_messages(self) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        for item in self._messages:
            messages.append(item.to_dict())
        return messages
    
    def add_tool_result(self, tool_result: ToolResultMessage) -> None:
        item = MessageItem(
            role=MessageRole.TOOL,
            content=tool_result.content,
            tool_call_id=tool_result.tool_call_id,
            token_count=count_tokens(tool_result.content or "", self._model_name or "")
        )
        self._messages.append(item)

    def set_latest_usage(self, usage: TokenUsage) -> None:
        self._latest_usage = usage

    def add_usage(self, usage: TokenUsage) -> None:
        self._total_usage = self._total_usage + usage if self._total_usage else usage

    def needs_compression(self) -> bool:
        context_limit = self._config.model.context_window
        current_tokens = self._latest_usage.total_tokens

        return current_tokens > (context_limit * 0.8)
    
    def replace_with_compressed_summary(self, summary: str) -> None:
        self._messages = []
        # TODO: adjust the prompt and save it in the prompting library
        compaction_message = f"The following is a compressed summary of the previous context: {summary}"
        assistant_message = f"I acknowledge that the previous context has been compressed. I will now proceed with the conversation."
        self.add_user_message(compaction_message)
        self.add_assistant_message(assistant_message)

    def prune_tool_outputs(self) -> None:
        user_message_count = sum(1 for message in self._messages if message.role == MessageRole.USER)
        if user_message_count < 2:
            return 0
        total_tokens = 0
        prune_tokens = 0
        to_prune: List[MessageItem] = []
        for msg in reversed(self._messages):
            if msg.pruned_at:
                break
            if msg.role == MessageRole.TOOL and msg.tool_call_id:
                tokens = msg.token_count or count_tokens(msg.content or "", self._model_name or "")
                total_tokens += tokens
                if total_tokens > self.PRUNE_PROTECT_TOKENS:
                    prune_tokens += tokens
                    to_prune.append(msg)

        if prune_tokens < self.PRUNE_MINIMUM_TOKENS:
            return 0
        
        pruned_count = 0
        for msg in to_prune:
            msg.content = '[Old tool result content cleared]'
            msg.token_count = count_tokens(msg.content or "", self._model_name or "")
            pruned_count += 1


        return pruned_count


