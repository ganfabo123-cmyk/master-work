"""Tools owned by ReleaseIncidentAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Callable

from pydantic import Field

from .base import BaseAgentTools
from .utils import search_markdown


_RUNBOOK_ROOT = Path(__file__).resolve().parents[3] / "data" / "release_incident"


class ReleaseIncidentTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        """Return the release-incident tools bound to this Agent instance."""
        return (self.search_release_runbooks,)

    def search_release_runbooks(
        self,
        query: Annotated[str, Field(description="用于检索生产发布、回滚或事件升级 Runbook 的关键词或问题。")],
    ) -> str:
        """检索本地发布故障 Runbook 并返回相关 Markdown 原文；未命中时明确说明。"""
        return search_markdown(query, _RUNBOOK_ROOT, no_match="No matching release runbook was found. Do not invent an operational procedure.")
