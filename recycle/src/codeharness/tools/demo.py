"""Tools owned by the deterministic demo Agent."""

from __future__ import annotations

from typing import Annotated, Any, Callable

from pydantic import Field

from .base import BaseAgentTools


class DemoTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        """Return the deterministic demo tool bound to this Agent instance."""
        return (self.inspect_task,)

    def inspect_task(
        self,
        task: Annotated[str, Field(description="需要确认已接收的任务原文。")],
    ) -> str:
        """回显任务原文，用于演示确定性的只读工具调用。"""
        return f"Task received: {task}"
