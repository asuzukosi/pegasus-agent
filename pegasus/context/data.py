from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List
from datetime import datetime
from pegasus.tools.data import ToolImage

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

@dataclass
class MessageItem:
    role: MessageRole
    content: str
    images: List[ToolImage] = field(default_factory=list)
    tool_call_id: str | None = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    token_count: int | None = None
    pruned_at: datetime | None = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"role": self.role.value}
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        content: str = self.content if self.content else ""
        if len(self.images) > 0:
            content: list[dict[str, Any]] = [{"type": "text", "text": content}] if content else []
            for image in self.images:
                content.append(image.to_content_part())
        result["content"] = content
        return result

@dataclass
class ToolResultMessage:
    tool_call_id: str
    content: str
    is_error: bool = False
    images: list[ToolImage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        content: str = self.content if self.content else ""
        if len(self.images) > 0:
            content: list[dict[str, Any]] = [{"type": "text", "text": content}] if content else []
            for image in self.images:
                content.append(image.to_content_part())
        result: Dict[str, Any] = {"role": "tool", "tool_call_id": self.tool_call_id, "content": content}
        return result