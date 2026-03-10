from typing import List
from pegasus.tools.base import Tool
from pegasus.tools.builtin.readfile import ReadFileTool
from pegasus.tools.builtin.writefile import WriteFileTool
from pegasus.tools.builtin.editfile import EditFileTool 
from pegasus.tools.builtin.shell import ShellTool
from pegasus.tools.builtin.websearch import WebSearchTool
from pegasus.tools.builtin.todos import TodosTool
from pegasus.tools.builtin.memory import MemoryTool 
from pegasus.tools.builtin.browser_use import BrowserUseTool
from pegasus.tools.builtin.vision_capture import VisionCaptureTool
from pegasus.tools.builtin.mcp_executor import MCPExecutorTool
from pegasus.tools.builtin.subagent import SubAgentTool

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
