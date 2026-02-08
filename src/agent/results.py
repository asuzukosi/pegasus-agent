from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List
from src.client.response import TokenUsage

class AgentEventType(str, Enum):
    # agent lifecycle events
    AGENT_START = 'agent_start'
    AGENT_END = 'agent_end'
    AGENT_ERROR = 'agent_error'

    # text streaming events
    TEXT_DELTA = 'text_delta'
    TEXT_COMPLETE = 'text_complete'

    # tool call events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"



@dataclass
class AgentEvent:
    type: AgentEventType
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def agent_start(cls, message: str) -> 'AgentEvent':
        return cls(type=AgentEventType.AGENT_START, data={'message': message})
    
    @classmethod
    def agent_end(cls, response: str| None, usage: TokenUsage) -> 'AgentEvent':
        return cls(type=AgentEventType.AGENT_END, data={'response': response, 'usage': usage.__dict__ if usage else None})
    
    @classmethod
    def agent_error(cls, error: str, details: dict[str, Any]) -> 'AgentEvent':
        return cls(type=AgentEventType.AGENT_ERROR, data={'error': error, 'details': details})
    
    @classmethod
    def text_delta(cls, content: str) -> 'AgentEvent':
        return cls(type=AgentEventType.TEXT_DELTA, data={'content': content})
    
    @classmethod
    def text_complete(cls, content: str) -> 'AgentEvent':
        return cls(type=AgentEventType.TEXT_COMPLETE, data={'content': content})
    
    @classmethod
    def tool_call_start(cls, call_id: str, name: str, arguments: Dict[str, Any]) -> 'AgentEvent':
        return cls(
            type=AgentEventType.TOOL_CALL_START,
            data={'call_id': call_id, 'name': name, 'arguments': arguments}
        )
    
    @classmethod
    def tool_call_complete(cls, call_id: str, name: str, success: bool, output: str,metadata: dict[str, Any] = {}, truncated: bool = False, error: str | None=None) -> 'AgentEvent':
        return cls(
            type=AgentEventType.TOOL_CALL_COMPLETE,
            data={'call_id': call_id, 'name': name, 'success': success, 'output': output,
                   'metadata': metadata, 'truncated': truncated, 'error': error if error else None}
        )
    