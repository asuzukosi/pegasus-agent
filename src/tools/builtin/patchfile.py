from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from typing import List


class FilePatch(BaseModel):
    old_content: str = Field(..., description="The old content of the file")
    new_content: str = Field(..., description="The text to replace old string with. Can be empty to delete the old string.")

class PatchFileParams(BaseModel):
    path: str = Field(..., description="The path to the file to patch")
    patches: List[FilePatch] = Field(..., description="The patches to apply to the file. The patches are applied in order and the old content of the file is the content of the file before the first patch is applied.")
    replace_all: bool = Field(False, description="Whether to replace all occurrences of the old content or just the first one")


class PatchFileTool(Tool):
    name: str = "patch_file"
    description: str = "Patch a file by applying a patch file"
    type: ToolType = ToolType.WRITE
    schema: PatchFileParams = PatchFileParams

    def __init__(self, config: Config) -> None:
        self._config = config

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = PatchFileParams(**invocation.params)
        return ToolResult.success_result(output=f"Patched {params.path} with {params.patch_file}")