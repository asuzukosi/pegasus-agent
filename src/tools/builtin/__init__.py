from .readfile import ReadFileTool
from typing import List
from src.tools.base import Tool
from src.config.config import Config

__all__ = [
    "ReadFileTool",
]

def get_all_builtin_tools(config: Config) -> List[Tool]:
    return [
        ReadFileTool(config),
    ]