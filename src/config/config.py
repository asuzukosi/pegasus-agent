from pydantic import BaseModel, Field, model_validator
from typing import List, Any, Dict
from pathlib import Path
import os

class ModelConfig(BaseModel):
    name: str = Field(default="mistral-7b-instruct-v0.2")
    base_url: str = Field(default="https://api.mistral.ai/v1")
    temperature: float = Field(default=1, ge=0, le=2.0)
    context_window: int | None = 256_000


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
    shell_environment: ShellEnvironmentPolicy = Field(default_factory=ShellEnvironmentPolicy)
    max_turns: int = 100
    max_tool_output_tokens: int = 50_000
    developer_instructions: str | None = None
    user_instructions: str | None = None
    debug: bool = False
    allowed_tools: list[str] | None = None
    timeout: int | None = None
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @property
    def api_key(self) -> str:
        return os.getenv('API_KEY', '')
    
    @property
    def base_url(self) -> str:
        return os.getenv('BASE_URL')
    
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