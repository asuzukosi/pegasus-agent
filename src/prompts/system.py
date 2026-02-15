from pathlib import Path
import jinja2
from src.config.config import Config
import json
import os


template_loader = jinja2.FileSystemLoader(searchpath="prompts")
template_env = jinja2.Environment(loader=template_loader)

def get_system_prompt(config: Config) -> str:
    parts = []

    # identity and role
    parts.append(_get_identity_section(config))

    # agents.md section
    parts.append(_get_agents_section(config))

    # security guidelines
    parts.append(_get_security_guidelines_section(config))

    if config.user_instructions:
        parts.append(config.user_instructions)
    if config.developer_instructions:
        parts.append(config.developer_instructions)


    # operational guidelines
    parts.append(_get_operational_section(config))

    # TODO: add token optimization tracking for the memory system so the llm is not clogged with information
    parts.append(_get_memory_section(config))



    # return the combined prompt
    return "\n\n".join(parts)

def _get_identity_section(config: Config) -> str:
    """
    retreives the identity and role of the agent.
    the identity allows the model to know which parts of its weights it should activate in order to perform the task properly
    """
    config
    template = template_env.get_template("identity.j2")
    return template.render()

def _get_agents_section(config: Config) -> str:
    """
    retreives the agents.md section of the prompt.
    the agents.md file is a file usually provided by the user to describe the project the agent and its roles in it. 
    it is a project spec used by the agent
    """
    config
    template = template_env.get_template("agents.j2")
    return template.render()

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

def _get_memory_section(config: Config) -> str:
    """
    retreives the memory section of the prompt.
    this determines the memory of the agent and how it should be used.
    """
    memory = os.path.join(config.cwd, "memory.json")
    with open(memory, "r") as f:
        memory = json.load(f)
    template = template_env.get_template("memory.j2", {"memory": memory})
    return template.render()