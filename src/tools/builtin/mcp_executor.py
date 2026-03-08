from __future__ import annotations

import asyncio
import ast
import json
import re
import textwrap
from types import SimpleNamespace
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.config.config import Config
from src.mcp.client import MCPClient, MCPToolInfo
from src.tools.base import Tool
from src.tools.data import ToolInvocation, ToolResult, ToolType


class MCPExecutorAction(str, Enum):
    LIST = "list"
    EXECUTE = "execute"

    def __str__(self) -> str:
        return self.value


class MCPExecutorParams(BaseModel):
    action: str = Field(
        ...,
        description="The action to perform on the mcp executor. Actions are: list, execute",
    )
    code: str | None = Field(
        None,
        description="Python code to execute when action is 'execute'. Set a variable named result to control the final returned value.",
    )


@dataclass
class MCPFunctionBinding:
    python_name: str
    tool_name: str
    server_name: str
    tool_info: MCPToolInfo


class MCPExecutorTool(Tool):
    name: str = "mcp_executor"
    description: str = (
        "Execute mcp capabilities through a compact python interface. "
        "Use action='list' to inspect available mcp functions and action='execute' "
        "to run python that awaits those functions and sets a result variable."
    )
    type: ToolType = ToolType.MCP
    schema: MCPExecutorParams = MCPExecutorParams

    def __init__(self, config: Config) -> None:
        self._config = config
        self._clients: dict[str, MCPClient] = {}
        self._bindings: dict[str, MCPFunctionBinding] = {}
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            self._clients = {}
            self._bindings = {}
            mcp_manager = self._config.mcp_manager
            if mcp_manager is None or not mcp_manager.initialized:
                self._initialized = True
                return
            for server_name, client in mcp_manager.connected_clients.items():
                self._clients[server_name] = client
                for tool_info in client.tools:
                    python_name = self._build_python_name(server_name, tool_info.name)
                    self._bindings[python_name] = MCPFunctionBinding(
                        python_name=python_name,
                        tool_name=tool_info.name,
                        server_name=server_name,
                        tool_info=tool_info,
                    )
            self._initialized = True

    def _build_python_name(self, server_name: str, tool_name: str) -> str:
        candidate = f"{server_name}__{tool_name}"
        candidate = re.sub(r"[^0-9a-zA-Z_]", "_", candidate)
        candidate = re.sub(r"_+", "_", candidate).strip("_")
        if not candidate:
            candidate = "mcp_function"
        if candidate[0].isdigit():
            candidate = f"mcp_{candidate}"
        return candidate.lower()

    def _format_schema(self, schema: dict[str, Any]) -> str:
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
        if not properties:
            return "{}"
        lines = ["{"]
        for key, value in properties.items():
            type_name = value.get("type", "any") if isinstance(value, dict) else "any"
            suffix = " required" if key in required else ""
            lines.append(f'  "{key}": "{type_name}{suffix}"')
        lines.append("}")
        return "\n".join(lines)

    def _render_function_list(self) -> str:
        if not self._bindings:
            return "no connected mcp servers are available."
        lines = [
            "available mcp python functions:",
            "",
            "call them with await inside execute mode and set a result variable.",
            "a limited asyncio helper is already available, so use asyncio.gather(...) without importing asyncio.",
            "",
        ]
        for binding in sorted(self._bindings.values(), key=lambda item: item.python_name):
            description = binding.tool_info.description or "no description provided"
            lines.append(f"- python name: {binding.python_name}")
            lines.append(f"  server: {binding.server_name}")
            lines.append(f"  mcp tool: {binding.tool_name}")
            lines.append(f"  description: {description}")
            lines.append("  arguments:")
            lines.append(textwrap.indent(self._format_schema(binding.tool_info.input_schema), "    "))
            lines.append("")
        return "\n".join(lines).rstrip()

    def _validate_script(self, code: str) -> list[str]:
        blocked_calls = {
            "open",
            "exec",
            "eval",
            "compile",
            "input",
            "__import__",
            "globals",
            "locals",
            "vars",
            "getattr",
            "setattr",
            "delattr",
            "breakpoint",
        }
        blocked_nodes = (
            ast.Import,
            ast.ImportFrom,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.With,
            ast.AsyncWith,
            ast.Try,
            ast.Raise,
            ast.Delete,
            ast.Global,
            ast.Nonlocal,
            ast.Lambda,
        )
        errors: list[str] = []
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as e:
            return [f"syntax error: {e}"]

        for node in ast.walk(tree):
            if isinstance(node, blocked_nodes):
                errors.append(f"unsupported syntax: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("_"):
                errors.append(f"unsafe name access: {node.id}")
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                errors.append(f"unsafe attribute access: {node.attr}")
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in blocked_calls:
                    errors.append(f"blocked call: {func.id}")
        return sorted(set(errors))

    def _safe_builtins(self, print_buffer: list[str]) -> dict[str, Any]:
        def sandbox_print(*args, **kwargs) -> None:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            print_buffer.append(sep.join(str(arg) for arg in args) + end.rstrip("\n"))

        return {
            "print": sandbox_print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
            "tuple": tuple,
            "set": set,
            "min": min,
            "max": max,
            "sum": sum,
            "enumerate": enumerate,
            "range": range,
            "zip": zip,
            "sorted": sorted,
            "any": any,
            "all": all,
        }

    def _coerce_binding_params(
        self,
        binding: MCPFunctionBinding,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        if not args:
            return kwargs
        schema = binding.tool_info.input_schema if isinstance(binding.tool_info.input_schema, dict) else {}
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        property_names = list(properties.keys())
        if len(args) > len(property_names):
            raise ValueError(
                f"{binding.python_name} accepts at most {len(property_names)} positional arguments, got {len(args)}"
            )
        params = dict(kwargs)
        for name, value in zip(property_names, args, strict=False):
            if name in params:
                raise ValueError(f"{binding.python_name} received multiple values for argument '{name}'")
            params[name] = value
        return params

    async def _run_binding(self, binding: MCPFunctionBinding, *args: Any, **kwargs: Any) -> dict[str, Any]:
        params = self._coerce_binding_params(binding, args, kwargs)
        client = self._clients[binding.server_name]
        result = await client.call_tool(binding.tool_name, params)
        if result["is_error"]:
            raise RuntimeError(result["output"] or f"mcp tool {binding.tool_name} failed")
        return {
            "server": binding.server_name,
            "tool": binding.tool_name,
            "output": result["output"],
            "raw_content": result["raw_content"],
        }

    async def _execute_script(self, code: str) -> ToolResult:
        validation_errors = self._validate_script(code)
        if validation_errors:
            return ToolResult.error_result(
                "unsafe or unsupported python provided for mcp execution",
                output="\n".join(validation_errors),
            )

        print_buffer: list[str] = []
        namespace: dict[str, Any] = {
            "__builtins__": self._safe_builtins(print_buffer),
            "asyncio": SimpleNamespace(gather=asyncio.gather, sleep=asyncio.sleep),
            "json": json,
        }
        for python_name, binding in self._bindings.items():
            async def _wrapper(*args, _binding: MCPFunctionBinding = binding, **kwargs):
                return await self._run_binding(_binding, *args, **kwargs)
            namespace[python_name] = _wrapper

        function_source = (
            "async def __mcp_user_code__():\n"
            + textwrap.indent(code, "    ")
            + "\n    try:\n"
            + "        return result\n"
            + "    except NameError:\n"
            + "        return None\n"
        )
        exec(function_source, namespace, namespace)
        result_value = await namespace["__mcp_user_code__"]()

        sections: list[str] = []
        if print_buffer:
            sections.append("printed output:\n" + "\n".join(line for line in print_buffer if line))
        if result_value is not None:
            try:
                rendered_result = json.dumps(result_value, indent=2, default=str)
            except TypeError:
                rendered_result = str(result_value)
            sections.append("result:\n" + rendered_result)
        if not sections:
            sections.append("script completed without printed output or result.")

        return ToolResult.success_result(
            output="\n\n".join(sections),
            metadata={
                "action": "execute",
                "available_functions": sorted(self._bindings.keys()),
            },
        )

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = MCPExecutorParams(**invocation.params)
        await self._ensure_initialized()

        if params.action == MCPExecutorAction.LIST:
            return ToolResult.success_result(
                output=self._render_function_list(),
                metadata={"action": "list", "function_count": len(self._bindings)},
            )
        if params.action == MCPExecutorAction.EXECUTE:
            if not params.code or not params.code.strip():
                return ToolResult.error_result("code is required when action is 'execute'")
            if not self._bindings:
                return ToolResult.error_result("no mcp functions are available because no mcp servers are connected")
            return await self._execute_script(params.code)
        return ToolResult.error_result(
            f"invalid action: {params.action}. valid actions are: {', '.join(action.value for action in MCPExecutorAction)}"
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"error executing mcp executor with error: {e}")

    async def close(self) -> None:
        self._clients = {}
        self._bindings = {}
        self._initialized = False
