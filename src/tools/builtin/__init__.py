from .readfile import ReadFileTool
from typing import List
from src.tools.base import Tool

__all__ = [
    "ReadFileTool",
]

def get_all_builtin_tools() -> List[Tool]:
    return [
        ReadFileTool(),
    ]