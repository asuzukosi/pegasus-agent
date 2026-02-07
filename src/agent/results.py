from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

class AgentEventType(str, Enum):
    # agent lifecycle events
    AGENT_START = 'agent_start'
    AGENT_END = 'agent_end'
    AGENT_ERROR = 'agent_error'

    # text streaming events
    TEXT_DELTA = 'text_delta'
    TEXT_COMPLETE = 'text_complete'



@dataclass
class AgentEvent:
    type: AgentEventType
    data: Dict[str, Any] = field(default_factory=dict)