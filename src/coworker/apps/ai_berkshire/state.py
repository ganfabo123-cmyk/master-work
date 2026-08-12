"""Investment-research State and App-owned research artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...core.base_state import State


class InvestmentPhase(StrEnum):
    PARALLEL_RESEARCH = "parallel_research"
    SYNTHESIS = "synthesis"
    FINISHED = "finished"


class InvestmentRole(StrEnum):
    BUSINESS = "business"
    FINANCIAL = "financial"
    INDUSTRY = "industry"
    RISK = "risk"
    LEAD = "lead"


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    artifact_id: str
    author: str
    role: InvestmentRole
    title: str
    thesis: str
    content: str
    score: int
    confidence: int
    citations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvestmentMemo:
    artifact_id: str
    recommendation: str
    summary: str
    content: str
    score: int
    confidence: int
    source_artifact_ids: tuple[str, ...]


@dataclass
class InvestmentState(State):
    company_name: str = ""
    ticker: str = ""
    data_cutoff: str = ""
    information_grade: str = "B"
    research_context: str = ""
    phase: InvestmentPhase = InvestmentPhase.PARALLEL_RESEARCH
    artifacts: dict[str, ResearchArtifact] = field(default_factory=dict)
    final_memo: InvestmentMemo | None = None
    consumed_action_ids: set[str] = field(default_factory=set)

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> "InvestmentState":
        return cls(task_id=task_id, session_id=session_id)

    @property
    def is_terminal(self) -> bool:
        return self.phase is InvestmentPhase.FINISHED

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "company_name": self.company_name,
            "ticker": self.ticker,
            "data_cutoff": self.data_cutoff,
            "information_grade": self.information_grade,
            "research_context": self.research_context,
            "phase": self.phase.value,
            "artifacts": {
                key: {
                    "artifact_id": value.artifact_id,
                    "author": value.author,
                    "role": value.role.value,
                    "title": value.title,
                    "thesis": value.thesis,
                    "content": value.content,
                    "score": value.score,
                    "confidence": value.confidence,
                    "citations": list(value.citations),
                }
                for key, value in self.artifacts.items()
            },
            "final_memo": None if self.final_memo is None else {
                "artifact_id": self.final_memo.artifact_id,
                "recommendation": self.final_memo.recommendation,
                "summary": self.final_memo.summary,
                "content": self.final_memo.content,
                "score": self.final_memo.score,
                "confidence": self.final_memo.confidence,
                "source_artifact_ids": list(self.final_memo.source_artifact_ids),
            },
            "consumed_action_ids": sorted(self.consumed_action_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "InvestmentState":
        raw_artifacts = dict(data.get("artifacts") or {})
        raw_memo = data.get("final_memo")
        return cls(
            task_id=str(data["task_id"]),
            session_id=str(data["session_id"]),
            company_name=str(data.get("company_name", "")),
            ticker=str(data.get("ticker", "")),
            data_cutoff=str(data.get("data_cutoff", "")),
            information_grade=str(data.get("information_grade", "B")),
            research_context=str(data.get("research_context", "")),
            phase=InvestmentPhase(str(data.get("phase", InvestmentPhase.PARALLEL_RESEARCH.value))),
            artifacts={
                str(key): ResearchArtifact(
                    artifact_id=str(value["artifact_id"]),
                    author=str(value["author"]),
                    role=InvestmentRole(str(value["role"])),
                    title=str(value["title"]),
                    thesis=str(value["thesis"]),
                    content=str(value["content"]),
                    score=int(value["score"]),
                    confidence=int(value["confidence"]),
                    citations=tuple(str(item) for item in value.get("citations", [])),
                )
                for key, value in raw_artifacts.items()
            },
            final_memo=None if not isinstance(raw_memo, dict) else InvestmentMemo(
                artifact_id=str(raw_memo["artifact_id"]),
                recommendation=str(raw_memo["recommendation"]),
                summary=str(raw_memo["summary"]),
                content=str(raw_memo["content"]),
                score=int(raw_memo["score"]),
                confidence=int(raw_memo["confidence"]),
                source_artifact_ids=tuple(str(item) for item in raw_memo["source_artifact_ids"]),
            ),
            consumed_action_ids={str(item) for item in data.get("consumed_action_ids", [])},
        )
