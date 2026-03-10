from pathlib import Path
import jinja2
from pegasus.config.config import Config
import json
import os, sys
from datetime import datetime
from pegasus.tools.base import Tool

template_loader = jinja2.FileSystemLoader(searchpath=".")
template_env = jinja2.Environment(loader=template_loader)

def get_system_prompt(config: Config) -> str:
    parts = []
    # identity and role
    parts.append(_get_identity_section(config))
    # environment
    parts.append(_get_environment_section(config))
    # security guidelines
    parts.append(_get_security_guidelines_section(config))
    # operational guidelines
    parts.append(_get_operational_section(config))
    # memory
    parts.append(_get_memory_section(config))
    return "\n\n".join(parts)

def _get_identity_section(config: Config) -> str:
    """
    retreives the identity and role of the agent.
    the identity allows the model to know which parts of its weights it should activate in order to perform the task properly
    """
    config
    template = template_env.get_template("identity.j2")
    return template.render()

def _get_shell_info() -> str:
    """get shell information based on platform."""
    if sys.platform == "darwin":
        return "/bin/zsh"
    elif sys.platform == "win32":
        return "PowerShell/cmd.exe"
    else:
        return "/bin/bash"

def _get_environment_section(config: Config) -> str:
    """
    retreives the environment section of the prompt.
    this determines the environment of the agent and how it should be used.
    """
    config
    template = template_env.get_template("environment.j2")
    cwd = config.cwd.as_posix()
    shell_info = _get_shell_info()
    return template.render({"now": datetime.now(), "os_info": os.uname().sysname, "cwd": cwd, "shell_info": shell_info})

def _get_security_guidelines_section(config: Config) -> str:
    """
    retreives the security guidelines section of the prompt.
    modify security guidelines to ensure the agent is secure and does not harm the user or the system.
    """
    template = template_env.get_template("security_guidelines.j2")
    return template.render()

def _get_operational_section(config: Config) -> str:
    """
    retreives the operational guidelines section of the prompt.
    this determines the tone and style of the agents responses.
    """
    config
    template = template_env.get_template("operational.j2")
    return template.render()

def _get_tools_section(config: Config, tools: list[Tool]) -> str:
    """
    retreives the tools section of the prompt.
    this determines the tools that the agent has access to.
    """
    regular_tools = [t for t in tools if not t.name.startswith("subagent_")]
    subagent_tools = [t for t in tools if t.name.startswith("subagent_")]

    guidelines = ""
    for tool in regular_tools:
        description = tool.description
        if len(description) > 100:
            description = description[:100] + "..."
        guidelines += f"- **{tool.name}**: {description}\n"

    if subagent_tools:
        guidelines += "\n## Sub-Agents\n\n"
        for tool in subagent_tools:
            description = tool.description
            if len(description) > 100:
                description = description[:100] + "..."
            guidelines += f"- **{tool.name}**: {description}\n"
    template = template_env.get_template("tools.j2")
    return template.render({"guidelines": guidelines, "subagent_tools": bool(subagent_tools)})

def _get_memory_section(config: Config) -> str:
    """
    retreives the memory section of the prompt.
    this determines the memory of the agent and how it should be used.
    """
    memory: Path = Path(os.path.join(config.cwd, "pegasus_memory.json"))
    if not memory.exists():
        return ""
    with open(memory, "r") as f:
        memory = json.load(f)
    template = template_env.get_template("memory.j2")
    return template.render({"memory": json.dumps(memory, indent=4)})