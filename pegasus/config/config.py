from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import List, Any, Dict
from pathlib import Path
from enum import Enum
from dotenv import load_dotenv
import os

from art import text2art

_GREEN = "\033[32m"

load_dotenv()

class ModelConfig(BaseModel):
    name: str = Field(default="moonshotai/kimi-k2.5")
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    temperature: float = Field(default=1, ge=0, le=2.0)
    context_window: int | None = 262_144
    tool_support: bool = False
    vision_support: bool = False
    nitro_support: bool = False
    cost_per_million_input_tokens: float = 0.0
    cost_per_million_output_tokens: float = 0.0
    api_key: str = Field(default=os.getenv("OPENROUTER_API_KEY"))
    open_source: bool = True

    @property
    def cost_per_input_token(self) -> float:
        """calculate cost per input token."""
        return self.cost_per_million_input_tokens / 1_000_000 if self.cost_per_million_input_tokens else 0.0

    @property
    def cost_per_output_token(self) -> float:
        """calculate cost per output token."""
        return self.cost_per_million_output_tokens / 1_000_000 if self.cost_per_million_output_tokens else 0.0

    def __str__(self) -> str:
        art_title = f"{_GREEN}{text2art(self.name)}"
        msg = (
            f"{art_title}\n"
            f"  MODEL NAME         : {self.name}\n"
            f"  BASE URL            : {self.base_url}\n"
            f"  TEMPERATURE         : {self.temperature}\n"
            f"  CONTEXT WINDOW      : {self.context_window}\n"
            f"  TOOL SUPPORT        : {self.tool_support}\n"
            f"  VISION SUPPORT      : {self.vision_support}\n"
            f"  NITRO SUPPORT       : {self.nitro_support}\n"
            f"  OPEN SOURCE         : {self.open_source}\n"
            f"  COST/INPUT TOKEN    : ${self.cost_per_input_token:.4f}\n"
            f"  COST/OUTPUT TOKEN   : ${self.cost_per_output_token:.4f}\n"
            f"  COST/MILLION INPUT  : ${self.cost_per_million_input_tokens:.4f}\n"
            f"  COST/MILLION OUTPUT : ${self.cost_per_million_output_tokens:.4f}\n"
            f"  API KEY             : {self.api_key}\n"
        )
        return msg

    def __repr__(self) -> str:
        return self.__str__()

MODEL_OPTIONS: Dict[str, ModelConfig] = {
    # open source large models
    "kimi-k2.5": ModelConfig(name="moonshotai/kimi-k2.5", base_url="https://openrouter.ai/api/v1", temperature=1, context_window=262_144, 
                              tool_support=True, vision_support=True,
                              cost_per_million_input_tokens=0.45, cost_per_million_output_tokens=2.20, nitro_support=False, open_source=True),
    "glm5": ModelConfig(name="z-ai/glm-5", base_url="https://openrouter.ai/api/v1", temperature=1, context_window=202_752, tool_support=True, 
                        vision_support=False,
                        cost_per_million_input_tokens=0.8, cost_per_million_output_tokens=2.56, nitro_support=False, open_source=True),
    "qwen3.5-122b": ModelConfig(name="qwen/qwen3.5-122b-a10b", base_url="https://openrouter.ai/api/v1", temperature=1, 
                                cost_per_million_input_tokens=0.26, cost_per_million_output_tokens=2.08, nitro_support=False,
                                context_window=262_144, tool_support=True, vision_support=True, open_source=True),
    "minimax-m2.5": ModelConfig(name="minimax/minimax-m2.5", base_url="https://openrouter.ai/api/v1", temperature=1,
                                 context_window=196_608, tool_support=True, vision_support=True,
                                 cost_per_million_input_tokens=0.295, cost_per_million_output_tokens=1.2, nitro_support=False, open_source=True),
    "olmo3.1-32b-instruct": ModelConfig(name="allenai/olmo-3.1-32b-instruct", base_url="https://openrouter.ai/api/v1", 
                                        temperature=1, context_window=65_536, tool_support=True, vision_support=False,
                                        cost_per_million_input_tokens=0.20, cost_per_million_output_tokens=0.60, nitro_support=False, open_source=True),
    "nemotron-3-nano-30b": ModelConfig(name="nvidia/nemotron-3-nano-30b-a3b", base_url="https://openrouter.ai/api/v1",
                                       temperature=1, context_window=262_144, tool_support=True, vision_support=False,
                                       cost_per_million_input_tokens=0.05, cost_per_million_output_tokens=0.20, nitro_support=False, open_source=True),
    "devstral2": ModelConfig(name="mistralai/devstral-2512", base_url="https://openrouter.ai/api/v1",
                             temperature=1, context_window=262_144, tool_support=True, vision_support=True,
                             cost_per_million_input_tokens=0.25, cost_per_million_output_tokens=0.75, nitro_support=False, open_source=True),
    "mercury2": ModelConfig(name="inception/mercury-2", base_url="https://openrouter.ai/api/v1", temperature=1, 
                            context_window=128_000, tool_support=True, vision_support=False,
                            cost_per_million_input_tokens=0.25, cost_per_million_output_tokens=0.75, nitro_support=False, open_source=True),

    # closed models
    "gpt-5.4": ModelConfig(name="openai/gpt-5.4", base_url="https://openrouter.ai/api/v1", temperature=1, 
                           context_window=1_050_000, tool_support=True, vision_support=True, nitro_support=True,
                           cost_per_million_input_tokens=2.5, cost_per_million_output_tokens=15, open_source=False),
    "codex-5.3": ModelConfig(name="openai/gpt-5.3-codex", base_url="https://openrouter.ai/api/v1", temperature=1, context_window=400_000, 
                             tool_support=True, vision_support=True, nitro_support=True,
                             cost_per_million_input_tokens=1.75, cost_per_million_output_tokens=14, open_source=False),
    "claude-sonnet-4.6": ModelConfig(name="anthropic/claude-sonnet-4.6", base_url="https://openrouter.ai/api/v1", 
                                     temperature=1, context_window=1_000_000, tool_support=True, vision_support=True,
                                     nitro_support=True,
                                     cost_per_million_input_tokens=3, cost_per_million_output_tokens=15, open_source=False),
    "claude-opus-4.6": ModelConfig(name="anthropic/claude-opus-4.6", base_url="https://openrouter.ai/api/v1", 
                                   temperature=1, context_window=1_000_000, tool_support=True, vision_support=True,
                                   nitro_support=True,
                                   cost_per_million_input_tokens=5, cost_per_million_output_tokens=25, open_source=False),

    "gemini-3.1-flash-lite": ModelConfig(name="google/gemini-3.1-flash-lite-preview", base_url="https://openrouter.ai/api/v1", 
                                         temperature=1, context_window=1_048_576, 
                                         tool_support=True, vision_support=True, nitro_support=True,
                                         cost_per_million_input_tokens=0.25, cost_per_million_output_tokens=1.5, open_source=False),
}

