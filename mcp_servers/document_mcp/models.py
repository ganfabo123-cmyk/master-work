"""Serializable document intermediate representation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class TextRegion:
    text: str
    source: Literal["native", "ocr"]
    order: int
    bbox: list[list[float]] | None = None
    confidence: float | None = None


@dataclass(slots=True)
class PageResult:
    page: int
    kind: Literal["native", "scanned", "mixed", "empty"]
    width: float
    height: float
    regions: list[TextRegion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(region.text for region in self.regions if region.text)


@dataclass(slots=True)
class DocumentResult:
    document_id: str
    source_path: str
    page_count: int
    pages: list[PageResult]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
