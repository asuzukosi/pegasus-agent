from typing import List, Dict, Any
from src.context.data import MessageItem, MessageRole, ToolResultMessage
from src.prompts.system import get_system_prompt
from src.utils.text import count_tokens
from src.config.config import Config


class ContextManager:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._system_prompt = get_system_prompt()
        self._messages: List[MessageItem] = []
        self._model_name: str | None = None

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