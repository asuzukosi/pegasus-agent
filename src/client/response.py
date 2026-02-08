from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum
import json

class StreamEventType(str, Enum):
    TEXT_DELTA = 'text_delta'
    TOOL_CALL_START = 'tool_call_start'
    TOOL_CALL_DELTA = 'tool_call_delta'
    TOOL_CALL_COMPLETE = 'tool_call_complete'
    MESSAGE_COMPLETE = 'message_complete'
    ERROR = 'error'

@dataclass
class TextDelta:
    content: str
    
    def __str__(self) -> str:
        return self.content

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens
        )

    def __sub__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens - other.prompt_tokens,
            completion_tokens=self.completion_tokens - other.completion_tokens,
            total_tokens=self.total_tokens - other.total_tokens,
            cached_tokens=self.cached_tokens - other.cached_tokens
        )

@dataclass
class ToolCallDelta:
    call_id: str
    name: str | None = None
    arguments_delta: str = ""

@dataclass
class ToolCall:
    call_id: str
    name: str | None = None
    arguments: Dict[str, Any] = {}

@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None = None
    error: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    tool_call_delta: ToolCallDelta | None = None
    tool_call: ToolCall | None = None

def parse_tool_call_arguments(arguments: str) -> Dict[str, Any]:
    if not arguments:
        return {}
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return {'raw_arguments': arguments}