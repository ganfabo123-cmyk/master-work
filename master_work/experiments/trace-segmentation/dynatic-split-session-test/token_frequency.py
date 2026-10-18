"""Count token frequencies in segmented trajectory files.

The script intentionally does not perform semantic analysis.  It only extracts
text from each segment and counts tokens, so the result can be reused by later
feature-extraction experiments.

Examples:
    python token_frequency.py \
      --slices-dir calibrated-confidence-length-banded-v3-slices \
      --output token-frequency-banded-v3
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


# A token is one of:
#   - a contiguous CJK run, e.g. "张三"
#   - a Latin/number/underscore run, e.g. "build_profile"
#   - a decimal/integer number
#   - one non-whitespace, non-word symbol
#
# Keeping CJK runs together makes the output useful for names and short Chinese
# phrases without requiring jieba or another external dependency.
TOKEN_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uF900-\uFAFF]+"
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|\d+(?:\.\d+)?"
    r"|[^\s\w]",
    re.UNICODE,
)


def tokenize(text: str, *, include_symbols: bool = True) -> list[str]:
    """Tokenize text deterministically without an external model or service."""
    tokens = TOKEN_RE.findall(text)
    if include_symbols:
        return tokens
    return [token for token in tokens if re.search(r"[\w\u3400-\u9fff]", token)]


def iter_text_values(value: Any) -> Iterable[str]:
    """Yield user/model/tool text recursively from a JSON value.

    Only values under a key named ``text`` are counted.  This avoids counting
    structural metadata such as category names, event indexes, and file names.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "text" and isinstance(child, str):
                yield child
            elif key != "text":
                yield from iter_text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_text_values(child)


def load_segment(path: Path, *, include_symbols: bool) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    counter: Counter[str] = Counter()
    text_count = 0
    character_count = 0

    for text in iter_text_values(data.get("events", data)):
        text_count += 1
        character_count += len(text)
        counter.update(tokenize(text, include_symbols=include_symbols))

    total_tokens = sum(counter.values())
    return {
        "source_file": str(path),
        "session_id": data.get("session_id"),
        "segment_index": data.get("segment_index"),
        "start_event": data.get("start_event"),
        "end_event": data.get("end_event"),
        "event_count": len(data.get("events", [])),
        "text_count": text_count,
        "character_count": character_count,
        "token_count": total_tokens,
        "unique_token_count": len(counter),
        "token_frequencies": dict(counter.most_common()),
    }


def iter_segment_files(slices_dir: Path) -> Iterable[Path]:
    yield from sorted(slices_dir.rglob("segment-*.json"))


def decompose_token_sets(results: list[dict[str, Any]]) -> tuple[set[str], dict[str, set[str]]]:
    """Split complete per-segment token sets into common and unique parts.

    For every segment ``S_i`` this produces:

        S_i = common_tokens | unique_tokens[i]

    where ``common_tokens`` is the intersection of all segment token sets.
    Frequencies are deliberately not used here: this operation is set
    decomposition, so a token is either present or absent in a segment.
    """
    if not results:
        return set(), {}

    token_sets = {
        segment_key(result): set(result["token_frequencies"])
        for result in results
    }
    common_tokens = set.intersection(*token_sets.values())
    unique_tokens = {
        key: tokens - common_tokens
        for key, tokens in token_sets.items()
    }
    return common_tokens, unique_tokens


def decompose_by_presence_threshold(
    results: list[dict[str, Any]],
    threshold: float,
) -> tuple[set[str], dict[str, set[str]], dict[str, int]]:
    """Decompose token sets by token presence across a fraction of segments.

    A token belongs to the ``threshold`` common set when it appears in at least
    ``ceil(threshold * segment_count)`` segment token sets.  For example, at
    0.90 a token present in 90% or more of the slices is considered common.

    The returned per-segment sets are residual sets, so for every segment:

        full_tokens = threshold_common_tokens | residual_tokens[segment]
    """
    if not results:
        return set(), {}, {}
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")

    token_sets = {
        segment_key(result): set(result["token_frequencies"])
        for result in results
    }
    document_frequency: Counter[str] = Counter()
    for tokens in token_sets.values():
        document_frequency.update(tokens)

    minimum_segments = math.ceil(threshold * len(token_sets))
    common_tokens = {
        token
        for token, count in document_frequency.items()
        if count >= minimum_segments
    }
    residual_tokens = {
        key: tokens - common_tokens
        for key, tokens in token_sets.items()
    }
    return common_tokens, residual_tokens, dict(document_frequency)


