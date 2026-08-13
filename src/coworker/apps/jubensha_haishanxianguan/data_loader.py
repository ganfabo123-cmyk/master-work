from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


ROLE_FILES = {
    "pan": "01_潘仕成剧本.md",
    "ivan": "02_伊凡剧本.md",
    "li": "03_李夫人剧本.md",
    "maid": "04_侍女剧本.md",
    "butler": "05_管家剧本.md",
    "he": "06_何绍基剧本.md",
}

ROLE_NAMES = {
    "pan": "潘仕成",
    "ivan": "伊凡",
    "li": "李夫人",
    "maid": "侍女",
    "butler": "管家",
    "he": "何绍基",
}

PERSON_CLUE_FILE = "08_12个人物线索.md"
SCENE_CLUE_FILE = "09_14个场景线索.md"
TRUTH_FILE = "10_复盘剧本.md"
ROLE_CARD_FILE = "07_6个角色人物卡.md"


@dataclass(frozen=True)
class MaterialRecord:
    material_id: str
    source: str
    content: str


class HaishanMaterialLoader:
    """Loads App-owned references without copying the large source bodies into State."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("data/jubensha")

    def _read(self, filename: str) -> str:
        return (self.root / filename).read_text(encoding="utf-8")

    def role_script(self, role_id: str) -> MaterialRecord:
        filename = ROLE_FILES[role_id]
        return MaterialRecord(f"script:{role_id}", filename, self._read(filename))

    def public_role_cards(self) -> MaterialRecord:
        return MaterialRecord("public-role-cards", ROLE_CARD_FILE, self._read(ROLE_CARD_FILE))

    @staticmethod
    def _heading_blocks(text: str, heading_pattern: str) -> list[str]:
        headings = list(re.finditer(heading_pattern, text, re.MULTILINE))
        blocks: list[str] = []
        for index, heading in enumerate(headings):
            next_heading = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            next_page = text.find("\n## 第 ", heading.end())
            stop = min(next_heading, next_page) if next_page >= 0 else next_heading
            blocks.append(text[heading.start() : stop].strip())
        return blocks

    def clues(self, kind: str) -> dict[str, MaterialRecord]:
        if kind == "person":
            filename, expected = PERSON_CLUE_FILE, 12
            pattern = r"^.*(?:綫索|線索|线索|索)：.*$"
        elif kind == "scene":
            filename, expected = SCENE_CLUE_FILE, 14
            pattern = r"^.*掉落：.*$"
        else:
            raise ValueError(f"unknown clue kind: {kind}")
        blocks = self._heading_blocks(self._read(filename), pattern)
        if len(blocks) != expected:
            raise ValueError(
                f"{filename} produced {len(blocks)} clues; expected {expected}; OCR layout changed"
            )
        return {
            f"{kind}-{index:02d}": MaterialRecord(
                f"{kind}-{index:02d}", filename, content
            )
            for index, content in enumerate(blocks, start=1)
        }

    def truth(self) -> MaterialRecord:
        text = self._read(TRUTH_FILE)
        match = re.search(r"(?ms)^## 第 4 页\s*(.*?)(?=^## 第 7 页|\Z)", text)
        if not match:
            raise ValueError("truth pages are missing")
        return MaterialRecord("truth", TRUTH_FILE, match.group(1).strip())
