"""
Pegasus - A lightweight terminal agent framework
"""

from pegasus.agent.agent import Agent
from pegasus.agent.results import AgentEvent, AgentEventType
from pegasus.config.config import Config, ModelConfig
from pegasus.session.session import Session
from pegasus.cli.cli import run_cli

__version__ = "0.1.0"
__all__ = [
    "Agent",
    "AgentEvent",
    "AgentEventType",
    "Config",
    "ModelConfig",
    "Session",
    "run_cli",
]