def group_tokens_by_presence_rate(
    results: list[dict[str, Any]],
    lower_percent: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return one mutually exclusive token-frequency band.

    The 100% band contains tokens present in every segment.  Other bands are
    half-open intervals: 90% means [90%, 100%), 80% means [80%, 90%), etc.
    Therefore a token is emitted in exactly one band rather than repeated in
    every cumulative threshold above its frequency.
    """
    if not results or lower_percent < 10 or lower_percent > 100:
        raise ValueError("lower_percent must be between 10 and 100")

    token_sets = {
        segment_key(result): set(result["token_frequencies"])
        for result in results
    }
    document_frequency: Counter[str] = Counter()
    for tokens in token_sets.values():
        document_frequency.update(tokens)

    segment_count = len(results)
    lower_count = math.ceil((lower_percent / 100) * segment_count)
    if lower_percent == 100:
        selected = {
            token: count
            for token, count in document_frequency.items()
            if count == segment_count
        }
    else:
        upper_count = math.ceil(((lower_percent + 10) / 100) * segment_count)
        selected = {
            token: count
            for token, count in document_frequency.items()
            if lower_count <= count < upper_count
        }

    rows = [
        {
            "token": token,
            "segment_count": count,
            "segment_rate": count / segment_count,
        }
        for token, count in selected.items()
    ]
    rows.sort(key=lambda row: (-row["segment_count"], row["token"]))
    return rows, dict(document_frequency)


def segment_key(result: dict[str, Any]) -> str:
    """Return a stable output key for one segment."""
    source_path = Path(result["source_file"])
    return f"{source_path.parent.name}__{source_path.stem}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Count tokens in every trajectory segment")
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-symbols",
        action="store_true",
        help="Also count punctuation and other standalone symbols",
    )
    args = parser.parse_args()

    if not args.slices_dir.is_dir():
        raise SystemExit(f"Slices directory does not exist: {args.slices_dir}")

    segment_files = list(iter_segment_files(args.slices_dir))
    if not segment_files:
        raise SystemExit(f"No segment-*.json files found under: {args.slices_dir}")

    results = [
        load_segment(path, include_symbols=args.include_symbols)
        for path in segment_files
    ]

    args.output.mkdir(parents=True, exist_ok=True)
    segments_output = args.output / "segments"
    segments_output.mkdir(parents=True, exist_ok=True)

    # One independent JSON file per segment.  The frequency table in each file
    # belongs only to that segment; no cross-segment frequency table is built.
    for result in results:
        source_path = Path(result["source_file"])
        output_path = segments_output / f"{segment_key(result)}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    common_tokens, unique_tokens = decompose_token_sets(results)
    decomposition_dir = args.output / "token-set-decomposition"
    unique_output_dir = decomposition_dir / "unique"
    unique_output_dir.mkdir(parents=True, exist_ok=True)

    (decomposition_dir / "common-tokens.json").write_text(
        json.dumps({
            "segment_count": len(results),
            "token_count": len(common_tokens),
            "tokens": sorted(common_tokens),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    decomposition_manifest = {
        "segment_count": len(results),
        "common_token_count": len(common_tokens),
        "segments": [],
    }
    for result in results:
        key = segment_key(result)
        unique = sorted(unique_tokens[key])
        (unique_output_dir / f"{key}.json").write_text(
            json.dumps({
                "segment_key": key,
                "unique_token_count": len(unique),
                "unique_tokens": unique,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        decomposition_manifest["segments"].append({
            "segment_key": key,
            "full_token_count": len(result["token_frequencies"]),
            "common_token_count": len(common_tokens),
            "unique_token_count": len(unique),
            "unique_tokens_file": str(unique_output_dir / f"{key}.json"),
        })

    (decomposition_dir / "decomposition.json").write_text(
        json.dumps(decomposition_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    threshold_root = args.output / "presence-thresholds"
    threshold_manifest = []
    for percent in range(10, 101, 10):
        threshold = percent / 100
        band_rows, document_frequency = group_tokens_by_presence_rate(results, percent)
        threshold_dir = threshold_root / f"{percent:03d}pct"
        threshold_dir.mkdir(parents=True, exist_ok=True)

        lower_count = math.ceil(threshold * len(results))
        upper_count = (
            len(results)
            if percent == 100
            else math.ceil(((percent + 10) / 100) * len(results)) - 1
        )
        (threshold_dir / "common-tokens.json").write_text(
            json.dumps({
                "band": f"{percent}%",
                "lower_rate": threshold,
                "upper_rate": 1.0 if percent == 100 else (percent + 10) / 100,
                "minimum_segment_count": lower_count,
                "maximum_segment_count": upper_count,
                "segment_count": len(results),
                "token_count": len(band_rows),
                "tokens": band_rows,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        threshold_manifest.append({
            "band": f"{percent}%",
            "minimum_segment_count": lower_count,
            "maximum_segment_count": upper_count,
            "common_token_count": len(band_rows),
            "directory": str(threshold_dir),
        })

    (threshold_root / "thresholds.json").write_text(
        json.dumps({"thresholds": threshold_manifest}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "slices_dir": str(args.slices_dir),
        "segment_count": len(results),
        "tokenizer": "cjk-runs + latin-identifiers + numbers + symbols",
        "include_symbols": args.include_symbols,
        "output_mode": "one JSON file per segment",
        "output_dir": str(segments_output),
        "token_set_decomposition": {
            "common_token_count": len(common_tokens),
            "unique_sets_dir": str(unique_output_dir),
            "manifest": str(decomposition_dir / "decomposition.json"),
        },
        "presence_thresholds": str(threshold_root),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "segment_count": summary["segment_count"],
        "output_dir": str(segments_output),
        "summary": str(args.output / "summary.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
