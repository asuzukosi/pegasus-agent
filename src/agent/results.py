from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List
from src.tools.data import FileDiff
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

    # turn  events
    TURN_END = "turn_end"
    TURN_START = "turn_start"   

    # loop events
    LOOP_END = "loop_end"
    LOOP_START = "loop_start"



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
    def tool_call_complete(cls, call_id: str, name: str, success: bool, output: str,metadata: dict[str, Any] = {}, truncated: bool = False, error: str | None=None, diff: FileDiff | None=None, exit_code: int | None=None) -> 'AgentEvent':
        return cls(
            type=AgentEventType.TOOL_CALL_COMPLETE,
            data={'call_id': call_id, 'name': name, 'success': success, 'output': output,
                   'metadata': metadata, 'truncated': truncated, 'error': error if error else None, 'diff': diff if diff else None, 'exit_code': exit_code if exit_code else None}
        )
    
    @classmethod
    def turn_end(cls) -> 'AgentEvent':
        return cls(type=AgentEventType.TURN_END)
    
    @classmethod
    def turn_start(cls) -> 'AgentEvent':
        return cls(type=AgentEventType.TURN_START)
    
    @classmethod
    def loop_end(cls) -> 'AgentEvent':
        return cls(type=AgentEventType.LOOP_END)
    
    @classmethod
    def loop_start(cls) -> 'AgentEvent':
        return cls(type=AgentEventType.LOOP_START)