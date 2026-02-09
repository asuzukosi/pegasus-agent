from pydantic import BaseModel, Field
from typing import List
from pathlib import Path
import os

class ModelConfig(BaseModel):
    name: str = Field(default="mistral-7b-instruct-v0.2")
    base_url: str = Field(default="https://api.mistral.ai/v1")
    temperature: float = Field(default=1, ge=0, le=2.0)
    context_window: int | None = 256_000



class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    max_turns: int = 100
    max_tool_output_tokens: int = 50_000
    developer_instructions: str | None = None
    user_instructions: str | None = None
    debug: bool = False

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