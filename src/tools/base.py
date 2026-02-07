from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Type
from pydantic import BaseModel, ValidationError
from src.tools.data import ToolInvocation, ToolResult, ToolType, ToolConfirmation

class Tool(ABC):
    name: str = "base_tool"
    description: str = "A base tool class"
    type: ToolType = ToolType.WRITE

    @property
    def schema(self) -> dict[str, Any] | Type[BaseModel]:
        raise NotImplementedError("Every tool must implement the schema method")

    @abstractmethod
    def execute(self, invocation: ToolInvocation, *args, **kwargs) -> ToolResult:
        raise NotImplementedError("Every tool must implement the execute method")

    def validate_params(self, params: dict[str, Any]) -> list[str] | None:
        schema = self.schema
        missing_params = []
        if isinstance(schema, dict):
            for key in schema.keys():
                if key not in params:
                    missing_params.append(f"Missing required parameter: {key}")
            return missing_params
        elif isinstance(schema, Type[BaseModel]):
            try:
                schema.model_validate(params).model_dump()
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error.get("loc", []))
                    msg = error.get("msg", "Validation error")
                    errors.append(f"Parameter {field}: {msg}")
                return errors
            except Exception as e:
                return [str(e)]
        return None
    
    def is_mutating(self, params: dict[str, Any]) -> bool:
        return self.type in [ToolType.WRITE, ToolType.BASH, ToolType.NETWORK, ToolType.MEMORY]
    
    async def get_confirmation(self, invocation: ToolInvocation) -> ToolConfirmation | None:
        if not self.is_mutating(invocation.params):
            return None
        
        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute {self.name}"
        )
    
    def to_openai_schema(self) -> dict[str, Any]:
        schema = self.schema

        if isinstance(schema, Type[BaseModel]):
            json_schema = schema.model_json_schema()
            result = {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
                    "required": json_schema.get("required", []),
                    "additionalProperties": False
                }
            }
            return result
        
        elif isinstance(schema, dict):
            result =  {
                "name": self.name,
                "description": self.description
            }
            if "parameters" in schema:
                result["parameters"] = schema["parameters"]
            else:
                result["parameters"] = schema
            return result
        
        raise ValueError(f"Invalid schema type for tool {self.name}: {type(schema)}")
