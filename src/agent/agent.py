from typing import AsyncGenerator
from src.agent.results import AgentEvent, AgentEventType

class Agent:
    def __init__(self) -> None:
        pass
        # keep track of session management

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        pass