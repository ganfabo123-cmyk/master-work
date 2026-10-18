"""Cheap, auditable target and execution-logic clustering for trajectory slices.

The implementation intentionally uses only local event text, deterministic token
statistics, parsed tool operations, and ordered operation sequences.  It does not
call an embedding service or an LLM.  A domain is processed independently so that
domain vocabulary can be retained as evidence while being down-weighted for the
behaviour comparison.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

try:
    from token_frequency import tokenize
    from tool_operation_objects import extract_tool, file_type
except ImportError:  # pragma: no cover - supports direct execution from another cwd
    from .token_frequency import tokenize
    from .tool_operation_objects import extract_tool, file_type


TARGET_WEIGHTS = {"user": 1.00, "assistant": 0.60, "thinking": 0.30, "tool": 0.15}
LOGIC_WEIGHTS = {"user": 0.20, "assistant": 0.80, "thinking": 0.40, "tool": 1.00}
# These are event-role weights, not domain labels.  They keep the evidence
# channels independent while allowing the same implementation to work on a
# domain that was not present when the script was written.
PROBLEM_WEIGHTS = {"user": 1.00, "assistant": 0.65, "thinking": 0.45, "tool": 0.15}
RESOLUTION_WEIGHTS = {"user": 0.15, "assistant": 0.80, "thinking": 0.45, "tool": 1.00}
VERIFICATION_WEIGHTS = {"user": 0.05, "assistant": 0.55, "thinking": 0.35, "tool": 0.90}
PHASES = ("early", "middle", "late")
MAX_TEXT_CHARS = 1200
MAX_TOOL_TEXT_CHARS = 600
MAX_SEQUENCE_LENGTH = 160

STOP_WORDS = set("""
a an and are as at be been but by can could did do does for from had has have
here how i if in into is it its me my no not of on or our out so that the their
them there these this those to us was we were what when where which who will
with would you your also all any each every just more most much now one other
some such than then they very via while yet the now let this only should all
about above after again against am an any because before being below between
both during each few further here how more most other over own same some than
too very what when where why once only just already actually across around
again still also back both either enough ever every get got had has having
into itself like may might must need next nor often perhaps rather really
seem since such take their them these those through under until upon used using
want well went were whatever whenever whether without within
""".split())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_slice_id(value: str) -> str:
    return value.removeprefix("segments__")


def session_id_for_slice(slice_id: str) -> str:
    """Recover the source Session without relying on a domain name or label."""
    marker = "__segment-"
    if marker in slice_id:
        return slice_id.rsplit(marker, 1)[0]
    return slice_id


def compact_text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"```[\s\S]*?```", " ", value)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    half = max(1, limit // 2)
    return text[:half] + " … " + text[-half:]


def clean_token(token: str) -> str:
    return token.strip().casefold()


def structural_noise(token: str) -> bool:
    token = clean_token(token)
    if not token or token in STOP_WORDS:
        return True
    if len(token) < 2 and not re.search(r"[\u3400-\u9fff]", token):
        return True
    if token.isnumeric() or re.fullmatch(r"\d+(?:\.\d+)+", token):
        return True
    # Identifier-shaped fragments are usually implementation details rather
    # than transferable behaviour evidence.  This is syntax filtering, not a
    # vocabulary of any application domain.
    if "_" in token:
        return True
    if re.fullmatch(r"[a-z]{0,5}\d+[a-z0-9]*", token) and len(token) <= 16:
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", token) and any(c.isdigit() for c in token):
        return True
    if re.fullmatch(r"[0-9a-f]{4,8}(?:-[0-9a-f]{4,8}){2,}", token):
        return True
    if token.startswith(("/", "\\", "c:/", "c:\\")) or "/" in token or "\\" in token:
        return True
    if token.startswith(("http", "www.")) or len(token) > 64:
        return True
    if re.fullmatch(r"[.!?,:;(){}\[\]<>+*=|&%#$@`~\-]+", token):
        return True
    return False


def rarity(document_rate: float) -> float:
    """Non-linear rare-token weight used by the domain experiments."""
    a = (1.0 - document_rate) ** 2
    b = document_rate**2
    return a / (a + b) if a + b else 0.0


def event_channel(event: dict[str, Any]) -> str | None:
    category = str(event.get("category", ""))
    if category == "user_text":
        return "user"
    if category == "assistant_text":
        return "assistant"
    if category in {"assistant_thinking", "assistant_reasoning"}:
        return "thinking"
    if category.startswith("tool_call:"):
        return "tool"
    return None


def argument_texts(value: object, key: str = "") -> Iterable[str]:
    """Yield short descriptive tool arguments, never long Write/Edit content."""
    if isinstance(value, str):
        if key in {"content", "patch", "old_string", "new_string", "replacement"}:
            return
        yield compact_text(value, MAX_TOOL_TEXT_CHARS)
    elif isinstance(value, dict):
        for child_key, child in value.items():
            yield from argument_texts(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from argument_texts(child, key)


def token_set(texts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        for raw in tokenize(text, include_symbols=False):
            token = clean_token(raw)
            if structural_noise(token) or token in seen:
                continue
            seen.add(token)
            result.append(token)
    return result


def phase_for(position: int, start: int, end: int) -> str:
    span = max(end - start, 1)
    ratio = (position - start) / span
    return PHASES[min(2, int(ratio * 3))]


def safe_operation_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:+-]", "_", value.casefold())


def build_event_rows(source: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    start = source.get("core_start_event")
    end = source.get("core_end_event")
    if start is None:
        start = source.get("start_event", 1)
    if end is None:
        end = source.get("end_event", start + len(source.get("events", [])) - 1)
    rows: list[dict[str, Any]] = []
    for offset, event in enumerate(source.get("events", [])):
        index = source.get("start_event", 1) + offset
        if not start <= index <= end:
            continue
        channel = event_channel(event)
        if channel is None:
            continue
        text_values: list[str] = []
        operations: list[str] = []
        targets: list[str] = []
        target_types: list[str] = []
        if channel == "tool":
            text_values.extend(argument_texts(event.get("arguments")))
            operations, targets, _ = extract_tool(event)
            target_types = [file_type(target) for target in targets]
        elif isinstance(event.get("text"), str):
            text_values.append(compact_text(event["text"], MAX_TEXT_CHARS))
        lexical = token_set(text_values)
        operation_tokens = [f"op:{safe_operation_token(item)}" for item in operations]
        operation_tokens.extend(f"filetype:{safe_operation_token(item)}" for item in target_types)
        if channel == "tool":
            tool_name = str(event.get("tool_name") or str(event.get("category", "")).removeprefix("tool_call:"))
            operation_tokens.insert(0, f"tool:{safe_operation_token(tool_name)}")
        symbols = [{"user": "U", "assistant": "A", "thinking": "H", "tool": "T"}[channel]]
        if channel == "tool":
            symbols = [f"T:{safe_operation_token(item)}" for item in operations] or [f"T:{safe_operation_token(str(event.get('tool_name') or 'unknown'))}"]
        rows.append({
            "event_index": index,
            "channel": channel,
            "tokens": lexical,
            "operation_tokens": operation_tokens,
            "symbols": symbols,
            "phase": phase_for(index, int(start), int(end)),
            "text_preview": compact_text(" ".join(text_values), 240),
            "operations": operations,
            "targets": targets,
            "target_types": target_types,
        })
    return rows


def load_slices(slices_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(slices_dir.rglob("segment-*.json")):
        source = read_json(path)
        sid = f"{path.parent.name}__{path.stem}"
        events = build_event_rows(source, path)
        result[sid] = {
            "slice_id": sid,
            "source_path": str(path.resolve()),
            "events": events,
            "first_user_text": next((row["text_preview"] for row in events if row["channel"] == "user"), ""),
        }
    if not result:
        raise ValueError(f"No segment files found under {slices_dir}")
    return result


def load_domains(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if isinstance(data, dict):
        data = data.get("domains", [])
    domains = []
    for row in data:
        did = row.get("domain_id") or row.get("cluster_id")
        members = row.get("members") or row.get("member_slice_ids") or []
        if did and members:
            domains.append({**row, "domain_id": did, "members": [normalize_slice_id(str(item)) for item in members]})
    return domains


def load_cards(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    data = read_json(path)
    if isinstance(data, dict):
        data = data.get("cards", data.get("domains", []))
    return {row.get("domain_id"): row for row in data if row.get("domain_id")}


def derive_anchors(domain: dict[str, Any], card: dict[str, Any] | None) -> set[str]:
    values: list[str] = []
    for key in ("terms", "core_terms", "source_terms", "distinctive_terms", "extended_terms"):
        values.extend(str(item) for item in domain.get(key, []) if isinstance(item, (str, int, float)))
        if card:
            values.extend(str(item) for item in card.get(key, []) if isinstance(item, (str, int, float)))
    if card:
        for item in card.get("file_tool_evidence", []):
            values.append(str(item).split(":", 1)[-1])
    anchors = set()
    for value in values:
        for token in token_set([value]):
            anchors.add(token)
    return anchors


def all_token_sets(slices: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    target: dict[str, set[str]] = {}
    logic: dict[str, set[str]] = {}
    for row in slices:
        target[row["slice_id"]] = set(token for event in row["events"] for token in event["tokens"] + event["operation_tokens"])
        logic[row["slice_id"]] = set(token for event in row["events"] for token in event["tokens"] + event["operation_tokens"])
    return target, logic


def document_stats(token_sets: dict[str, set[str]]) -> tuple[dict[str, int], int]:
    df = Counter()
    for tokens in token_sets.values():
        df.update(tokens)
    return dict(df), max(len(token_sets), 1)


def l2_normalize(vector: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    return {key: value / norm for key, value in vector.items()} if norm else {}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return max(0.0, min(1.0, sum(value * right.get(key, 0.0) for key, value in left.items())))


def sequence_ngrams(sequence: list[str]) -> dict[str, float]:
    vector: Counter[str] = Counter()
    for size in (2, 3):
        for index in range(len(sequence) - size + 1):
            vector["→".join(sequence[index:index + size])] += 1.0
    return l2_normalize(dict(vector))


def lcs_similarity(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left = left[:MAX_SEQUENCE_LENGTH]
    right = right[:MAX_SEQUENCE_LENGTH]
    previous = [0] * (len(right) + 1)
    for a in left:
        current = [0]
        for index, b in enumerate(right, start=1):
            current.append(previous[index - 1] + 1 if a == b else max(previous[index], current[-1]))
        previous = current
    return previous[-1] / max(len(left), len(right))


def compress_sequence(symbols: list[str], phases: list[str]) -> tuple[list[str], list[str]]:
    sequence: list[str] = []
    phase_sequence: list[str] = []
    for symbol, phase in zip(symbols, phases, strict=True):
        if sequence and sequence[-1] == symbol:
            continue
        sequence.append(symbol)
        phase_sequence.append(f"phase:{phase}:{symbol}")
    return sequence[:MAX_SEQUENCE_LENGTH], phase_sequence[:MAX_SEQUENCE_LENGTH]


def _binary_cosine(left: dict[str, int] | set[str], right: dict[str, int] | set[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / math.sqrt(len(left_set) * len(right_set))


def build_domain_features(slices: list[dict[str, Any]], anchors: set[str], global_df: dict[str, int] | None = None, global_n: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_sets, logic_sets = all_token_sets(slices)
    target_df, n = document_stats(target_sets)
    logic_df, _ = document_stats(logic_sets)
    session_token_sets: dict[str, set[str]] = defaultdict(set)
    for row in slices:
        session_id = session_id_for_slice(row["slice_id"])
        session_token_sets[session_id].update(
            token
            for event in row["events"]
            for token in event["tokens"] + event["operation_tokens"]
        )
    session_df, session_n = document_stats(session_token_sets)

    # Sequence statistics are also computed before weighting.  A repeated
    # Read/Edit/Test pattern is useful, but a pattern present in nearly every
    # Session should not dominate the logical representation.
    raw_sequences: dict[str, tuple[list[str], list[str]]] = {}
    operation_ngram_df: Counter[str] = Counter()
    for row in slices:
        symbols: list[str] = []
        phases: list[str] = []
        for event in row["events"]:
            symbols.extend(event["symbols"])
            phases.extend(event["phase"] for _ in event["symbols"])
        sequence, phase_sequence = compress_sequence(symbols, phases)
        raw_sequences[row["slice_id"]] = (sequence, phase_sequence)
        operation_ngram_df.update(sequence_ngrams(sequence).keys())

    # Global high-document-frequency filtering is computed from the current domain;
    # operation/file tokens remain because they are structural evidence.
    local_blacklist = {
        token for token, count in target_df.items()
        if count / n >= 0.90 and not token.startswith(("op:", "tool:", "filetype:"))
    }
    global_blacklist = {
        token for token, count in (global_df or {}).items()
        if global_n and count / global_n >= 0.35 and not token.startswith(("op:", "tool:", "filetype:"))
    }
    common_blacklist = {token for token in local_blacklist | global_blacklist if token not in anchors}
    features: list[dict[str, Any]] = []

    def token_factor(token: str) -> float:
        df = target_df.get(token, 1)
        p = df / n
        session_p = session_df.get(token, 1) / max(session_n, 1)
        idf = 1.0 + math.log((n + 1) / (df + 1))
        # Session rarity prevents several slices from one long Session from
        # becoming equivalent to independent evidence from several Sessions.
        session_factor = 0.35 + 0.65 * rarity(session_p)
        # Structural operations remain available, but frequent generic
        # operations are data-driven down-weighted rather than hard-coded away.
        structural_factor = 1.0
        if token.startswith(("op:", "tool:", "filetype:")):
            structural_p = df / n
            structural_factor = 0.25 + 0.75 * rarity(structural_p)
        domain_factor = 0.25 if token.removeprefix("op:").removeprefix("tool:").removeprefix("filetype:") in anchors else 1.0
        return rarity(p) * idf * session_factor * structural_factor * domain_factor

    # Evidence cards should expose relatively discriminative terms.  This is
    # a data-derived cut over the current domain, not a list of operation or
    # domain keywords.  The full weighted vectors still retain every allowed
    # token, so this only affects the auditable core evidence.
    factor_by_token = {
        token: token_factor(token)
        for token in target_df
        if token not in common_blacklist
    }
    evidence_factor_cut = quantile(list(factor_by_token.values()), 0.55) if factor_by_token else 0.0

    for row in slices:
        target_vector: dict[str, float] = defaultdict(float)
        logic_text_vector: dict[str, float] = defaultdict(float)
        problem_vector: dict[str, float] = defaultdict(float)
        resolution_vector: dict[str, float] = defaultdict(float)
        verification_vector: dict[str, float] = defaultdict(float)
        phases: list[str] = []
        target_evidence: set[str] = set()
        logic_evidence: set[str] = set()
        problem_evidence: set[str] = set()
        resolution_evidence: set[str] = set()
        verification_evidence: set[str] = set()
        sequence_symbols: list[str] = []
        channel_counts = Counter(event["channel"] for event in row["events"])
        for event in row["events"]:
            channel = event["channel"]
            target_weight = TARGET_WEIGHTS[channel] / max(channel_counts[channel], 1)
            logic_weight = LOGIC_WEIGHTS[channel] / max(channel_counts[channel], 1)
            problem_weight = PROBLEM_WEIGHTS[channel] / max(channel_counts[channel], 1)
            resolution_weight = RESOLUTION_WEIGHTS[channel] / max(channel_counts[channel], 1)
            verification_weight = VERIFICATION_WEIGHTS[channel] / max(channel_counts[channel], 1)
            phase_factor = {"early": 0.65, "middle": 0.85, "late": 1.0}[event["phase"]]
            event_tokens = set(event["tokens"] + event["operation_tokens"])
            for token in event_tokens:
                if token in common_blacklist and not token.startswith(("op:", "tool:", "filetype:")):
                    continue
                factor = token_factor(token)
                value_target = target_weight * factor
                value_logic = logic_weight * factor
                value_problem = problem_weight * factor
                value_resolution = resolution_weight * factor
                value_verification = verification_weight * phase_factor * factor
                target_vector[token] += value_target
                logic_text_vector[token] += value_logic
                problem_vector[token] += value_problem
                resolution_vector[token] += value_resolution
                verification_vector[token] += value_verification
                if value_target and factor >= evidence_factor_cut:
                    target_evidence.add(token)
                if value_logic and factor >= evidence_factor_cut:
                    logic_evidence.add(token)
                if value_problem and factor >= evidence_factor_cut:
                    problem_evidence.add(token)
                if value_resolution and factor >= evidence_factor_cut:
                    resolution_evidence.add(token)
                if value_verification and factor >= evidence_factor_cut:
                    verification_evidence.add(token)
            event_symbols = event["symbols"]
            for symbol in event_symbols:
                sequence_symbols.append(symbol)
                phases.append(event["phase"])
        sequence, phase_sequence = raw_sequences[row["slice_id"]]
        sequence_vector = sequence_ngrams(sequence)
        sequence_vector = {
            # Preserve ordered behavior as the primary logic signal.  The
            # current-domain n-gram rarity is only a mild correction for
            # universal workflows, so high-similar traces are not fragmented.
            key: value * (0.70 + 0.30 * rarity(operation_ngram_df.get(key, 1) / max(n, 1)))
            for key, value in sequence_vector.items()
        }
        sequence_vector = l2_normalize(sequence_vector)
        phase_vector = sequence_ngrams(phase_sequence)
        order_vector = l2_normalize({
            **{key: value * 0.80 for key, value in sequence_vector.items()},
            **{key: value * 0.20 for key, value in phase_vector.items()},
        })
        operation_ngrams = set(sequence_vector)
        features.append({
            "slice_id": row["slice_id"],
            "session_id": session_id_for_slice(row["slice_id"]),
            "source_path": row["source_path"],
            "target_vector": l2_normalize(dict(target_vector)),
            "logic_text_vector": l2_normalize(dict(logic_text_vector)),
            "problem_vector": l2_normalize(dict(problem_vector)),
            "resolution_vector": l2_normalize(dict(resolution_vector)),
            "verification_vector": l2_normalize(dict(verification_vector)),
            "logic_order_vector": order_vector,
            "sequence": sequence,
            "phase_sequence": phase_sequence,
            "operation_ngrams": sorted(operation_ngrams),
            "target_evidence": {token: 1 for token in sorted(target_evidence)},
            "logic_evidence": {token: 1 for token in sorted(logic_evidence)},
            "problem_evidence": {token: 1 for token in sorted(problem_evidence)},
            "resolution_evidence": {token: 1 for token in sorted(resolution_evidence)},
            "verification_evidence": {token: 1 for token in sorted(verification_evidence)},
            "first_user_text": row.get("first_user_text", ""),
            "event_counts": dict(channel_counts),
            "operations": sorted({op for event in row["events"] for op in event["operations"]}),
        })
    config = {
        "slice_count": len(slices),
        "session_count": len(session_token_sets),
        "domain_anchor_count": len(anchors),
        "common_blacklist_count": len(common_blacklist),
        "common_blacklist": sorted(common_blacklist),
        "global_blacklist_rate": 0.35,
        "session_rarity_enabled": True,
        "operation_ngram_rarity_enabled": True,
        "operation_ngram_rarity_floor": 0.70,
        "evidence_factor_cut_quantile": 0.55,
        "evidence_factor_cut": round(evidence_factor_cut, 8),
        "token_document_frequency": dict(sorted(target_df.items())),
        "session_document_frequency": dict(sorted(session_df.items())),
        "operation_ngram_document_frequency": dict(sorted(operation_ngram_df.items())),
    }
    return features, config


def pairwise(features: list[dict[str, Any]], view: str) -> list[list[float]]:
    size = len(features)
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            same_session = features[i].get("session_id") == features[j].get("session_id")
            cross_session_evidence = 0.0
            if view == "target":
                target = cosine(features[i]["target_vector"], features[j]["target_vector"])
                problem = cosine(features[i].get("problem_vector", {}), features[j].get("problem_vector", {}))
                if not same_session:
                    cross_session_evidence = 0.5 * _binary_cosine(features[i]["target_evidence"], features[j]["target_evidence"])
                    cross_session_evidence += 0.5 * _binary_cosine(features[i].get("problem_evidence", {}), features[j].get("problem_evidence", {}))
                value = 0.80 * target + 0.15 * problem + 0.05 * cross_session_evidence
            else:
                order = cosine(features[i]["logic_order_vector"], features[j]["logic_order_vector"])
                lcs = lcs_similarity(features[i]["sequence"], features[j]["sequence"])
                text = cosine(features[i]["logic_text_vector"], features[j]["logic_text_vector"])
                resolution = cosine(features[i].get("resolution_vector", {}), features[j].get("resolution_vector", {}))
                verification = cosine(features[i].get("verification_vector", {}), features[j].get("verification_vector", {}))
                if not same_session:
                    cross_session_evidence = 0.5 * _binary_cosine(features[i].get("resolution_evidence", {}), features[j].get("resolution_evidence", {}))
                    cross_session_evidence += 0.5 * _binary_cosine(features[i].get("verification_evidence", {}), features[j].get("verification_evidence", {}))
                value = (
                    0.56 * order
                    + 0.23 * lcs
                    + 0.12 * text
                    + 0.05 * resolution
                    + 0.03 * verification
                    + 0.01 * cross_session_evidence
                )
            # Repeated slices from one Session remain eligible for the same
            # group, but they cannot provide the same affinity as independent
            # Sessions.  This is a generic provenance correction, not a domain
            # rule.
            if same_session:
                value *= 0.95
            matrix[i][j] = matrix[j][i] = round(value, 8)
    for i in range(size):
        matrix[i][i] = 1.0
    return matrix


def complete_linkage(matrix: list[list[float]], threshold: float) -> list[list[int]]:
    clusters = [[index] for index in range(len(matrix))]
    while len(clusters) > 1:
        best: tuple[float, int, int] | None = None
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                value = min(matrix[a][b] for a in clusters[left] for b in clusters[right])
                candidate = (value, left, right)
                if value >= threshold and (best is None or candidate > best):
                    best = candidate
        if best is None:
            break
        _, left, right = best
        clusters[left].extend(clusters[right])
        del clusters[right]
    return [sorted(cluster) for cluster in clusters]


def silhouette(matrix: list[list[float]], clusters: list[list[int]]) -> float:
    useful = [cluster for cluster in clusters if len(cluster) >= 2]
    if len(useful) < 2:
        return -1.0
    labels = {item: cluster for cluster in useful for item in cluster}
    values = []
    for item, cluster in labels.items():
        own = [other for other in cluster if other != item]
        a = sum(1.0 - matrix[item][other] for other in own) / max(len(own), 1)
        b_values = []
        for other_cluster in useful:
            if other_cluster is cluster:
                continue
            b_values.append(sum(1.0 - matrix[item][other] for other in other_cluster) / len(other_cluster))
        b = min(b_values) if b_values else 1.0
        values.append((b - a) / max(a, b, 1e-9))
    return sum(values) / len(values) if values else -1.0


def choose_clusters(matrix: list[list[float]]) -> tuple[list[list[int]], dict[str, Any]]:
    n = len(matrix)
    if n < 2:
        return [[0]] if n else [], {"threshold": None, "silhouette": None, "coverage": 0.0, "stability": 0.0}
    values = sorted({matrix[i][j] for i in range(n) for j in range(i + 1, n)})
    candidates = sorted(set(values[::max(1, len(values) // 18)] + [0.35, 0.45, 0.55, 0.65, 0.75, 0.85]))
    best: tuple[float, list[list[int]], dict[str, Any]] | None = None
    for threshold in candidates:
        clusters = complete_linkage(matrix, threshold)
        useful = [cluster for cluster in clusters if len(cluster) >= 2]
        coverage = sum(len(cluster) for cluster in useful) / n
        sil = silhouette(matrix, useful)
        stability = 0.0
        if sil < -0.5 or coverage == 0:
            score = -1.0
        else:
            # Margin stability rewards clusters whose weakest pair is above the cut.
            margins = [min(matrix[a][b] for a in cluster for b in cluster if a != b) - threshold for cluster in useful]
            stability = sum(max(0.0, min(1.0, 1.0 + margin)) for margin in margins) / max(len(margins), 1)
            # Coverage is squared so a tiny, very pure pair does not beat a
            # broader but still separated behavioural partition.
            score = max(0.0, sil) * (coverage ** 2) * stability
        metadata = {"threshold": round(threshold, 8), "silhouette": round(sil, 8), "coverage": round(coverage, 8), "stability": round(stability if sil >= -0.5 and coverage else 0.0, 8), "selection_score": round(max(0.0, score), 8)}
        candidate = (score, useful, metadata)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return [], {"threshold": None, "silhouette": None, "coverage": 0.0, "stability": 0.0}
    return best[1], best[2]


def split_pressure(slice_count: int, ideal_groups: int, sharpness: float = 4.0) -> dict[str, float]:
    """Return the continuous pressure used by the split experiments.

    ``raw_ratio`` is intentionally kept as an auditable quantity.  It is not
    interpreted as the output cluster count.  ``effective_pressure`` is a
    smooth, sub-linear transform so that large domains receive more incentive
    to split without making the requested group count a hard constraint.
    """
    count = max(0, int(slice_count))
    reference = max(1, int(ideal_groups))
    exponent = max(0.5, float(sharpness))
    raw_ratio = count / reference
    effective = math.log1p(raw_ratio ** exponent) / exponent if raw_ratio else 0.0
    return {
        "slice_count": float(count),
        "ideal_groups": float(reference),
        "raw_ratio": round(raw_ratio, 8),
        "sharpness": round(exponent, 8),
        "effective_pressure": round(effective, 8),
    }


def _overflow_penalty(groups: list[list[int]], capacity: float) -> float:
    if not groups:
        return 0.0
    capacity = max(float(capacity), 1.0)
    return sum(max(0.0, len(group) / capacity - 1.0) ** 2 for group in groups) / len(groups)


def _pair_retention(matrix: list[list[float]], groups: list[list[int]], quantile_rate: float = 0.90) -> tuple[float, int, float]:
    values = [matrix[i][j] for i in range(len(matrix)) for j in range(i + 1, len(matrix))]
    if not values:
        return 1.0, 0, 0.0
    cut = quantile(values, quantile_rate)
    high_pairs = [(i, j) for i in range(len(matrix)) for j in range(i + 1, len(matrix)) if matrix[i][j] >= cut]
    memberships: dict[int, set[int]] = defaultdict(set)
    for group_id, group in enumerate(groups):
        for index in group:
            memberships[index].add(group_id)
    retained = sum(1 for left, right in high_pairs if memberships[left] & memberships[right])
    return retained / max(len(high_pairs), 1), len(high_pairs), cut


def _reverse_compaction_score(groups: list[list[int]], reverse_groups: list[list[int]] | None) -> float:
    """Measure how much reverse diversity packets stay visible in forward groups.

    A reverse packet is deliberately diverse.  Splitting it over many forward
    groups makes it harder for a downstream model to see that diversity in one
    context.  The score is a small regularizer, never a replacement for
    positive similarity.
    """
    if not groups or not reverse_groups:
        return 0.0
    memberships: dict[int, set[int]] = defaultdict(set)
    for group_id, group in enumerate(groups):
        for index in group:
            memberships[index].add(group_id)
    denominator = max(len(groups) - 1, 1)
    values: list[float] = []
    for packet in reverse_groups:
        represented = set()
        for index in packet:
            represented.update(memberships.get(index, set()))
        fragmentation = max(0.0, (len(represented) - 1) / denominator)
        values.append(max(0.0, 1.0 - fragmentation))
    return sum(values) / max(len(values), 1)


def _materialize_forward_cover(
    matrix: list[list[float]],
    base_groups: list[list[int]],
    overlap_margin: float = 0.0,
) -> list[list[int]]:
    """Cover every slice and optionally retain close secondary memberships."""
    n = len(matrix)
    groups = [sorted(set(group)) for group in base_groups if group]
    if not groups and n:
        groups = [[index] for index in range(n)]
    assigned = {index for group in groups for index in group}
    for index in range(n):
        if index in assigned:
            continue
        scores = [sum(matrix[index][member] for member in group) / len(group) for group in groups]
        target = max(range(len(groups)), key=lambda group_id: (scores[group_id], -len(groups[group_id]), -group_id))
        groups[target].append(index)
    if overlap_margin > 0.0 and len(groups) > 1:
        for index in range(n):
            scores = sorted(
                ((sum(matrix[index][member] for member in group) / len(group), group_id) for group_id, group in enumerate(groups)),
                reverse=True,
            )
            if not scores or scores[0][0] <= 0.0:
                continue
            best_score = scores[0][0]
            for score, group_id in scores[1:]:
                if best_score - score <= overlap_margin and index not in groups[group_id]:
                    groups[group_id].append(index)
    return sorted((sorted(set(group)) for group in groups), key=lambda group: (min(group), len(group)))


def choose_forward_groups(
    matrix: list[list[float]],
    ideal_groups: int,
    sharpness: float = 4.0,
    load_weight: float = 0.12,
    overlap_margin: float = 0.0,
    reverse_groups: list[list[int]] | None = None,
    reverse_strategy_weight: float = 0.01,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Select a forward cover by balancing pair retention and load pressure.

    Candidate cuts are data-derived.  The reference group count only controls
    the smooth load pressure and the corresponding reference capacity; it is
    never used as a hard cluster-count target.
    """
    n = len(matrix)
    if n == 0:
        return [], {"mode": "forward", "group_count": 0}
    pressure = split_pressure(n, ideal_groups, sharpness)
    capacity = n / max(1, ideal_groups)
    values = [matrix[i][j] for i in range(n) for j in range(i + 1, n)]
    if not values:
        groups = [[0]]
        return groups, {"mode": "forward", "group_count": 1, "pressure": pressure, "reference_capacity": capacity}
    quantile_cuts = [quantile(values, rate) for rate in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95)]
    candidates = sorted(set([0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95] + quantile_cuts + values[::max(1, len(values) // 24)]))
    best: tuple[float, list[list[int]], dict[str, Any]] | None = None
    for threshold in candidates:
        base = complete_linkage(matrix, threshold)
        groups = _materialize_forward_cover(matrix, base, overlap_margin)
        retention, high_pair_count, high_cut = _pair_retention(matrix, groups)
        reverse_compaction = _reverse_compaction_score(groups, reverse_groups)
        overflow = _overflow_penalty(groups, capacity)
        group_ratio = len(groups) / max(1, ideal_groups)
        excess_group_penalty = max(0.0, group_ratio - 1.0) ** 2
        duplicate_rate = max(0, sum(len(group) for group in groups) - n) / max(n, 1)
        score = (
            retention
            + reverse_strategy_weight * reverse_compaction
            - load_weight * pressure["effective_pressure"] * overflow
            - 0.08 * excess_group_penalty
            - 0.05 * duplicate_rate
        )
        metadata = {
            "mode": "forward",
            "threshold": round(threshold, 8),
            "group_count": len(groups),
            "coverage": round(len({index for group in groups for index in group}) / max(n, 1), 8),
            "pair_retention": round(retention, 8),
            "reverse_compaction_score": round(reverse_compaction, 8),
            "high_pair_count": high_pair_count,
            "high_pair_cut": round(high_cut, 8),
            "overflow_penalty": round(overflow, 8),
            "duplicate_rate": round(duplicate_rate, 8),
            "selection_score": round(score, 8),
            "load_weight": load_weight,
            "reverse_strategy_weight": reverse_strategy_weight,
            "pressure": pressure,
            "reference_capacity": round(capacity, 8),
        }
        candidate = (score, groups, metadata)
        if best is None or candidate[0] > best[0]:
            best = candidate
    assert best is not None
    return best[1], best[2]


def choose_reverse_groups(
    matrix: list[list[float]],
    ideal_groups: int,
    sharpness: float = 4.0,
    load_weight: float = 0.12,
    fragmentation_weight: float = 0.15,
) -> tuple[list[list[int]], dict[str, Any]]:
    """Select an independent reverse (diversity/anti) partition.

    The reverse experiment deliberately rewards dissimilar members within a
    packet.  It is not a post-processing step over the forward result.
    """
    n = len(matrix)
    if n == 0:
        return [], {"mode": "reverse", "group_count": 0}
    pressure = split_pressure(n, ideal_groups, sharpness)
    capacity = n / max(1, ideal_groups)
    candidate_counts = sorted(set(max(1, min(n, count)) for count in [1, 2, ideal_groups - 1, ideal_groups, ideal_groups + 1, ideal_groups * 2, ideal_groups * 3]))
    best: tuple[float, list[list[int]], dict[str, Any]] | None = None
    for group_count in candidate_counts:
        groups = anti_partition(matrix, group_count)
        if not groups:
            continue
        mean_distance = sum(1.0 - matrix[left][right] for group in groups for offset, left in enumerate(group) for right in group[offset + 1:]) / max(sum(len(group) * (len(group) - 1) / 2 for group in groups), 1)
        overflow = _overflow_penalty(groups, capacity)
        balance = sum(abs(len(group) - capacity) for group in groups) / max(n, 1)
        group_ratio = len(groups) / max(1, ideal_groups)
        fragmentation = max(0.0, group_ratio - 1.0) ** 2
        score = mean_distance - load_weight * pressure["effective_pressure"] * overflow - 0.04 * balance - fragmentation_weight * fragmentation
        metadata = {
            "mode": "reverse",
            "group_count": len(groups),
            "candidate_group_count": group_count,
            "coverage": round(len({index for group in groups for index in group}) / max(n, 1), 8),
            "mean_within_dissimilarity": round(mean_distance, 8),
            "overflow_penalty": round(overflow, 8),
            "balance_penalty": round(balance, 8),
            "fragmentation_penalty": round(fragmentation, 8),
            "selection_score": round(score, 8),
            "load_weight": load_weight,
            "fragmentation_weight": fragmentation_weight,
            "pressure": pressure,
            "reference_capacity": round(capacity, 8),
        }
        candidate = (score, groups, metadata)
        if best is None or candidate[0] > best[0]:
            best = candidate
    assert best is not None
    return best[1], best[2]


def _cluster_evidence_tokens(feature: dict[str, Any], view: str) -> set[str]:
    if view == "target":
        tokens = set(feature.get("target_evidence", {})) | set(feature.get("problem_evidence", {}))
    else:
        tokens = set(feature.get("resolution_evidence", {})) | set(feature.get("verification_evidence", {}))
    # Tool names, file types, and operation symbols remain available in the
    # vectors and sequence prototype.  They do not count as independent
    # problem-solving evidence because they describe the mechanics shared by
    # almost every coding Session.
    return {
        token for token in tokens
        if not token.startswith(("op:", "tool:", "filetype:")) and not token.startswith("_")
    }


def _rank_feature_evidence(feature: dict[str, Any], view: str, limit: int = 40) -> list[str]:
    if view == "target":
        vectors = [feature.get("target_vector", {}), feature.get("problem_vector", {})]
    else:
        vectors = [feature.get("resolution_vector", {}), feature.get("verification_vector", {})]
    values: Counter[str] = Counter()
    for vector in vectors:
        values.update(vector)
    allowed = _cluster_evidence_tokens(feature, view)
    return [token for token, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]) if item[0] in allowed else (1.0, item[0])) if token in allowed][:limit]


def _cluster_core(
    features: list[dict[str, Any]],
    matrix: list[list[float]],
    cluster: list[int],
    view: str,
    limit: int = 5,
) -> tuple[list[int], dict[str, Any]]:
    """Select an auditable cross-Session core without semantic labels.

    A core member must share at least one automatically-derived evidence token
    with another Session when such evidence exists.  If a cluster has no such
    pair, its central members are retained as satellites and the result is
    explicitly marked as routing-only.
    """
    if not cluster:
        return [], {"unique_session_count": 0, "cross_session_pair_count": 0, "core_session_count": 0, "core_status": "empty"}
    session_ids = {features[index].get("session_id", features[index]["slice_id"]) for index in cluster}
    support_sessions: dict[int, set[str]] = {index: set() for index in cluster}
    cross_pairs = 0
    for offset, left in enumerate(cluster):
        left_tokens = _cluster_evidence_tokens(features[left], view)
        for right in cluster[offset + 1:]:
            if features[left].get("session_id") == features[right].get("session_id"):
                continue
            shared = left_tokens & _cluster_evidence_tokens(features[right], view)
            if not shared:
                continue
            cross_pairs += 1
            support_sessions[left].add(features[right].get("session_id", features[right]["slice_id"]))
            support_sessions[right].add(features[left].get("session_id", features[left]["slice_id"]))

    centrality = {
        index: sum(matrix[index][other] for other in cluster if other != index) / max(len(cluster) - 1, 1)
        for index in cluster
    }
    ranked = sorted(
        cluster,
        key=lambda index: (-len(support_sessions[index]), -centrality[index], features[index]["slice_id"]),
    )
    core: list[int] = []
    core_sessions: set[str] = set()
    # Prefer one representative per independently supported Session before
    # filling the remaining core slots with the strongest evidence.
    for index in ranked:
        session_id = features[index].get("session_id", features[index]["slice_id"])
        if support_sessions[index] and session_id not in core_sessions:
            core.append(index)
            core_sessions.add(session_id)
        if len(core) >= min(limit, len(cluster)):
            break
    for index in ranked:
        if len(core) >= min(limit, len(cluster)):
            break
        if index not in core:
            core.append(index)
            core_sessions.add(features[index].get("session_id", features[index]["slice_id"]))

    status = "cross_session_core" if cross_pairs and len(core_sessions) >= 2 else "routing_only"
    return core, {
        "unique_session_count": len(session_ids),
        "cross_session_pair_count": cross_pairs,
        "core_session_count": len(core_sessions),
        "core_status": status,
        "member_session_ids": sorted(session_ids),
    }


def cluster_payload(features: list[dict[str, Any]], matrix: list[list[float]], clusters: list[list[int]], view: str, metadata: dict[str, Any]) -> dict[str, Any]:
    output = []
    assigned: set[int] = set()
    for number, cluster in enumerate(clusters, start=1):
        assigned.update(cluster)
        evidence = Counter()
        evidence_score = Counter()
        evidence_sessions: dict[str, set[str]] = defaultdict(set)
        operation_evidence = Counter()
        operation_sessions: dict[str, set[str]] = defaultdict(set)
        for index in cluster:
            values = _cluster_evidence_tokens(features[index], view)
            evidence.update(values)
            if view == "target":
                value_vectors = (features[index].get("target_vector", {}), features[index].get("problem_vector", {}))
            else:
                value_vectors = (features[index].get("resolution_vector", {}), features[index].get("verification_vector", {}))
            for vector in value_vectors:
                for token, value in vector.items():
                    if token in values:
                        evidence_score[token] += value
            session_id = features[index].get("session_id", features[index]["slice_id"])
            for token in values:
                evidence_sessions[token].add(session_id)
            raw_values = set(features[index].get("logic_evidence", {}))
            for token in raw_values:
                if token.startswith(("op:", "tool:", "filetype:")):
                    operation_evidence[token] += 1
                    operation_sessions[token].add(session_id)
        representative = sorted(cluster, key=lambda index: (-sum(matrix[index][other] for other in cluster) / max(len(cluster) - 1, 1), features[index]["slice_id"]))[:5]
        prototype_index = representative[0] if representative else cluster[0]
        prototype_sequence = features[prototype_index]["sequence"][:60] if view == "logic" else []
        core, core_meta = _cluster_core(features, matrix, cluster, view)
        core_ids = {features[index]["slice_id"] for index in core}
        token_candidates = [token for token in evidence if len(evidence_sessions[token]) >= 2]
        display_tokens = token_candidates or list(evidence)
        prototype_tokens = [
            {
                "token": token,
                "support": len(evidence_sessions[token]),
                "session_support": len(evidence_sessions[token]),
                "slice_support": evidence[token],
                "weight": round(evidence_score[token], 8),
            }
            for token in sorted(display_tokens, key=lambda item: (-len(evidence_sessions[item]), -evidence_score[item], item))[:20]
        ]
        prototype_operations = [
            {
                "token": token,
                "session_support": len(operation_sessions[token]),
                "slice_support": operation_evidence[token],
            }
            for token in sorted(operation_evidence, key=lambda item: (-len(operation_sessions[item]), -operation_evidence[item], item))[:20]
        ]
        output.append({
            "cluster_id": f"{view}-{number:02d}",
            "view": view,
            "member_slice_ids": [features[index]["slice_id"] for index in cluster],
            "size": len(cluster),
            "member_session_ids": core_meta["member_session_ids"],
            "unique_session_count": core_meta["unique_session_count"],
            "core_slice_ids": [features[index]["slice_id"] for index in core],
            "satellite_slice_ids": [features[index]["slice_id"] for index in cluster if features[index]["slice_id"] not in core_ids],
            "core_session_count": core_meta["core_session_count"],
            "core_status": core_meta["core_status"],
            "cross_session_pair_count": core_meta["cross_session_pair_count"],
            "prototype_tokens": prototype_tokens,
            "rare_member_tokens": [
                {"token": token, "session_support": len(evidence_sessions[token]), "slice_support": evidence[token]}
                for token in sorted(evidence, key=lambda item: (-evidence_score[item], item))[:20]
                if token not in display_tokens
            ],
            "prototype_operations": prototype_operations,
            "prototype_sequence": [{"sequence": " → ".join(prototype_sequence), "support": 1, "source_slice_id": features[prototype_index]["slice_id"]}],
            "representative_slice_ids": [features[index]["slice_id"] for index in representative],
            "evidence": [{"slice_id": features[index]["slice_id"], "first_user_text": features[index]["first_user_text"], "top_evidence": _rank_feature_evidence(features[index], view)} for index in representative],
        })
    residual = [features[index]["slice_id"] for index in range(len(features)) if index not in assigned]
    return {"view": view, "clusters": output, "residual_slice_ids": residual, "selection": metadata}


def quantile(values: list[float], rate: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(math.floor((len(values) - 1) * rate))))]


