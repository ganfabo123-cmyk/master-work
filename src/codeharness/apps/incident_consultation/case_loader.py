"""Load one RCAEval sample into bounded, source-addressable evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    kind: str
    summary: str
    source_file: str
    source_locator: str

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "summary": self.summary,
            "source_file": self.source_file,
            "source_locator": self.source_locator,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Evidence":
        return cls(**data)


@dataclass(frozen=True, slots=True)
class IncidentCase:
    case_id: str
    injection_time: int
    evidence: dict[str, tuple[Evidence, ...]]


def load_rcaeval_case(root: Path) -> IncidentCase:
    """Create compact evidence without modifying or copying the source rows."""
    source = _source_directory(root)
    injection_time = int((source / "inject_time.txt").read_text(encoding="utf-8").strip())
    return IncidentCase(
        case_id="rcaeval-multi-source-sample",
        injection_time=injection_time,
        evidence={
            "metrics": _metric_evidence(source / "metrics.csv", injection_time),
            "logs": _log_evidence(source / "logs.csv", injection_time),
            "traces": _trace_evidence(source / "traces.csv", injection_time),
        },
    )


def _source_directory(root: Path) -> Path:
    direct = root / "multi-source-data"
    source = direct if direct.is_dir() else root
    required = ("inject_time.txt", "metrics.csv", "logs.csv", "traces.csv")
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"RCAEval case is missing: {', '.join(missing)}")
    return source


def _metric_evidence(path: Path, injection_time: int) -> tuple[Evidence, ...]:
    before: dict[str, list[float]] = defaultdict(list)
    after: dict[str, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            timestamp = int(float(row["time"]))
            target = before if injection_time - 120 <= timestamp < injection_time else after if injection_time <= timestamp <= injection_time + 120 else None
            if target is None:
                continue
            for name, raw in row.items():
                if name == "time" or raw in (None, "", "nan", "NaN"):
                    continue
                try:
                    target[name].append(float(raw))
                except ValueError:
                    continue
    changes: list[tuple[float, str, float, float]] = []
    for name in before.keys() & after.keys():
        if not before[name] or not after[name]:
            continue
        old, new = fmean(before[name]), fmean(after[name])
        scale = max(abs(old), 1e-9)
        changes.append((abs(new - old) / scale, name, old, new))
    return tuple(
        Evidence(
            evidence_id=f"metric-{index}",
            kind="metrics",
            summary=f"{name}: 注入前均值 {old:.6g}，注入后均值 {new:.6g}，相对变化 {score:.2f}。",
            source_file="metrics.csv",
            source_locator=f"time={injection_time - 120}..{injection_time + 120};column={name}",
        )
        for index, (score, name, old, new) in enumerate(sorted(changes, reverse=True)[:8], 1)
    )


def _log_evidence(path: Path, injection_time: int) -> tuple[Evidence, ...]:
    counts: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                timestamp = int(row["timestamp"]) // 1_000_000_000
            except (KeyError, TypeError, ValueError):
                continue
            if not injection_time - 120 <= timestamp <= injection_time + 120:
                continue
            service = row.get("container_name") or "unknown"
            signal = row.get("error") or row.get("level") or row.get("log_template") or "unclassified"
            key = (service, signal)
            counts[key] += 1
            examples.setdefault(key, row.get("message") or row.get("log_template") or "")
    return tuple(
        Evidence(
            evidence_id=f"log-{index}",
            kind="logs",
            summary=f"{service}: 信号 {signal!r} 出现 {count} 次；示例：{examples[(service, signal)][:240]}",
            source_file="logs.csv",
            source_locator=f"timestamp={injection_time - 120}..{injection_time + 120};container={service}",
        )
        for index, ((service, signal), count) in enumerate(counts.most_common(8), 1)
    )


def _trace_evidence(path: Path, injection_time: int) -> tuple[Evidence, ...]:
    durations: dict[str, list[float]] = defaultdict(list)
    errors: Counter[str] = Counter()
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                timestamp = int(row["startTimeMillis"]) // 1000
            except (KeyError, TypeError, ValueError):
                continue
            if not injection_time - 120 <= timestamp <= injection_time + 120:
                continue
            service = row.get("serviceName") or "unknown"
            try:
                durations[service].append(float(row.get("duration") or 0))
            except ValueError:
                pass
            status = row.get("statusCode")
            if status not in (None, "", "0", "0.0"):
                errors[service] += 1
    ranked = sorted(
        ((fmean(values), service, len(values), errors[service]) for service, values in durations.items() if values),
        reverse=True,
    )[:8]
    return tuple(
        Evidence(
            evidence_id=f"trace-{index}",
            kind="traces",
            summary=f"{service}: {count} 个 Span，平均 duration={average:.2f}，非零状态 {error_count} 次。",
            source_file="traces.csv",
            source_locator=f"startTimeMillis={injection_time - 120}000..{injection_time + 120}000;service={service}",
        )
        for index, (average, service, count, error_count) in enumerate(ranked, 1)
    )
