from dataclasses import dataclass, field
from typing import Dict, Any, Union
from enum import Enum
from pegasus.utils.logger import logger
import json
from typing import List

class StreamEventType(str, Enum):
    TEXT_DELTA = 'text_delta'
    TOOL_CALL_COMPLETE = 'tool_call_complete'
    MESSAGE_COMPLETE = 'message_complete' # always has usage data
    ERROR = 'error'

@dataclass
class TextDelta:
    content: str

    def __add__(self, other: 'TextDelta') -> 'TextDelta':
        return TextDelta(content=self.content + other.content)

    def __str__(self) -> str:
        return self.content


@dataclass
class ReasoningDelta:
    reasoning: str

    def __add__(self, other: 'ReasoningDelta') -> 'ReasoningDelta':
        return ReasoningDelta(reasoning=self.reasoning + other.reasoning)

    def __str__(self) -> str:
        return self.reasoning
    
@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_time: float | None = None  # seconds

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def __sub__(self, other: 'TokenUsage') -> 'TokenUsage':
        return TokenUsage(
            prompt_tokens=self.prompt_tokens - other.prompt_tokens,
            completion_tokens=self.completion_tokens - other.completion_tokens,
            total_tokens=self.total_tokens - other.total_tokens,
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
    arguments: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None = None
    reasoning_delta: ReasoningDelta | None = None
    refusal: str | None = None
    annotations: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    tool_calls: List[ToolCall] = field(default_factory=list)

def merge_text_deltas(deltas: List[TextDelta]) -> TextDelta | None:
    """given a list of text deltas, add all content together."""
    parts = [d.content for d in deltas if d.content]
    return TextDelta(content="".join(parts)) if parts else None


def merge_reasoning_deltas(deltas: List[ReasoningDelta]) -> ReasoningDelta | None:
    """given a list of reasoning deltas, add all reasoning together."""
    parts = [d.reasoning for d in deltas if d.reasoning]
    return ReasoningDelta(reasoning="".join(parts)) if parts else None


def parse_tool_call_arguments(arguments: Union[str, Dict, None]) -> Dict[str, Any]:
    try:
        if not arguments:
            return {}
        if isinstance(arguments, str):
            return json.loads(arguments)
        return arguments
    except Exception as e:
        logger.error(f"Error parsing tool call arguments: {e} with arguments: {arguments}")
        return {}