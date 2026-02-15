from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from typing import List
from src.client.response import ToolCall
from dataclasses import dataclass
from src.agent.agent import Agent
from typing import AsyncGenerator
from src.agent.results import AgentEvent, AgentEventType
from copy import deepcopy
import asyncio


@dataclass
class SubAgentDefinition:
    name: str # sub agent name
    description: str # sub agent description
    goal_prompt: str # sub agent goal prompt which defines the identity of the agent
    allowed_tools: list[str] | None = None # list of tool names that the sub agent is allowed to use
    max_turns: int = 20 # max turns for the sub agent to run
    timeout: int = 600 # timeout in seconds for the sub agent to run

class SubAgentParams(BaseModel):
    task: str = Field(..., description="The task that the sub agent should perform")

class SubAgentTool(Tool):
    name: str = "sub_agent"
    description: str = "A tool to interact with a sub agent"
    type: ToolType = ToolType.SUB_AGENT
    schema: SubAgentParams = SubAgentParams

    def __init__(self, config: Config, definition: SubAgentDefinition) -> None:
        self._config = config
        self._definition = definition

    @property
    def name(self) -> str:
        return self._definition.name
    
    @property
    def description(self) -> str:
        return self._definition.description
    
    @property
    def goal_prompt(self) -> str:
        return self._definition.goal_prompt
    
    @property
    def is_mutating(self) -> bool:
        return True
    
    async def _agent_loop(self) -> AsyncGenerator[AgentEvent, None]:
        sub_config = deepcopy(self._config)
        sub_config.max_turns = self._definition.max_turns
        sub_config.timeout = self._definition.timeout
        sub_config.allowed_tools = self._definition.allowed_tools

        tool_calls: List[ToolCall] = []
        final_response: str | None = None
        error = None
        terminate_reason: str | None = 'goal_reached'
        with Agent(sub_config) as agent:
            deadline = asyncio.get_event_loop().time() + sub_config.timeout
            sub_agent: Agent = agent
            async for event in sub_agent.run(self.goal_prompt):
                if asyncio.get_event_loop().time() > deadline:
                    terminate_reason = 'timeout'
                    break
                if event.type == AgentEventType.TEXT_COMPLETE:
                    final_response = event.data['content']
                elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                    tool_calls.append(ToolCall(call_id=event.data['call_id'], name=event.data['name'], arguments=event.data['arguments']))
                elif event.type == AgentEventType.AGENT_ERROR:
                    error = event.data['error']
                    final_response = f"Error executing sub agent tool with error: {error}"
                    terminate_reason = 'error'
                elif event.type == AgentEventType.AGENT_END:
                    break

        result = f""" sub agent {self.name} terminated with reason: {terminate_reason}
        tools called: {tool_calls}
        final response: {final_response}
        error: {error}
        """
        return ToolResult.success_result(result, metadata=dict(terminate_reason=terminate_reason, error=error))

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = SubAgentParams(**invocation.params)
        if not params.task:
            return ToolResult.error_result("Missing required parameter: goal")
        try:
            return await self._agent_loop()
        except Exception as e:
            return ToolResult.error_result(f"Error executing sub agent tool with error: {e}")

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error executing sub agent tool with error: {e}")
        


CODE_REVIEWER = SubAgentDefinition(
    name="code_reviewer",
    description="A sub agent that reviews code",
    goal_prompt="You are a code reviewer. You are given a code snippet and you need to review it and provide a report.",
    allowed_tools=["writefile", "readfile", "list_dir"],
    max_turns=10,
    timeout=600,
)

CODE_INVESTIGATOR = SubAgentDefinition(
    name="code_investigator",
    description="A sub agent that investigates code",
    goal_prompt="You are a code investigator. You are given a code snippet and you need to investigate it and provide a report.",
    allowed_tools=["writefile", "readfile", "list_dir"],
    max_turns=10,
    timeout=600,
)
