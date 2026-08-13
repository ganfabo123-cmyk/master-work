"""Hybrid native-text and OCR PDF parser."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

from ..models import DocumentResult, PageResult, TextRegion
from .ocr import OcrEngine

OcrMode = Literal["auto", "always", "never"]


class PdfEngine:
    def __init__(self, ocr: OcrEngine, *, max_pages: int = 500) -> None:
        self.ocr = ocr
        self.max_pages = max_pages

    def parse(
        self,
        path: Path,
        *,
        ocr_mode: OcrMode = "auto",
        pages: list[int] | None = None,
    ) -> DocumentResult:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("encrypted PDFs are not supported in this stage")
        if len(reader.pages) > self.max_pages:
            raise ValueError(f"PDF has {len(reader.pages)} pages; limit is {self.max_pages}")
        selected = self._selected_pages(len(reader.pages), pages)
        parsed_pages: list[PageResult] = []
        warnings: list[str] = []
        for page_number in selected:
            page = reader.pages[page_number - 1]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            native_text = (page.extract_text() or "").strip()
            regions: list[TextRegion] = []
            if native_text and ocr_mode != "always":
                regions.append(TextRegion(native_text, "native", 1))

            page_images = list(page.images)
            should_ocr = ocr_mode == "always" or (
                ocr_mode == "auto" and (not native_text or bool(page_images))
            )
            page_warnings: list[str] = []
            if should_ocr:
                if not page_images:
                    page_warnings.append("OCR requested but the page has no extractable images")
                for image_index, page_image in enumerate(page_images, 1):
                    try:
                        ocr_result = self.ocr.recognize_image(page_image.image.convert("RGB"))
                        offset = len(regions)
                        for region in ocr_result["regions"]:
                            region.order += offset
                            regions.append(region)
                    except Exception as error:
                        message = f"image {image_index} OCR failed: {error}"
                        page_warnings.append(message)
                        warnings.append(f"page {page_number}: {message}")

            sources = {region.source for region in regions}
            if sources == {"native"}:
                kind = "native"
            elif sources == {"ocr"}:
                kind = "scanned"
            elif len(sources) > 1:
                kind = "mixed"
            else:
                kind = "empty"
            parsed_pages.append(PageResult(
                page=page_number,
                kind=kind,
                width=width,
                height=height,
                regions=regions,
                warnings=page_warnings,
            ))

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = {
            str(key).lstrip("/"): str(value)
            for key, value in (reader.metadata or {}).items()
        }
        return DocumentResult(
            document_id=f"sha256:{digest}",
            source_path=str(path),
            page_count=len(reader.pages),
            pages=parsed_pages,
            metadata=metadata,
            warnings=warnings,
        )

    @staticmethod
    def _selected_pages(page_count: int, pages: list[int] | None) -> list[int]:
        if pages is None:
            return list(range(1, page_count + 1))
        selected = list(dict.fromkeys(pages))
        invalid = [page for page in selected if page < 1 or page > page_count]
        if invalid:
            raise ValueError(f"page numbers out of range 1..{page_count}: {invalid}")
        return selected
