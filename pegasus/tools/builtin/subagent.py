from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from pegasus.runtime.results import AgentEventType
from pegasus.config.config import Config
from pegasus.tools.base import Tool
from pegasus.tools.data import ToolInvocation, ToolResult, ToolType
from pegasus.utils.logger import logger


class SubAgentParams(BaseModel):
    goal: str = Field(..., description="The goal or instruction for the subagent to complete.")
    max_turns: int = Field(20, ge=1, le=100, description="The maximum number of turns for the subagent run.")
    timeout_seconds: int = Field(
        300,
        ge=10,
        le=1800,
        description="The maximum runtime in seconds for the subagent run.",
    )


class SubAgentTool(Tool):
    name: str = "subagent"
    description: str = (
        "Delegate a focused goal to a child agent. "
        "The subagent gets the caller's tools, runs its own agentic loop once, and returns its final answer."
    )
    type: ToolType = ToolType.SUB_AGENT
    schema: SubAgentParams = SubAgentParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _run_subagent(self, params: SubAgentParams) -> ToolResult:
        from pegasus.runtime.agent import Agent

        sub_config = Config(**self._config.model_dump(exclude_none=True))
        sub_config.max_turns = params.max_turns

        agent = Agent(sub_config)
        await agent.startup()

        final_response: str | None = None
        tool_names: list[str] = []
        try:
            async def _consume() -> None:
                nonlocal final_response
                async for event in agent.run(params.goal):
                    if event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get("content", "")
                        logger.info(f"subagent final response: {final_response}")
                    elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                        tool_name = event.data.get("name")
                        if tool_name:
                            tool_names.append(tool_name)
                            logger.info(
                                f"subagent tool call completed: {tool_name} success={event.data.get('success', False)}"
                            )

            await asyncio.wait_for(_consume(), timeout=params.timeout_seconds)
        except asyncio.TimeoutError:
            return ToolResult.error_result(
                f"subagent timed out after {params.timeout_seconds} seconds",
                metadata={"timeout_seconds": params.timeout_seconds},
            )
        finally:
            await agent.cleanup()

        output_lines = [
            "subagent completed successfully.",
            f"goal: {params.goal}",
            f"tools used: {', '.join(tool_names) if tool_names else 'none'}",
            "",
            "final response:",
            final_response if final_response else "no final response",
        ]
        return ToolResult.success_result(
            output="\n".join(output_lines),
            metadata={"tool_names": tool_names, "max_turns": params.max_turns},
        )

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = SubAgentParams(**invocation.params)
        return await self._run_subagent(params)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"error executing subagent tool with error: {e}")
