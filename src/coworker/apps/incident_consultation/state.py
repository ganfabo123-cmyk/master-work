"""State owned by the incident-consultation Environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...core.base_state import State
from .case_loader import Evidence, IncidentCase


class ConsultationPhase(StrEnum):
    INDEPENDENT_ANALYSIS = "independent_analysis"
    FINAL_DIAGNOSIS = "final_diagnosis"
    FINISHED = "finished"


class ExpertRole(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    LEAD = "lead"


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    expert: str
    role: ExpertRole
    component: str
    summary: str
    evidence_ids: tuple[str, ...]
    confidence: int


@dataclass(frozen=True, slots=True)
class FinalDiagnosis:
    component: str
    root_cause: str
    evidence_ids: tuple[str, ...]
    confidence: int


@dataclass
class IncidentState(State):
    case_id: str = ""
    injection_time: int = 0
    phase: ConsultationPhase = ConsultationPhase.INDEPENDENT_ANALYSIS
    evidence: dict[str, tuple[Evidence, ...]] = field(default_factory=dict)
    findings: dict[str, Finding] = field(default_factory=dict)
    final_diagnosis: FinalDiagnosis | None = None
    consumed_action_ids: set[str] = field(default_factory=set)

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> "IncidentState":
        return cls(task_id=task_id, session_id=session_id)

    @classmethod
    def from_case(cls, case: IncidentCase, *, task_id: str, session_id: str) -> "IncidentState":
        return cls(task_id=task_id, session_id=session_id, case_id=case.case_id, injection_time=case.injection_time, evidence=case.evidence)

    @property
    def is_terminal(self) -> bool:
        return self.phase is ConsultationPhase.FINISHED

    def evidence_for(self, role: ExpertRole) -> tuple[Evidence, ...]:
        return self.evidence.get(role.value, ())

    def all_evidence_ids(self) -> set[str]:
        return {item.evidence_id for items in self.evidence.values() for item in items}

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "case_id": self.case_id,
            "injection_time": self.injection_time,
            "phase": self.phase.value,
            "evidence": {kind: [item.to_dict() for item in items] for kind, items in self.evidence.items()},
            "findings": {
                key: {
                    "finding_id": value.finding_id,
                    "expert": value.expert,
                    "role": value.role.value,
                    "component": value.component,
                    "summary": value.summary,
                    "evidence_ids": list(value.evidence_ids),
                    "confidence": value.confidence,
                }
                for key, value in self.findings.items()
            },
            "final_diagnosis": None if self.final_diagnosis is None else {
                "component": self.final_diagnosis.component,
                "root_cause": self.final_diagnosis.root_cause,
                "evidence_ids": list(self.final_diagnosis.evidence_ids),
                "confidence": self.final_diagnosis.confidence,
            },
            "consumed_action_ids": sorted(self.consumed_action_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "IncidentState":
        raw_findings = data.get("findings") or {}
        raw_diagnosis = data.get("final_diagnosis")
        return cls(
            task_id=str(data["task_id"]),
            session_id=str(data["session_id"]),
            case_id=str(data.get("case_id", "")),
            injection_time=int(data.get("injection_time", 0)),
            phase=ConsultationPhase(str(data.get("phase", ConsultationPhase.INDEPENDENT_ANALYSIS.value))),
            evidence={
                str(kind): tuple(Evidence.from_dict(item) for item in items)
                for kind, items in dict(data.get("evidence") or {}).items()
            },
            findings={
                str(key): Finding(
                    finding_id=str(value["finding_id"]), expert=str(value["expert"]),
                    role=ExpertRole(str(value["role"])), component=str(value["component"]),
                    summary=str(value["summary"]), evidence_ids=tuple(str(item) for item in value["evidence_ids"]),
                    confidence=int(value["confidence"]),
                )
                for key, value in dict(raw_findings).items()
            },
            final_diagnosis=None if not isinstance(raw_diagnosis, dict) else FinalDiagnosis(
                component=str(raw_diagnosis["component"]), root_cause=str(raw_diagnosis["root_cause"]),
                evidence_ids=tuple(str(item) for item in raw_diagnosis["evidence_ids"]), confidence=int(raw_diagnosis["confidence"]),
            ),
            consumed_action_ids={str(item) for item in data.get("consumed_action_ids", [])},
        )
