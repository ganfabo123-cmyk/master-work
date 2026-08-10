"""Load and validate one structured murder-mystery case package."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_CASE_ROOT = Path(__file__).resolve().parents[4] / "data" / "script_murder" / "shadow_of_the_elysee"


@dataclass(frozen=True, slots=True)
class Character:
    character_id: str
    name: str
    private_briefing: str
    goals: tuple[str, ...]
    relationships: dict[str, str]


@dataclass(frozen=True, slots=True)
class CaseDocument:
    document_id: str
    round_no: int
    recipients: tuple[str, ...] | str
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class ScriptMurderCase:
    case_id: str
    title: str
    public_briefing: str
    public_situation: tuple[str, ...]
    public_cast: dict[str, str]
    characters: dict[str, Character]
    documents: dict[str, CaseDocument]
    deliveries: dict[int, tuple[str, ...]]
    truths: tuple[dict[str, Any], ...]
    character_order: tuple[str, ...]

    def documents_for(self, round_no: int, character_id: str) -> tuple[CaseDocument, ...]:
        return tuple(
            self.documents[document_id]
            for document_id in self.deliveries.get(round_no, ())
            if self.documents[document_id].recipients == "all"
            or character_id in self.documents[document_id].recipients
        )


def load_case(root: Path = DEFAULT_CASE_ROOT) -> ScriptMurderCase:
    manifest = _read_json(root / "manifest.json")
    setting = _read_json(root / manifest["files"]["setting"])
    truth_data = _read_json(root / manifest["files"]["moderator_truth"])
    character_order = tuple(str(item) for item in manifest["character_ids"])
    characters: dict[str, Character] = {}
    for character_id in character_order:
        raw = _read_json(root / "characters" / f"{character_id}.json")
        if raw.get("character_id") != character_id:
            raise ValueError(f"Character identity mismatch: {character_id}")
        characters[character_id] = Character(
            character_id=character_id,
            name=str(raw["name"]),
            private_briefing=str(raw["private_briefing"]),
            goals=tuple(str(item) for item in raw["goals"]),
            relationships={str(key): str(value) for key, value in raw["relationships"].items()},
        )
    raw_documents = _read_json(root / manifest["files"]["documents"])["documents"]
    documents: dict[str, CaseDocument] = {}
    for raw in raw_documents:
        document_id = str(raw["document_id"])
        if document_id in documents:
            raise ValueError(f"Duplicate document: {document_id}")
        recipients = raw["recipients"]
        parsed_recipients = "all" if recipients == "all" else tuple(str(item) for item in recipients)
        documents[document_id] = CaseDocument(
            document_id=document_id,
            round_no=int(raw["round"]),
            recipients=parsed_recipients,
            title=str(raw["title"]),
            content=str(raw["content"]),
        )
    deliveries: dict[int, tuple[str, ...]] = {}
    for relative_path in manifest["files"]["reveals"]:
        raw = _read_json(root / relative_path)
        deliveries[int(raw["round"])] = tuple(str(item["document_id"]) for item in raw["deliveries"])
    case = ScriptMurderCase(
        case_id=str(manifest["case_id"]),
        title=str(manifest["title"]),
        public_briefing=str(setting["public_briefing"]),
        public_situation=tuple(str(item) for item in setting["public_situation"]),
        public_cast={str(key): str(value) for key, value in setting["public_cast"].items()},
        characters=characters,
        documents=documents,
        deliveries=deliveries,
        truths=tuple(dict(item) for item in truth_data["truths"]),
        character_order=character_order,
    )
    _validate(case, expected_player_count=int(manifest["player_count"]))
    return case


def _validate(case: ScriptMurderCase, *, expected_player_count: int) -> None:
    character_ids = set(case.characters)
    if len(case.characters) != expected_player_count or len(case.character_order) != expected_player_count:
        raise ValueError("Case player count does not match its character data")
    if set(case.character_order) != character_ids or set(case.public_cast) != character_ids:
        raise ValueError("Character indexes are inconsistent")
    for character in case.characters.values():
        missing = set(character.relationships) - character_ids
        if missing:
            raise ValueError(f"Unknown relationship targets for {character.character_id}: {sorted(missing)}")
    for round_no, document_ids in case.deliveries.items():
        for document_id in document_ids:
            document = case.documents.get(document_id)
            if document is None or document.round_no != round_no:
                raise ValueError(f"Invalid round document reference: {round_no}/{document_id}")
            if document.recipients != "all" and not set(document.recipients) <= character_ids:
                raise ValueError(f"Unknown document recipient: {document_id}")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
