from src.tools.builtin.readfile import ReadFileTool
from src.tools.builtin.writefile import WriteFileTool
from src.tools.builtin.editfile import EditFileTool 
# from src.tools.builtin.patchfile import PatchFileTool
from src.tools.builtin.shell import ShellTool

from typing import List
from src.tools.base import Tool
from src.config.config import Config
__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ShellTool",
]

def get_all_builtin_tools(config: Config) -> List[Tool]:
    return [
        ReadFileTool(config),
        WriteFileTool(config),
        EditFileTool(config),
        ShellTool(config),
    ]