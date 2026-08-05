from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints

from pydantic import TypeAdapter, ValidationError


class ToolError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CompiledTool:
    name: str
    description: str
    fn: Callable[..., Any]
    signature: inspect.Signature
    hints: dict[str, Any]

    def schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, parameter in self.signature.parameters.items():
            annotation = self.hints.get(name, Any)
            properties[name] = TypeAdapter(annotation).json_schema()
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
        return {"name": self.name, "description": self.description, "parameters": {"type": "object", "properties": properties, "required": required}}

    def invoke(self, arguments: dict[str, Any]) -> Any:
        try:
            bound = self.signature.bind(**arguments)
            for name, value in bound.arguments.items():
                bound.arguments[name] = TypeAdapter(self.hints.get(name, Any)).validate_python(value, strict=True)
            result = self.fn(*bound.args, **bound.kwargs)
            return TypeAdapter(self.hints.get("return", Any)).validate_python(result, strict=True)
        except (TypeError, ValidationError) as error:
            raise ToolError(f"{self.name}: invalid call: {error}") from error


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, CompiledTool] = {}

    def register(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        if fn.__name__ in self._tools:
            raise ValueError(f"duplicate tool: {fn.__name__}")
        self._tools[fn.__name__] = CompiledTool(fn.__name__, inspect.getdoc(fn) or "", fn, inspect.signature(fn), get_type_hints(fn, include_extras=True))
        return fn

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name}")
        return self._tools[name].invoke(arguments)


registry = ToolRegistry()
tool = registry.register


@tool
def inspect_task(task: str) -> str:
    """Return a deterministic observation about the current task."""
    return f"Task received: {task}"