def negative_products(features: list[dict[str, Any]], target_matrix: list[list[float]], logic_matrix: list[list[float]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    values_target = [target_matrix[i][j] for i in range(len(features)) for j in range(i + 1, len(features))]
    values_logic = [logic_matrix[i][j] for i in range(len(features)) for j in range(i + 1, len(features))]
    target_cut = quantile(values_target, 0.10)
    logic_cut = quantile(values_logic, 0.10)
    edges: list[dict[str, Any]] = []
    blocked: set[tuple[int, int]] = set()
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            shared = set(features[i]["operation_ngrams"]) & set(features[j]["operation_ngrams"])
            if target_matrix[i][j] <= target_cut and logic_matrix[i][j] <= logic_cut and not shared:
                blocked.add((i, j))
                edges.append({
                    "left_slice_id": features[i]["slice_id"],
                    "right_slice_id": features[j]["slice_id"],
                    "target_similarity": target_matrix[i][j],
                    "logic_similarity": logic_matrix[i][j],
                    "reason": ["low_target_similarity", "low_logic_similarity", "disjoint_operation_ngrams"],
                })
    # Deterministic greedy maximal compatible groups.  These are covers, not
    # claims that members are semantically equivalent.
    degrees = Counter(index for edge in blocked for index in edge)
    groups: list[list[int]] = []
    for seed in sorted(range(len(features)), key=lambda index: (degrees[index], features[index]["slice_id"])):
        group = [seed]
        for candidate in sorted(range(len(features)), key=lambda index: (-logic_matrix[seed][index] - target_matrix[seed][index], features[index]["slice_id"])):
            if candidate in group:
                continue
            if all(tuple(sorted((candidate, member))) not in blocked for member in group):
                group.append(candidate)
        if len(group) >= 2:
            key = tuple(sorted(group))
            if not any(key == tuple(sorted(existing)) for existing in groups):
                groups.append(group)
    groups_payload = [{"group_id": f"compatible-{index:02d}", "member_slice_ids": [features[item]["slice_id"] for item in group], "size": len(group), "meaning": "no emitted cannot-link edge exists inside this group"} for index, group in enumerate(groups, start=1)]
    return edges, groups_payload, {"target_cut_p10": round(target_cut, 8), "logic_cut_p10": round(logic_cut, 8), "cannot_link_count": len(edges), "compatible_group_count": len(groups_payload)}


def reverse_cannot_link_edges(features: list[dict[str, Any]], matrix: list[list[float]], view: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the reverse experiment's evidence: only reliable low-similarity pairs.

    The reverse experiment does not ask which items are similar.  It asks which
    pairs have enough evidence that they must not share a group.  A p10 cut is
    computed independently for each domain and view, so no semantic threshold
    or domain vocabulary is hard-coded.  Logic pairs additionally need
    disjoint operation n-grams: a low text score alone is not enough to call two
    execution traces incompatible when they still share an ordered operation.
    """
    values = [matrix[i][j] for i in range(len(features)) for j in range(i + 1, len(features))]
    cut = quantile(values, 0.10)
    edges: list[dict[str, Any]] = []
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            similarity = matrix[i][j]
            if similarity > cut:
                continue
            reason = [f"low_{view}_similarity"]
            if view == "logic":
                shared = set(features[i]["operation_ngrams"]) & set(features[j]["operation_ngrams"])
                if shared:
                    continue
                reason.append("disjoint_operation_ngrams")
            edges.append({
                "left_slice_id": features[i]["slice_id"],
                "right_slice_id": features[j]["slice_id"],
                "similarity": round(similarity, 8),
                "reason": reason,
            })
    return edges, {
        "view": view,
        "cut_p10": round(cut, 8),
        "cannot_link_count": len(edges),
        "pair_count": len(values),
        "edge_rate": round(len(edges) / max(len(values), 1), 8),
    }


def reverse_partition(features: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[int]]:
    """Color the cannot-link graph into full, non-overlapping compatibility groups.

    Every trajectory is assigned exactly once and no output group contains an
    emitted cannot-link edge.  DSATUR-style greedy coloring keeps the number of
    groups small without pretending that members are positively similar.  This
    is the key difference from complete-linkage: the reverse result is a
    coverage-preserving partition under explicit incompatibility constraints.
    """
    sid_to_index = {feature["slice_id"]: index for index, feature in enumerate(features)}
    adjacency: list[set[int]] = [set() for _ in features]
    for edge in edges:
        left = sid_to_index.get(edge["left_slice_id"])
        right = sid_to_index.get(edge["right_slice_id"])
        if left is None or right is None or left == right:
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)
    colors = [-1] * len(features)
    remaining = set(range(len(features)))
    while remaining:
        def key(index: int) -> tuple[int, int, str]:
            saturation = len({colors[neighbor] for neighbor in adjacency[index] if colors[neighbor] >= 0})
            return saturation, len(adjacency[index]), features[index]["slice_id"]
        current = max(remaining, key=key)
        forbidden = {colors[neighbor] for neighbor in adjacency[current] if colors[neighbor] >= 0}
        color = 0
        while color in forbidden:
            color += 1
        colors[current] = color
        remaining.remove(current)
    groups: dict[int, list[int]] = defaultdict(list)
    for index, color in enumerate(colors):
        groups[color].append(index)
    # Stable IDs make repeated runs auditable even if the greedy coloring uses
    # a different color number after a future implementation change.
    return sorted((sorted(group) for group in groups.values()), key=lambda group: (features[group[0]]["slice_id"], len(group)))


def anti_partition(matrix: list[list[float]], group_count: int) -> list[list[int]]:
    """Partition all rows into diverse bundles using dissimilarity as affinity.

    This is the requested reverse experiment: unlike a compatibility partition,
    a bundle is deliberately seeded with far-apart trajectories.  The number of
    bundles comes from the cannot-link graph coloring count, while a minimum of
    two bundles keeps a domain with no emitted negative edge from collapsing to
    one opaque packet.  Capacity balancing prevents one packet from absorbing
    the whole domain and preserves complete coverage.
    """
    n = len(matrix)
    if n == 0:
        return []
    group_count = max(1, min(group_count, n))
    if n > 1:
        group_count = max(2, group_count)

    def distance(left: int, right: int) -> float:
        return 1.0 - matrix[left][right]

    mean_distance = [sum(distance(index, other) for other in range(n) if other != index) / max(n - 1, 1) for index in range(n)]
    seeds = [min(range(n), key=lambda index: (-mean_distance[index], index))]
    while len(seeds) < group_count:
        remaining = [index for index in range(n) if index not in seeds]
        seed = max(remaining, key=lambda index: (min(distance(index, chosen) for chosen in seeds), mean_distance[index], -index))
        seeds.append(seed)
    groups: list[list[int]] = [[seed] for seed in seeds]
    capacity = math.ceil(n / group_count)
    remaining = [index for index in range(n) if index not in seeds]
    remaining.sort(key=lambda index: (-min(distance(index, seed) for seed in seeds), index))
    for index in remaining:
        available = [group for group in range(group_count) if len(groups[group]) < capacity] or list(range(group_count))
        group = max(
            available,
            key=lambda candidate: (
                sum(distance(index, member) for member in groups[candidate]) / len(groups[candidate]),
                -len(groups[candidate]),
                -candidate,
            ),
        )
        groups[group].append(index)

    def bundle_score(bundle: list[int]) -> float:
        return sum(distance(left, right) for offset, left in enumerate(bundle) for right in bundle[offset + 1:])

    # Greedy assignment is deterministic but can make an early choice that
    # leaves two similar points paired together.  A small deterministic swap
    # pass fixes such local inversions while preserving balanced capacities.
    for _ in range(n):
        best: tuple[float, int, int, int, int] | None = None
        for left_group in range(group_count):
            for right_group in range(left_group + 1, group_count):
                left_bundle, right_bundle = groups[left_group], groups[right_group]
                for left_offset, left in enumerate(left_bundle):
                    for right_offset, right in enumerate(right_bundle):
                        old = bundle_score(left_bundle) + bundle_score(right_bundle)
                        swapped_left = left_bundle.copy()
                        swapped_right = right_bundle.copy()
                        swapped_left[left_offset], swapped_right[right_offset] = right, left
                        gain = bundle_score(swapped_left) + bundle_score(swapped_right) - old
                        candidate = (gain, left_group, right_group, left, right)
                        if gain > 1e-12 and (best is None or candidate > best):
                            best = candidate
        if best is None:
            break
        _, left_group, right_group, left, right = best
        left_offset = groups[left_group].index(left)
        right_offset = groups[right_group].index(right)
        groups[left_group][left_offset], groups[right_group][right_offset] = right, left
    return sorted((sorted(group) for group in groups), key=lambda group: (min(group), len(group)))


def reverse_cluster_payload(features: list[dict[str, Any]], matrix: list[list[float]], clusters: list[list[int]], view: str, metadata: dict[str, Any]) -> dict[str, Any]:
    output = []
    mode = metadata.get("mode", "reverse")
    for number, cluster in enumerate(clusters, start=1):
        evidence = Counter()
        for index in cluster:
            evidence.update(features[index]["target_evidence"] if view == "target" else features[index]["logic_evidence"])
        representative = sorted(
            cluster,
            key=lambda index: (sum(matrix[index][other] for other in cluster if other != index) / max(len(cluster) - 1, 1), features[index]["slice_id"]),
        )[:5]
        prototype_index = representative[0] if representative else cluster[0]
        prototype_sequence = features[prototype_index]["sequence"][:60] if view == "logic" else []
        output.append({
            "cluster_id": f"{view}-reverse-{number:02d}",
            "view": view,
            "mode": mode,
            "member_slice_ids": [features[index]["slice_id"] for index in cluster],
            "size": len(cluster),
            "prototype_tokens": [{"token": token, "support": count} for token, count in evidence.most_common(30)],
            "prototype_sequence": [{"sequence": " → ".join(prototype_sequence), "support": 1, "source_slice_id": features[prototype_index]["slice_id"]}],
            "representative_slice_ids": [features[index]["slice_id"] for index in representative],
            "evidence": [{"slice_id": features[index]["slice_id"], "first_user_text": features[index]["first_user_text"], "top_evidence": (features[index]["target_evidence"] if view == "target" else features[index]["logic_evidence"])} for index in representative],
            "mean_within_similarity": round(sum(matrix[left][right] for offset, left in enumerate(cluster) for right in cluster[offset + 1:]) / max(len(cluster) * (len(cluster) - 1) / 2, 1), 8),
        })
    return {"view": view, "mode": mode, "clusters": output, "residual_slice_ids": [], "selection": metadata}


def render_report(domain_id: str, features: list[dict[str, Any]], target: dict[str, Any], logic: dict[str, Any], negative_meta: dict[str, Any]) -> str:
    lines = [f"# {domain_id} behavior clustering", "", f"Slices: {len(features)}", "", "## Target clusters", "", f"Clusters: {len(target['clusters'])}; residual: {len(target['residual_slice_ids'])}", ""]
    for cluster in target["clusters"]:
        tokens = ", ".join(item["token"] for item in cluster["prototype_tokens"][:10]) or "—"
        lines.append(f"- `{cluster['cluster_id']}` ({cluster['size']}, sessions={cluster.get('unique_session_count', 0)}, core={cluster.get('core_status', 'unknown')}): {tokens}")
    lines.extend(["", "## Logic clusters", "", f"Clusters: {len(logic['clusters'])}; residual: {len(logic['residual_slice_ids'])}", ""])
    for cluster in logic["clusters"]:
        sequence = cluster["prototype_sequence"][0]["sequence"] if cluster["prototype_sequence"] else "—"
        lines.append(f"- `{cluster['cluster_id']}` ({cluster['size']}, sessions={cluster.get('unique_session_count', 0)}, core={cluster.get('core_status', 'unknown')}): {sequence}")
    lines.extend(["", "## Cannot-link", "", f"Target p10: {negative_meta['target_cut_p10']}; logic p10: {negative_meta['logic_cut_p10']}; edges: {negative_meta['cannot_link_count']}", ""])
    return "\n".join(lines) + "\n"


def run(
    slices_dir: Path,
    domains_path: Path,
    feature_cards_path: Path | None,
    output: Path,
    ideal_groups: int = 4,
    pressure_sharpness: float = 4.0,
    load_weight: float = 0.12,
    overlap_margin: float = 0.0,
    fragmentation_weight: float = 0.15,
    reverse_strategy_weight: float = 0.01,
) -> dict[str, Any]:
    """Run the two independent experiments over all configured domains."""
    slices = load_slices(slices_dir)
    domains = load_domains(domains_path)
    cards = load_cards(feature_cards_path)
    global_sets, _ = all_token_sets(list(slices.values()))
    global_df, global_n = document_stats(global_sets)
    output.mkdir(parents=True, exist_ok=True)
    shared_out = output / "shared"
    forward_out = output / "forward"
    reverse_out = output / "reverse"
    all_representations: list[dict[str, Any]] = []
    cross_index: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []

    for domain in domains:
        did = domain["domain_id"]
        members = [slices[sid] for sid in domain["members"] if sid in slices]
        if not members:
            continue
        anchors = derive_anchors(domain, cards.get(did))
        features, feature_config = build_domain_features(members, anchors, global_df, global_n)
        target_matrix = pairwise(features, "target")
        logic_matrix = pairwise(features, "logic")

        reverse_target_groups, reverse_target_meta = choose_reverse_groups(
            target_matrix, ideal_groups, pressure_sharpness, load_weight, fragmentation_weight
        )
        reverse_logic_groups, reverse_logic_meta = choose_reverse_groups(
            logic_matrix, ideal_groups, pressure_sharpness, load_weight, fragmentation_weight
        )
        forward_target_groups, forward_target_meta = choose_forward_groups(
            target_matrix,
            ideal_groups,
            pressure_sharpness,
            load_weight,
            overlap_margin,
            reverse_target_groups,
            reverse_strategy_weight,
        )
        forward_logic_groups, forward_logic_meta = choose_forward_groups(
            logic_matrix,
            ideal_groups,
            pressure_sharpness,
            load_weight,
            overlap_margin,
            reverse_logic_groups,
            reverse_strategy_weight,
        )

        forward_target = cluster_payload(features, target_matrix, forward_target_groups, "target", forward_target_meta)
        forward_logic = cluster_payload(features, logic_matrix, forward_logic_groups, "logic", forward_logic_meta)
        reverse_target = reverse_cluster_payload(features, target_matrix, reverse_target_groups, "target", reverse_target_meta)
        reverse_logic = reverse_cluster_payload(features, logic_matrix, reverse_logic_groups, "logic", reverse_logic_meta)

        target_edges, target_edge_meta = reverse_cannot_link_edges(features, target_matrix, "target")
        logic_edges, logic_edge_meta = reverse_cannot_link_edges(features, logic_matrix, "logic")

        shared_domain = shared_out / did
        forward_domain = forward_out / did
        reverse_domain = reverse_out / did
        write_json(shared_domain / "feature-config.json", feature_config)
        shared_domain.joinpath("representations.jsonl").write_text(
            "".join(
                json.dumps(
                    {key: value for key, value in row.items() if key not in {"target_vector", "logic_text_vector", "logic_order_vector"}},
                    ensure_ascii=False,
                )
                + "\n"
                for row in features
            ),
            encoding="utf-8",
        )
        shared_domain.joinpath("target-similarity.json").write_text(json.dumps(target_matrix, ensure_ascii=False), encoding="utf-8")
        shared_domain.joinpath("logic-similarity.json").write_text(json.dumps(logic_matrix, ensure_ascii=False), encoding="utf-8")

        write_json(forward_domain / "target-clusters.json", forward_target)
        write_json(forward_domain / "logic-clusters.json", forward_logic)
        forward_domain.joinpath("report.md").write_text(
            render_report(did, features, forward_target, forward_logic, {
                "target_cut_p10": target_edge_meta["cut_p10"],
                "logic_cut_p10": logic_edge_meta["cut_p10"],
                "cannot_link_count": target_edge_meta["cannot_link_count"] + logic_edge_meta["cannot_link_count"],
            })
            + "\nThis directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.\n",
            encoding="utf-8",
        )

        write_json(reverse_domain / "target-clusters.json", reverse_target)
        write_json(reverse_domain / "logic-clusters.json", reverse_logic)
        reverse_domain.joinpath("target-cannot-link.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in target_edges),
            encoding="utf-8",
        )
        reverse_domain.joinpath("logic-cannot-link.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in logic_edges),
            encoding="utf-8",
        )
        reverse_domain.joinpath("report.md").write_text(
            f"# {did} reverse behavior grouping\n\n"
            f"Slices: {len(features)}\n\n"
            "This directory is an independent reverse experiment. It deliberately rewards dissimilar members within each packet; it is not a post-processing step over the forward result.\n\n"
            f"- Target groups: {len(reverse_target['clusters'])}; mean within dissimilarity: {reverse_target_meta['mean_within_dissimilarity']}\n"
            f"- Logic groups: {len(reverse_logic['clusters'])}; mean within dissimilarity: {reverse_logic_meta['mean_within_dissimilarity']}\n"
            f"- Target p10 cannot-link evidence: {target_edge_meta['cannot_link_count']} pairs\n"
            f"- Logic p10 cannot-link evidence: {logic_edge_meta['cannot_link_count']} pairs\n",
            encoding="utf-8",
        )

        for feature in features:
            all_representations.append({
                "domain_id": did,
                "slice_id": feature["slice_id"],
                "session_id": feature["session_id"],
                "sequence": feature["sequence"],
                "phase_sequence": feature["phase_sequence"],
                "operations": feature["operations"],
                "event_counts": feature["event_counts"],
                "first_user_text": feature["first_user_text"],
                "target_evidence": sorted(feature["target_evidence"]),
                "problem_evidence": sorted(feature["problem_evidence"]),
                "resolution_evidence": sorted(feature["resolution_evidence"]),
                "verification_evidence": sorted(feature["verification_evidence"]),
            })
            item = cross_index.setdefault(
                feature["slice_id"],
                {
                    "slice_id": feature["slice_id"],
                    "session_id": feature["session_id"],
                    "domain_ids": [],
                    "forward_target_cluster_ids": [],
                    "forward_logic_cluster_ids": [],
                    "forward_target_core_cluster_ids": [],
                    "forward_logic_core_cluster_ids": [],
                    "reverse_target_cluster_ids": [],
                    "reverse_logic_cluster_ids": [],
                },
            )
            item["domain_ids"].append(did)

        for cluster in forward_target["clusters"]:
            for sid in cluster["member_slice_ids"]:
                cross_index[sid]["forward_target_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")
        for cluster in forward_logic["clusters"]:
            for sid in cluster["member_slice_ids"]:
                cross_index[sid]["forward_logic_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")
            for sid in cluster["core_slice_ids"]:
                cross_index[sid]["forward_logic_core_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")
        for cluster in forward_target["clusters"]:
            for sid in cluster["core_slice_ids"]:
                cross_index[sid]["forward_target_core_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")
        for cluster in reverse_target["clusters"]:
            for sid in cluster["member_slice_ids"]:
                cross_index[sid]["reverse_target_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")
        for cluster in reverse_logic["clusters"]:
            for sid in cluster["member_slice_ids"]:
                cross_index[sid]["reverse_logic_cluster_ids"].append(f"{did}:{cluster['cluster_id']}")

        summaries.append({
            "domain_id": did,
            "slice_count": len(features),
            "forward_target_cluster_count": len(forward_target["clusters"]),
            "forward_logic_cluster_count": len(forward_logic["clusters"]),
            "reverse_target_cluster_count": len(reverse_target["clusters"]),
            "reverse_logic_cluster_count": len(reverse_logic["clusters"]),
            "forward_target": forward_target_meta,
            "forward_logic": forward_logic_meta,
            "reverse_target": reverse_target_meta,
            "reverse_logic": reverse_logic_meta,
            "target_cannot_link_count": target_edge_meta["cannot_link_count"],
            "logic_cannot_link_count": logic_edge_meta["cannot_link_count"],
            "forward_target_cross_session_core_count": sum(cluster.get("core_status") == "cross_session_core" for cluster in forward_target["clusters"]),
            "forward_logic_cross_session_core_count": sum(cluster.get("core_status") == "cross_session_core" for cluster in forward_logic["clusters"]),
            "forward_target_routing_only_count": sum(cluster.get("core_status") == "routing_only" for cluster in forward_target["clusters"]),
            "forward_logic_routing_only_count": sum(cluster.get("core_status") == "routing_only" for cluster in forward_logic["clusters"]),
        })

    output.joinpath("slice-representations.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_representations),
        encoding="utf-8",
    )
    output.joinpath("cross-view-index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sorted(cross_index.values(), key=lambda row: row["slice_id"])),
        encoding="utf-8",
    )
    manifest = {
        "algorithm_version": "behavior-logic-clustering-v4-session-evidence",
        "inputs": {
            "slices_dir": str(slices_dir.resolve()),
            "domains": str(domains_path.resolve()),
            "feature_cards": str(feature_cards_path.resolve()) if feature_cards_path else None,
        },
        "experiments": {
            "forward": "high-similarity coverage with smooth load pressure, Session-aware evidence, and reverse-diversity compaction regularizer",
            "reverse_strategy": "independent dissimilarity/anti-clustering used as an internal forward regularizer",
            "reverse_strategy_is_primary_output": False,
        },
        "split_pressure": {
            "formula": "P(r)=log(1+r^k)/k",
            "raw_ratio": "slice_count / ideal_groups",
            "ideal_groups": ideal_groups,
            "sharpness": pressure_sharpness,
            "load_weight": load_weight,
            "overlap_margin": overlap_margin,
            "fragmentation_weight": fragmentation_weight,
            "reverse_strategy_weight": reverse_strategy_weight,
        },
        "event_policy": {
            "included": ["user_text", "assistant_text", "assistant_thinking", "assistant_reasoning", "tool_call:*"],
            "excluded": ["record:*", "tool_result", "user_image", "unknown"],
            "max_text_chars": MAX_TEXT_CHARS,
            "max_tool_text_chars": MAX_TOOL_TEXT_CHARS,
        },
        "weights": {
            "target": TARGET_WEIGHTS,
            "logic": LOGIC_WEIGHTS,
            "problem": PROBLEM_WEIGHTS,
            "resolution": RESOLUTION_WEIGHTS,
            "verification": VERIFICATION_WEIGHTS,
        },
        "session_evidence": {
            "same_session_affinity_multiplier": 0.95,
            "target_similarity_components": {"target": 0.80, "problem": 0.15, "cross_session_evidence": 0.05},
            "logic_similarity_components": {"order": 0.56, "lcs": 0.23, "text": 0.12, "resolution": 0.05, "verification": 0.03, "cross_session_evidence": 0.01},
            "cluster_core": "automatically derived shared evidence across distinct Session IDs; no domain vocabulary is hard-coded",
        },
        "domain_suppression_factor": 0.25,
        "blacklist": {"local_document_rate": 0.90, "global_document_rate": 0.35, "domain_anchors_exempt": True},
        "logic_similarity": {"order_ngram": 0.60, "lcs": 0.25, "text": 0.15},
        "domain_count": len(summaries),
        "source_slice_count": len(slices),
    }
    write_json(output / "manifest.json", manifest)
    summary = {
        "algorithm_version": manifest["algorithm_version"],
        "domain_count": len(summaries),
        "source_slice_count": len(slices),
        "domain_summaries": summaries,
        "representation_rows": len(all_representations),
        "cross_view_slice_count": len(cross_index),
    }
    write_json(output / "summary.json", summary)
    output.joinpath("README.md").write_text(
        "# 行为目标与执行逻辑聚类\n\n"
        "\x60forward/\x60 是最终正向结果：它最大化高相似轨迹的共同覆盖，并使用反向多样性包的压缩分数作为小权重正则。"
        "\x60reverse/\x60 保存该正则使用的反向策略证据，不是另一套需要单独交给 LLM 的主结果。"
        "两者共享事件投影、词项表示和相似度计算，但正向分组仍以相似性为主目标。\x60split_pressure\x60 只提供连续的规模压力，不指定最终簇数。"
        "词项和有序操作会按当前领域及独立 Session 的文档频率自动降权；每个正向簇还输出跨 Session 的 core 与 satellites。\n\n"
        "每个细领域都分别输出 target 和 logic 两个视图；\x60shared/\x60 保存可审计表示和相似度矩阵，"
        "\x60cross-view-index.jsonl\x60 保存轨迹在四类结果中的归属。\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--domains", type=Path, required=True)
    parser.add_argument("--feature-cards", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ideal-groups", type=int, default=4, help="Reference group count used only by split pressure.")
    parser.add_argument("--pressure-sharpness", type=float, default=4.0)
    parser.add_argument("--load-weight", type=float, default=0.12)
    parser.add_argument("--overlap-margin", type=float, default=0.0)
    parser.add_argument("--fragmentation-weight", type=float, default=0.15)
    parser.add_argument("--reverse-strategy-weight", type=float, default=0.01)
    args = parser.parse_args()
    print(json.dumps(
        run(
            args.slices_dir,
            args.domains,
            args.feature_cards,
            args.output,
            args.ideal_groups,
            args.pressure_sharpness,
            args.load_weight,
            args.overlap_margin,
            args.fragmentation_weight,
            args.reverse_strategy_weight,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
