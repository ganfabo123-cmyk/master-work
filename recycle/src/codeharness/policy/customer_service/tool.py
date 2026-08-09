"""Tools owned by CustomerServiceAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Callable

from pydantic import Field

from .base import BaseAgentTools
from .utils import search_markdown


_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


class CustomerServiceTools(BaseAgentTools):
    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        """Return the customer-service tools bound to this Agent instance."""
        return (self.search_customer_knowledge,)

    def search_customer_knowledge(
        self,
        query: Annotated[str, Field(description="用于检索客服知识库的关键词或完整问题。")],
    ) -> str:
        """检索本地客服知识库并返回最相关的 Markdown 原文；未命中时明确说明。"""
        return search_markdown(query, _DATA_ROOT, no_match="No matching customer-service material was found. Do not invent policy details.")
