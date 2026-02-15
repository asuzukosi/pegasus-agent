from src.tools.builtin.readfile import ReadFileTool
from src.tools.builtin.writefile import WriteFileTool
from src.tools.builtin.editfile import EditFileTool 
# from src.tools.builtin.patchfile import PatchFileTool
from src.tools.builtin.shell import ShellTool
from src.tools.builtin.listdir import ListDirTool
from src.tools.builtin.grep import GrepTool
from src.tools.builtin.glob import GlobTool
from src.tools.builtin.websearch import WebSearchTool
from src.tools.builtin.webfetch import WebFetchTool
from src.tools.builtin.todos import TodosTool
from src.tools.builtin.memory import MemoryTool # TODO: explore other types of memory architectures
from typing import List
from src.tools.base import Tool
from src.config.config import Config
from src.tools.subagents import SubAgentTool, CODE_REVIEWER, CODE_INVESTIGATOR, SubAgentDefinition
__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "MemoryTool",
    "TodosTool",
]

def get_all_builtin_tools(config: Config) -> List[Tool]:
    return [
        ReadFileTool(config),
        WriteFileTool(config),
        EditFileTool(config),
        ShellTool(config),
        ListDirTool(config),
        GrepTool(config),
        GlobTool(config),
        WebSearchTool(config),
        WebFetchTool(config),
        MemoryTool(config),
        TodosTool(config),
    ]

def get_default_sub_agent_definitions(config: Config) -> List[SubAgentDefinition]:
    return [
        CODE_REVIEWER,
        CODE_INVESTIGATOR,
    ]