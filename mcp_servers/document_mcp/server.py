"""Real MCP server entrypoint for document parsing tools."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from threading import Lock
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .engines import OcrEngine, PdfEngine
from .models import DocumentResult
from .security import resolve_readable_file

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
_OCR = OcrEngine()
_PDF = PdfEngine(_OCR)
_DOCUMENTS: dict[str, DocumentResult] = {}
_CACHE_LOCK = Lock()


def create_server() -> FastMCP:
    server = FastMCP(
        "document-parser",
        instructions=(
            "Use parse_pdf first. It parses native PDF text directly and applies OCR to scanned "
            "pages. Then use get_pdf_content with selected pages so large documents do not flood "
            "the model context. OCR text is raw evidence and may contain recognition errors."
        ),
        log_level="WARNING",
    )

    @server.tool(structured_output=True)
    def ocr_image(
        image_path: Annotated[str, Field(description="Absolute or allowed-root-relative image path.")],
    ) -> dict[str, Any]:
        """Recognize raw text in an image with coordinates and confidence scores."""
        path = resolve_readable_file(image_path, suffixes=IMAGE_SUFFIXES)
        result = _OCR.recognize_path(path)
        return {
            **result,
            "source_path": str(path),
            "regions": [asdict(region) for region in result["regions"]],
        }

    @server.tool(structured_output=True)
    def parse_pdf(
        pdf_path: Annotated[str, Field(description="Absolute or allowed-root-relative PDF path.")],
        ocr_mode: Annotated[
            Literal["auto", "always", "never"],
            Field(description="auto uses OCR only when a page has no native text layer."),
        ] = "auto",
        pages: Annotated[
            list[int] | None,
            Field(description="Optional one-based page numbers; omitted means all pages."),
        ] = None,
    ) -> dict[str, Any]:
        """Parse and cache a PDF, using native text where available and OCR for scanned pages."""
        path = resolve_readable_file(pdf_path, suffixes={".pdf"})
        document = _PDF.parse(path, ocr_mode=ocr_mode, pages=pages)
        with _CACHE_LOCK:
            _DOCUMENTS[document.document_id] = document
        return {
            "document_id": document.document_id,
            "source_path": document.source_path,
            "page_count": document.page_count,
            "parsed_pages": [
                {
                    "page": page.page,
                    "kind": page.kind,
                    "region_count": len(page.regions),
                    "character_count": len(page.text),
                    "preview": page.text[:500],
                    "warnings": page.warnings,
                }
                for page in document.pages
            ],
            "warnings": document.warnings,
        }

    @server.tool(structured_output=True)
    def get_pdf_content(
        document_id: Annotated[str, Field(description="document_id returned by parse_pdf.")],
        pages: Annotated[
            list[int] | None,
            Field(description="Optional one-based pages to return; omitted returns parsed pages."),
        ] = None,
        max_chars: Annotated[
            int,
            Field(ge=1, le=100_000, description="Maximum total text characters returned."),
        ] = 20_000,
        include_coordinates: Annotated[
            bool,
            Field(description="Include OCR bounding boxes and confidence scores."),
        ] = False,
    ) -> dict[str, Any]:
        """Read selected pages from a document previously parsed by parse_pdf."""
        with _CACHE_LOCK:
            document = _DOCUMENTS.get(document_id)
        if document is None:
            raise ValueError("unknown document_id; call parse_pdf in this MCP session first")
        requested = set(pages) if pages is not None else None
        available = {page.page for page in document.pages}
        if requested is not None and not requested <= available:
            raise ValueError(f"requested pages were not parsed: {sorted(requested - available)}")

        remaining = max_chars
        output_pages: list[dict] = []
        truncated = False
        for page in document.pages:
            if requested is not None and page.page not in requested:
                continue
            page_regions: list[dict] = []
            for region in page.regions:
                if remaining <= 0:
                    truncated = True
                    break
                text = region.text[:remaining]
                if len(text) < len(region.text):
                    truncated = True
                item = {
                    "text": text,
                    "source": region.source,
                    "order": region.order,
                }
                if include_coordinates:
                    item.update({"bbox": region.bbox, "confidence": region.confidence})
                page_regions.append(item)
                remaining -= len(text)
            output_pages.append({
                "page": page.page,
                "kind": page.kind,
                "regions": page_regions,
                "warnings": page.warnings,
            })
            if remaining <= 0:
                break
        return {
            "document_id": document.document_id,
            "pages": output_pages,
            "truncated": truncated,
            "max_chars": max_chars,
        }

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Document parsing MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    args = parser.parse_args()
    create_server().run(transport=args.transport)


if __name__ == "__main__":
    main()
