from .readfile import ReadFileTool
from .writefile import WriteFileTool
from typing import List
from src.tools.base import Tool
from src.config.config import Config

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
]

def get_all_builtin_tools(config: Config) -> List[Tool]:
    return [
        ReadFileTool(config),
        WriteFileTool(config),
    ]