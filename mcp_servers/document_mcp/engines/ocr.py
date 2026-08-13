"""RapidOCR adapter preserving raw recognition evidence."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from ..models import TextRegion


class OcrEngine:
    def __init__(self, *, max_pixels: int = 50_000_000) -> None:
        self.max_pixels = max_pixels
        self._engine: RapidOCR | None = None
        self._lock = Lock()

    def _get_engine(self) -> RapidOCR:
        with self._lock:
            if self._engine is None:
                self._engine = RapidOCR()
            return self._engine

    def recognize_path(self, path: Path) -> dict[str, Any]:
        with Image.open(path) as image:
            return self.recognize_image(image.convert("RGB"))

    def recognize_image(self, image: Image.Image) -> dict[str, Any]:
        width, height = image.size
        if width * height > self.max_pixels:
            raise ValueError(
                f"image has {width * height} pixels; limit is {self.max_pixels}"
            )
        result, elapsed = self._get_engine()(np.asarray(image.convert("RGB")))
        raw = result or []
        ordered = sorted(
            raw,
            key=lambda item: (
                min(float(point[1]) for point in item[0]),
                min(float(point[0]) for point in item[0]),
            ),
        )
        regions = [
            TextRegion(
                text=str(text),
                source="ocr",
                order=index,
                bbox=[[round(float(x), 2), round(float(y), 2)] for x, y in box],
                confidence=round(float(confidence), 6),
            )
            for index, (box, text, confidence) in enumerate(ordered, 1)
        ]
        timings = [round(float(value), 6) for value in elapsed] if elapsed else []
        return {
            "width": width,
            "height": height,
            "engine": "rapidocr_onnxruntime",
            "timings_seconds": timings,
            "regions": regions,
        }
