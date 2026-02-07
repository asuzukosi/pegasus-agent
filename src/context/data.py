from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

@dataclass
class MessageItem:
    role: MessageRole
    content: str
    token_count: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
        }
