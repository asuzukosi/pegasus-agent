from src.config.config import Config
from src.config.config import HookConfig
from typing import List, Any
from src.config.config import HookTrigger
import asyncio
import os
import sys
import signal
import tempfile

class HookSystem:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._hooks: List[HookConfig] = config.hooks
        if not self._config.hooks_enabled:
            return 
        self._hooks = [hook for hook in self._hooks if hook.enabled]

    async def _run_command(self, command: str, env: dict[str, str]) -> None:
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self._config.cwd, env=env, start_new_session=True)
        try:
            await asyncio.wait_for(process.communicate(), timeout=self._config.timeout)
        except asyncio.TimeoutError:
            if sys.platform == "win32":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.kill()

    async def _run_script(self, script: str, env: dict[str, str]) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh')as temp_file:
            temp_file.write("#!/bin/sh\n")
            temp_file.write(script)
            script_path = temp_file.name
            try:
                os.chmod(script_path, 0o755)
                await self._run_command(script_path, env)
            except Exception as e:
                raise e
            finally:
                os.unlink(script_path)

    async def _run_hook(self, hook: HookConfig, env: dict[str, str]) -> None:
        if hook.command:
            self._run_command(hook.command, env)
        else:
            await self._run_script(hook.script, env)


    def _build_env(self, trigger: HookTrigger, tool_name: str | None = None, user_message: str | None = None, exception: Exception | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env['AI_AGENT_TRIGGER'] = trigger.value
        env['AI_AGENT_CWD'] = str(self._config.cwd)
        if tool_name:
            env['AI_AGENT_TOOL_NAME'] = tool_name
        if user_message:
            env['AI_AGENT_USER_MESSAGE'] = user_message
        if exception:
            env['AI_AGENT_EXCEPTION'] = str(exception)
        return env

    def trigger_before_agent(self, message: str) -> None:
        env = self._build_env(HookTrigger.BEFORE_AGENT, user_message=message)
        for hook in self._hooks:
            if hook.trigger == HookTrigger.BEFORE_AGENT:
                self._run_hook(hook, env)

    def trigger_before_tool(self, tool_name: str, tool_params: dict[str, Any]) -> None:
        env = self._build_env(HookTrigger.BEFORE_TOOL, tool_name=tool_name, tool_params=tool_params)
        for hook in self._hooks:
            if hook.trigger == HookTrigger.BEFORE_TOOL:
                self._run_hook(hook, env)
     
    def trigger_after_tool(self, tool_name: str, tool_params: dict[str, Any]) -> None:
        env = self._build_env(HookTrigger.AFTER_TOOL, tool_name=tool_name, tool_params=tool_params)
        for hook in self._hooks:
            if hook.trigger == HookTrigger.AFTER_TOOL:
                self._run_hook(hook, env)
     
    def trigger_after_agent(self, message: str) -> None:
        env = self._build_env(HookTrigger.AFTER_AGENT, user_message=message)
        for hook in self._hooks:
            if hook.trigger == HookTrigger.AFTER_AGENT:
                self._run_hook(hook, env)