def list_default_model_names() -> list:
    """Return a list of all available default model option names."""
    return list(MODEL_OPTIONS.keys())

def get_model_config(model_name: str) -> ModelConfig:
    """Get ModelConfig for the given model name."""
    config = MODEL_OPTIONS.get(model_name)
    if not config:
        raise ValueError(f"No model found for '{model_name}'. Available: {', '.join(MODEL_OPTIONS.keys())}")
    return config


def list_open_source_model_names() -> list:
    """Return model keys for all open source models."""
    return [key for key, cfg in MODEL_OPTIONS.items() if cfg.open_source]


def list_closed_source_model_names() -> list:
    """Return model keys for all closed source models."""
    return [key for key, cfg in MODEL_OPTIONS.items() if not cfg.open_source]


def get_model_options_by_context_window() -> List[Dict[str, Any]]:
    """return model options as a list of dicts with model_key and context_window for sorting/filtering."""
    return [
        {"model_key": key, "context_window": cfg.context_window or 0}
        for key, cfg in MODEL_OPTIONS.items()
    ]


def get_model_options_by_input_token_cost() -> List[Dict[str, Any]]:
    """return model options as a list of dicts with model_key and cost_per_million_input_tokens for sorting/filtering."""
    return [
        {"model_key": key, "cost_per_million_input_tokens": cfg.cost_per_million_input_tokens}
        for key, cfg in MODEL_OPTIONS.items()
    ]


def get_model_options_by_output_token_cost() -> List[Dict[str, Any]]:
    """return model options as a list of dicts with model_key and cost_per_million_output_tokens for sorting/filtering."""
    return [
        {"model_key": key, "cost_per_million_output_tokens": cfg.cost_per_million_output_tokens}
        for key, cfg in MODEL_OPTIONS.items()
    ]


class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False
    exclude_patterns: List[str] = Field(default_factory=lambda: ["*KEY*", "*TOKEN*", "*SECRET*"])
    set_vars: dict[str, str] = Field(default_factory=dict)

class MCPServerConfig(BaseModel):
    enabled: bool = True
    startup_timeout_sec: float = 10.0

    # stdout transport
    command: str = Field(default="")
    args: List[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None

    # http/sse transport
    url: str | None = None

    @model_validator(mode="after")
    def validate_transport(self) -> 'MCPServerConfig':
        has_command = bool(self.command)
        has_url = bool(self.url)
        if not has_command and not has_url:
            raise ValueError("Either command or url must be provided")
        if has_command and has_url:
            raise ValueError("Only one of command or url must be provided")
        if has_command and not self.cwd:
            raise ValueError("cwd must be provided when command is provided")
        return self

class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    max_turns: int = 100
    shell_environment: ShellEnvironmentPolicy = Field(default_factory=ShellEnvironmentPolicy)
    max_tool_output_tokens: int = 50_000
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    _mcp_manager: Any | None = PrivateAttr(default=None)

    @property
    def api_key(self) -> str:
        return os.getenv('API_KEY', '')
    
    @property
    def base_url(self) -> str:
        return self.model.base_url
    
    @property
    def model_name(self) -> str:
        return self.model.name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    @property
    def temperature(self) -> None:
        return self.model.temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self.model.temperature = value

    def validate(self) -> List[str] | None:
        errors: List[str] = []
        if not self.api_key:
            errors.append("API key is required")

        if not self.cwd.exists():
            errors.append(f"Current working directory does not exist: {self.cwd}")
        
        if errors:
            return errors
        return None

    @property
    def mcp_manager(self) -> Any | None:
        return self._mcp_manager

    @mcp_manager.setter
    def mcp_manager(self, value: Any | None) -> None:
        self._mcp_manager = value