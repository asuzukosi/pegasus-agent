from typing import List
from src.tools.base import Tool
from src.tools.builtin.readfile import ReadFileTool
from src.tools.builtin.writefile import WriteFileTool
from src.tools.builtin.editfile import EditFileTool 
from src.tools.builtin.shell import ShellTool
from src.tools.builtin.websearch import WebSearchTool
from src.tools.builtin.todos import TodosTool
from src.tools.builtin.memory import MemoryTool 
from src.tools.builtin.browser_use import BrowserUseTool
from src.tools.builtin.vision_capture import VisionCaptureTool
from src.tools.builtin.mcp_executor import MCPExecutorTool
from src.tools.builtin.subagent import SubAgentTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ShellTool",
    "WebSearchTool",
    "MemoryTool",
    "TodosTool",
    "BrowserUseTool",
    "VisionCaptureTool",
    "MCPExecutorTool",
    "SubAgentTool",
]

def get_all_builtin_tools() -> List[Tool]:
    return [
        ReadFileTool,
        WriteFileTool,
        ShellTool,
        EditFileTool,
        WebSearchTool,
        MemoryTool,
        TodosTool,
        BrowserUseTool,
        VisionCaptureTool,
        MCPExecutorTool,
        SubAgentTool,
    ]
