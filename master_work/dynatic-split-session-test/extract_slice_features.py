"""Extract interpretable, low-cost features from per-slice token counts.

This is deliberately not an LLM classifier.  It uses only token frequencies,
document frequency across slices, a small transparent lexicon, and simple
co-occurrence rules to produce an inspectable feature card for every slice.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


# These are intentionally small and editable.  They are behavior signals, not
# ground-truth labels.
SIGNAL_LEXICONS: dict[str, set[str]] = {
    "read_or_locate": {
        "read", "grep", "find", "search", "locate", "list", "ls", "cat",
        "inspect", "explore", "look", "scan", "查看", "读取", "搜索", "查找",
    },
    "modify": {
        "edit", "write", "replace", "update", "patch", "modify", "change",
        "create", "add", "delete", "remove", "implement", "fix", "修改", "编辑",
    },
    "test_or_build": {
        "test", "tests", "pytest", "jest", "build", "compile", "check", "verify",
        "lint", "run", "npm", "gradle", "maven", "构建", "测试", "验证", "编译",
    },
    "failure": {
        "error", "failed", "failure", "exception", "traceback", "crash", "invalid",
        "bug", "issue", "失败", "错误", "异常", "报错",
    },
    "recovery": {
        "retry", "again", "rollback", "recover", "repair", "resolve", "fix",
        "重试", "恢复", "修复", "解决",
    },
    "documentation": {
        "readme", "markdown", "md", "documentation", "docs", "document", "文档",
    },
    "configuration": {
        "config", "configuration", "settings", "package", "json", "yaml", "yml",
        "toml", "env", "依赖", "配置",
    },
}

OBJECT_LEXICONS: dict[str, set[str]] = {
    "source_code": {"src", "source", "code", "class", "function", "method", "ts", "js", "py", "java", "代码"},
    "tests": {"test", "tests", "pytest", "jest", "spec", "测试"},
    "configuration": {"config", "configuration", "package", "json", "yaml", "yml", "toml", "env", "配置"},
    "documentation": {"readme", "markdown", "md", "docs", "document", "文档"},
}


def normalize_token(token: str) -> str:
    return token.strip().lower()


def load_records(input_dir: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(input_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["feature_source_file"] = str(path)
        records.append(data)
    if not records:
        raise SystemExit(f"No per-slice JSON files found in {input_dir}")
    return records


def calculate_idf(records: list[dict[str, Any]]) -> dict[str, float]:
    document_frequency: Counter[str] = Counter()
    for record in records:
        document_frequency.update({normalize_token(token) for token in record["token_frequencies"]})
    total = len(records)
    return {
        token: math.log((total + 1) / (count + 1)) + 1.0
        for token, count in document_frequency.items()
    }


def lexicon_scores(
    frequencies: dict[str, int],
    idf: dict[str, float],
) -> dict[str, float]:
    normalized = {normalize_token(token): count for token, count in frequencies.items()}
    total = max(sum(normalized.values()), 1)
    scores = {}
    for name, lexicon in SIGNAL_LEXICONS.items():
        scores[name] = round(
            sum(count * idf.get(token, 1.0) for token, count in normalized.items() if token in lexicon)
            / total,
            6,
        )
    return scores


def object_scores(frequencies: dict[str, int], idf: dict[str, float]) -> dict[str, float]:
    normalized = {normalize_token(token): count for token, count in frequencies.items()}
    total = max(sum(normalized.values()), 1)
    return {
        name: round(
            sum(count * idf.get(token, 1.0) for token, count in normalized.items() if token in lexicon)
            / total,
            6,
        )
        for name, lexicon in OBJECT_LEXICONS.items()
    }


def top_discriminative_tokens(
    frequencies: dict[str, int],
    idf: dict[str, float],
    limit: int = 20,
) -> list[dict[str, Any]]:
    scored = []
    for token, count in frequencies.items():
        normalized = normalize_token(token)
        if not normalized or not re.search(r"[a-z0-9\u3400-\u9fff]", normalized):
            continue
        scored.append({
            "token": token,
            "count": count,
            "idf": round(idf.get(normalized, 1.0), 6),
            "tfidf_score": round(count * idf.get(normalized, 1.0), 6),
        })
    scored.sort(key=lambda item: (-item["tfidf_score"], item["token"].lower()))
    return scored[:limit]


def infer_behavior(signals: dict[str, float], objects: dict[str, float]) -> tuple[str, float, list[str]]:
    read = signals["read_or_locate"]
    modify = signals["modify"]
    verify = signals["test_or_build"]
    failure = signals["failure"]
    recovery = signals["recovery"]

    candidates: list[tuple[str, float, list[str]]] = [
        ("失败后的修复与重新验证", failure + recovery + modify + verify,
         ["failure", "recovery", "modify", "test_or_build"]),
        ("修改代码并验证", modify + verify,
         ["modify", "test_or_build"]),
        ("仓库探索与问题定位", read + objects["source_code"],
         ["read_or_locate", "source_code"]),
        ("配置或依赖处理", modify + signals["configuration"] + objects["configuration"],
         ["modify", "configuration"]),
        ("测试或构建验证", verify,
         ["test_or_build"]),
        ("文档处理", signals["documentation"] + objects["documentation"],
         ["documentation"]),
    ]
    candidates.sort(key=lambda item: item[1], reverse=True)
    label, raw_score, evidence = candidates[0]
    # This is a relative heuristic confidence, not a calibrated probability.
    total = sum(signals.values()) + 1e-9
    confidence = min(0.99, max(0.05, raw_score / total))
    active_evidence = [name for name in evidence if signals.get(name, objects.get(name, 0.0)) > 0]
    return label, round(confidence, 4), active_evidence


def make_feature(record: dict[str, Any], idf: dict[str, float]) -> dict[str, Any]:
    frequencies = record["token_frequencies"]
    signals = lexicon_scores(frequencies, idf)
    objects = object_scores(frequencies, idf)
    behavior, confidence, evidence = infer_behavior(signals, objects)
    source = Path(record["source_file"])
    slice_id = f"{source.parent.name}__{source.stem}"
    return {
        "slice_id": slice_id,
        "source_path": str(source),
        "segment_index": record.get("segment_index"),
        "event_range": [record.get("start_event"), record.get("end_event")],
        "behavior_guess": behavior,
        "behavior_confidence_heuristic": confidence,
        "evidence_dimensions": evidence,
        "signal_scores": signals,
        "object_scores": objects,
        "top_discriminative_tokens": top_discriminative_tokens(frequencies, idf),
        "token_count": record.get("token_count"),
        "unique_token_count": record.get("unique_token_count"),
    }


def write_markdown(features: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Slice Features",
        "",
        "基于 token 频数、跨切片 IDF 和透明词典生成；行为判断是启发式结果，不是人工标签。",
        "",
        "| Slice ID | Source path | Behavior guess | Confidence | Top evidence tokens |",
        "|---|---|---|---:|---|",
    ]
    for feature in features:
        tokens = ", ".join(item["token"] for item in feature["top_discriminative_tokens"][:8])
        lines.append(
            f"| `{feature['slice_id']}` | `{feature['source_path']}` | "
            f"{feature['behavior_guess']} | {feature['behavior_confidence_heuristic']:.3f} | {tokens} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract interpretable features per trajectory slice")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    records = load_records(args.input_dir)
    idf = calculate_idf(records)
    features = [make_feature(record, idf) for record in records]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = args.output_dir / "slice-features.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for feature in features:
            handle.write(json.dumps(feature, ensure_ascii=False) + "\n")
    write_markdown(features, args.output_dir / "slice-features.md")
    (args.output_dir / "feature-config.json").write_text(
        json.dumps({
            "method": "tfidf + transparent lexicon scores + co-signal heuristic",
            "slice_count": len(features),
            "idf_vocabulary_size": len(idf),
            "not_llm_classified": True,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "slice_count": len(features),
        "jsonl": str(jsonl_path),
        "markdown": str(args.output_dir / "slice-features.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
