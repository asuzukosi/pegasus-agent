from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult, FileDiff
from src.config.config import Config
from pydantic import BaseModel, Field
from src.utils.paths import resolve_path, ensure_parent_directory
from pathlib import Path
class EditIfFileParams(BaseModel):
    path: str = Field(..., description="The path to the file to edit")
    old_string: str = Field(..., description="The exact text to find and replace Must match exactly (including whitespace and identation) and must be unique in the file unless replace_all is true")
    new_string: str = Field(..., description="The text to replace old string with. Can be empty to delete the old string.")
    replace_all: bool = Field(False, description="Whether to replace all occurrences of the old_string or just the first one")

class EditFileTool(Tool):
    name: str = "edit_file"
    description: str = "Edit a file by replacing text. The `old_string` must match exactly "\
    "(including whitespace and identation) and must be unique in the file" \
    "unless replace_all is true. Use this for precise, surgical edits. "\
    "For creating new files or complete rewrites, use write_file instead."
    type: ToolType = ToolType.WRITE
    schema: EditIfFileParams = EditIfFileParams


    def __init__(self, config: Config) -> None:
        self._config = config

    def _no_match_error(self, old_string:str, content:str, path: Path) -> str:
        lines =  content.splitlines()
        partial_matches = []
        search_terms = old_string.splitlines()[:5]

        if search_terms:
            first_term = search_terms[0]
            for i, line in enumerate(lines, 1):
                if first_term in line:
                    partial_matches.append((i, line.strip()[:80]))
                    if len(partial_matches) >= 3:
                        break
        error_msg = f"old_string not found in file: {path.as_posix()}"
        if partial_matches:
            error_msg += f"\n\nPossible similar lines:\n"
            for line_num, line_preview in partial_matches:
                error_msg += f"\n Line {line_num}: {line_preview}"
            error_msg += f"\n\nMake sure old_string matches exactly (including whitespace and indentation)."
        else:
            error_msg += f"\n\nMake sure old_string matches exactly (including whitespace, indentation, line breaks and any invisible characters).Try reading the file again."
        return ToolResult.error_result(error_msg)

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = EditIfFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        if not path.exists() and not params.old_string:
            return ToolResult.error_result(f"File does not exist: {path.as_posix()}")
        file_exists = path.exists()
        if not file_exists:
            # TODO: the edit file tool should not be able to create a new file with the edit_file tool, we will remove this later
            path: Path = ensure_parent_directory(path)
            path.touch()
            path.write_text(params.new_string, encoding="utf-8")
            line_count = len(params.new_string.splitlines())
            byte_count = len(params.new_string.encode("utf-8"))
            return ToolResult.success_result(f"Created {path} {line_count} lines", 
                                             diff = FileDiff(path=path, old_content="", new_content=params.new_string, is_new_file=True, is_deletion=False), 
                                             metadata=dict(path=str(path.as_posix()), is_new_file=True, lines=line_count, bytes=byte_count))
        
        old_content = path.read_text(encoding="utf-8")
        if not old_content:
            return ToolResult.error_result(f"File is empty: {path.as_posix()} use write_file to create a new file")
        occurence_count = old_content.count(params.old_string)
        if occurence_count == 0:
            return self._no_match_error(params.old_string, old_content, path)
        
        if occurence_count > 1 and not params.replace_all:
            return ToolResult.error_result(f"old_string found {occurence_count} times in file: {path.as_posix()}. Use replace_all to replace all occurrences. Provide more context o make the match unique.", metadata=dict(path=str(path.as_posix()), occurence_count=occurence_count))
        
        if params.replace_all:
            new_content = old_content.replace(params.old_string, params.new_string)
            replaced_count = occurence_count
        else:
            new_content = old_content.replace(params.old_string, params.new_string, 1)
            replaced_count = 1
        if new_content == old_content:
            return ToolResult.error_result(f"No changes made to file: {path.as_posix()} old string is the same as new string. Check old_string and new_string.")
        path.write_text(new_content, encoding="utf-8")
        new_line_count = len(new_content.splitlines())
        old_line_count = len(old_content.splitlines())
        line_diff = new_line_count - old_line_count
        diff_message = ""
        if line_diff > 0:
            diff_message += f"+{line_diff} lines\n"
        elif line_diff < 0:
            diff_message += f"-{line_diff} lines\n"
        diff = FileDiff(path=path, old_content=old_content, new_content=new_content, is_new_file=file_exists, is_deletion=False)
        return ToolResult.success_result(output=f"Edited {path.as_posix()} {new_line_count} lines. {diff_message}", metadata=dict(path=str(path.as_posix()), is_new_file=file_exists, 
                                                                                                              lines=new_line_count,
                                                                                                              replaced_count=replaced_count), 
                                                                                                              diff=diff)
    

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error executing edit_file tool with error: {e}")   