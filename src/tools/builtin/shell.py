from src.tools.base import Tool
from src.tools.data import ToolType, ToolInvocation, ToolResult
from src.config.config import Config
from pydantic import BaseModel, Field
from pathlib import Path
import asyncio
import fnmatch
import sys
import os

class ShellParams(BaseModel):
    command: str = Field(..., description="The command to run")
    cwd: str = Field(None, description="The current working directory to run the command in. If not provided, the current working directory will be used.")
    timeout: int = Field(120, ge=1, le=600, description="The timeout in seconds for the command (default 120 seconds, max 600 seconds, min 1 second)")


BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
}

class ShellTool(Tool):
    name: str = "shell"
    description: str = "Execute a shell command. Use this for running commands, scripts and cli tools"
    type: ToolType = ToolType.BASH
    schema: ShellParams = ShellParams

    def __init__(self, config: Config) -> None:
        self._config = config

    def _build_environment(self) -> dict[str, str]:
        env = os.environ.copy()
        shell_environment = self._config.shell_environment
        # remove default excludes
        if shell_environment.ignore_default_excludes:
            for pattern in shell_environment.exclude_patterns:
                keys_to_remove = [k for k in env.keys() if fnmatch.fnmatch(k.upper(), pattern.upper())]
                for key in keys_to_remove:
                    del env[key]
        # add set vars
        if shell_environment.set_vars:
            env.update(shell_environment.set_vars)
        return env

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ShellParams(**invocation.params)
        if params.command.lower().strip() in BLOCKED_COMMANDS:
            return ToolResult.error_result(f"Command is blocked: {params.command}", metadata=dict(blocked=True))
        if params.cwd:
            cwd = Path(params.cwd)
            if not cwd.is_absolute():
                cwd = invocation.cwd / cwd
        else:
            cwd = invocation.cwd
        
        if not cwd.exists():
            return ToolResult.error_result(f"Current working directory does not exist: {cwd}", metadata=dict(cwd=str(cwd.as_posix())))

        env = self._build_environment()
        if sys.platform == "win32":
            command = ["cmd.exe", "/c", params.command]
        else:
            command = ["bash", "-c", params.command]

        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd, env=env, start_new_session=True)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=params.timeout)
        except asyncio.TimeoutError:
            if sys.platform == "win32":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.kill()
            return ToolResult.error_result(f"command timed out: {params.command} in {params.timeout} seconds", metadata=dict(timeout=params.timeout))

        stdout = stdout.decode("utf-8", errors="replace").strip()
        stderr = stderr.decode("utf-8", errors="replace").strip()
        exit_code = process.returncode
        
        output = ""
        truncated = False
        if stdout.strip():
            output += stdout.rstrip()
        if stderr.strip():
            output += "\n--- stderr ---\n" + stderr.rstrip()
        if exit_code != 0:
            output += f"\n--- exit code ---\n{exit_code}"

        if len(output) > 100 * 1024:
            output = output[:100 * 1024] + "\n...truncated..."
            truncated = True
        
        return ToolResult(
            success=exit_code == 0,
            error=stderr if exit_code != 0 else None,
            exit_code=exit_code,
            output=output,
            truncated=truncated,
        )


    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"Error executing shell tool with error: {e}")