"""Global multi-view Skill-space and capacity-aware routing experiment.

V5 deliberately keeps the V4 implementation untouched.  It builds one global
representation for unique slices, then derives per-domain routing packages and
overlapping Skill candidates from the same coordinates.  Only the Python
standard library is used so the experiment remains cheap and reproducible.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import re
from typing import Any

try:
    from behavior_logic_clustering import (
        _binary_cosine,
        choose_forward_groups,
        compact_text,
        compress_sequence,
        cosine,
        derive_anchors,
        l2_normalize,
        load_cards,
        load_domains,
        load_slices,
        lcs_similarity,
        quantile,
        rarity,
        read_json,
        safe_operation_token,
        session_id_for_slice,
        structural_noise,
        token_set,
        write_json,
    )
except ImportError:  # pragma: no cover - package import fallback
    from .behavior_logic_clustering import (
        _binary_cosine,
        choose_forward_groups,
        compact_text,
        compress_sequence,
        cosine,
        derive_anchors,
        l2_normalize,
        load_cards,
        load_domains,
        load_slices,
        lcs_similarity,
        quantile,
        rarity,
        read_json,
        safe_operation_token,
        session_id_for_slice,
        structural_noise,
        token_set,
        write_json,
    )


VIEWS = ("problem", "resolution", "verification", "order")
VIEW_WEIGHTS = {
    "problem": 1.00,
    "resolution": 0.90,
    "verification": 0.80,
    "order": 0.85,
}
CHANNEL_WEIGHTS = {
    "problem": {"user": 1.00, "assistant": 0.65, "thinking": 0.45, "tool": 0.15},
    "resolution": {"user": 0.15, "assistant": 0.80, "thinking": 0.45, "tool": 1.00},
    "verification": {"user": 0.05, "assistant": 0.55, "thinking": 0.35, "tool": 0.90},
}
PHASE_FACTOR = {"early": 0.65, "middle": 0.85, "late": 1.00}
MAX_FEATURES_PER_SLICE = 80
MAX_RELATION_ATOMS = 10
NMF_SEED = 1729
STRUCTURAL_ATOMS = {
    "problem", "resolution", "verification", "order", "relation", "ngram",
    "phase", "action", "filetype", "op", "tool", "early", "middle", "late",
    "problem-action", "action-verification", "resolution-verification",
}


def _feature_atoms(feature: str) -> set[str]:
    # Feature prefixes describe the projection channel.  They are useful for
    # addressing a coordinate but are not evidence of a transferable task.
    # Strip these structural labels before data-driven lexical filtering so
    # the blacklist cannot accidentally learn words such as ``order`` or
    # ``action`` from our own feature names.
    text = feature.replace("::", " ").replace("|", " ").replace("=>", " ").replace("->", " ")
    atoms = set(token_set([text]))
    return {atom for atom in atoms if atom not in STRUCTURAL_ATOMS}


def _structural_order_feature(feature: str) -> bool:
    """Return whether an order n-gram contains only channel/phase markers."""
    if not feature.startswith("order|"):
        return False
    marker = "ngram:"
    if marker not in feature:
        return False
    payload = feature.split(marker, 1)[1]
    symbols = payload.split("→")
    structural = {"U", "A", "H"}
    for symbol in symbols:
        if symbol in structural:
            continue
        if symbol.startswith("phase:") and symbol.rsplit(":", 1)[-1] in structural:
            continue
        return False
    return bool(symbols)


def _order_operation_count(feature: str) -> int:
    """Count tool-operation symbols in an order n-gram."""
    if not feature.startswith("order|") or "ngram:" not in feature:
        return 0
    return sum(
        symbol.startswith("T:")
        for symbol in feature.split("ngram:", 1)[1].split("→")
    )


def _vector_norm(vector: dict[str, float]) -> dict[str, float]:
    return l2_normalize({key: float(value) for key, value in vector.items() if value > 0})


def _binary_intersection(left: set[str], right: set[str]) -> set[str]:
    return set(left).intersection(right)


def _phase_index(phase: str) -> int:
    return {"early": 0, "middle": 1, "late": 2}.get(phase, 1)


def _top_items(values: Counter[str] | dict[str, float], limit: int) -> list[str]:
    return [key for key, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _raw_slice_views(row: dict[str, Any]) -> dict[str, Any]:
    """Create raw, auditable four-view features for one slice."""
    raw: dict[str, Counter[str]] = {view: Counter() for view in VIEWS}
    phase_tokens: dict[str, Counter[str]] = {phase: Counter() for phase in ("early", "middle", "late")}
    phase_operations: dict[str, Counter[str]] = {phase: Counter() for phase in ("early", "middle", "late")}
    channel_counts = Counter(event["channel"] for event in row["events"])

    for event in row["events"]:
        channel = event["channel"]
        phase = event["phase"]
        tokens = set(event.get("tokens", []) + event.get("operation_tokens", []))
        operations = set(event.get("operations", []))
        phase_tokens[phase].update(tokens)
        phase_operations[phase].update(
            f"op:{safe_operation_token(operation)}" for operation in operations
        )
        for view in ("problem", "resolution", "verification"):
            base = CHANNEL_WEIGHTS[view][channel] / max(channel_counts[channel], 1)
            phase_factor = PHASE_FACTOR[phase]
            if view == "problem":
                phase_factor = {"early": 1.00, "middle": 0.75, "late": 0.35}[phase]
            elif view == "resolution":
                phase_factor = {"early": 0.35, "middle": 1.00, "late": 0.70}[phase]
            elif view == "verification":
                phase_factor = {"early": 0.15, "middle": 0.55, "late": 1.00}[phase]
            for token in tokens:
                raw[view][f"{view}|{token}"] += base * phase_factor

    sequence_symbols: list[str] = []
    phases: list[str] = []
    for event in row["events"]:
        sequence_symbols.extend(event.get("symbols", []))
        phases.extend(event["phase"] for _ in event.get("symbols", []))
    sequence, phase_sequence = compress_sequence(sequence_symbols, phases)

    for ngram_size in (2, 3):
        for index in range(len(sequence) - ngram_size + 1):
            gram = "→".join(sequence[index:index + ngram_size])
            raw["order"][f"order|ngram:{gram}"] += 1.0
        for index in range(len(phase_sequence) - ngram_size + 1):
            gram = "→".join(phase_sequence[index:index + ngram_size])
            raw["order"][f"order|phase-ngram:{gram}"] += 0.6

    # Data-derived problem->action and action->verification relations.  No
    # operation or application vocabulary is embedded here.
    early_tokens = _top_items(phase_tokens["early"], MAX_RELATION_ATOMS)
    middle_tokens = _top_items(phase_tokens["middle"], MAX_RELATION_ATOMS)
    middle_ops = _top_items(phase_operations["middle"], MAX_RELATION_ATOMS)
    late_ops = _top_items(phase_operations["late"], MAX_RELATION_ATOMS)
    if not middle_ops:
        middle_ops = _top_items(phase_operations["early"], MAX_RELATION_ATOMS)
    if not late_ops:
        late_ops = _top_items(phase_operations["middle"], MAX_RELATION_ATOMS)
    for token in early_tokens:
        for operation in middle_ops[:6]:
            raw["resolution"][f"relation|problem-action:{token}=>{operation}"] += 0.8
    for operation in middle_ops[:8]:
        for verification in late_ops[:6]:
            raw["verification"][f"relation|action-verification:{operation}=>{verification}"] += 0.9
    for token in middle_tokens[:8]:
        for verification in late_ops[:6]:
            raw["verification"][f"relation|resolution-verification:{token}=>{verification}"] += 0.6

    return {
        "raw_views": raw,
        "sequence": sequence,
        "phase_sequence": phase_sequence,
        "first_user_text": row.get("first_user_text", ""),
        "event_counts": dict(channel_counts),
        "operations": sorted({operation for event in row["events"] for operation in event.get("operations", [])}),
    }


def _global_anchor_set(
    domains: list[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
) -> set[str]:
    anchors: set[str] = set()
    for domain in domains:
        anchors.update(derive_anchors(domain, cards.get(domain["domain_id"])))
    return anchors


def build_global_features(
    slices: dict[str, dict[str, Any]],
    domains: list[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one global sparse representation for unique slices."""
    rows: list[dict[str, Any]] = []
    for slice_id in sorted(slices):
        raw = _raw_slice_views(slices[slice_id])
        row = {
            "slice_id": slice_id,
            "session_id": session_id_for_slice(slice_id),
            "source_path": slices[slice_id]["source_path"],
            **raw,
        }
        rows.append(row)

    anchors = _global_anchor_set(domains, cards)
    feature_df: Counter[str] = Counter()
    feature_sessions: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        seen: set[str] = set()
        for view in VIEWS:
            seen.update(f"{view}::{feature}" for feature in row["raw_views"][view])
        feature_df.update(seen)
        for feature in seen:
            feature_sessions[feature].add(row["session_id"])
    n = max(len(rows), 1)
    session_ids = {row["session_id"] for row in rows}
    session_n = max(len(session_ids), 1)
    session_feature_sets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for view in VIEWS:
            for feature in row["raw_views"][view]:
                session_feature_sets[row["session_id"]].add(f"{view}::{feature}")
    session_df = Counter()
    for features in session_feature_sets.values():
        session_df.update(features)

    sequence_sessions: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for symbol in set(row.get("sequence", [])):
            # Bare role symbols are structural markers, not sequence evidence.
            if symbol not in {"U", "A", "H"}:
                sequence_sessions[symbol].add(row["session_id"])

    lexical_df: Counter[str] = Counter()
    for row in rows:
        lexical: set[str] = set()
        for view in VIEWS:
            for feature in row["raw_views"][view]:
                lexical.update(_feature_atoms(feature))
        lexical_df.update(lexical)
    lexical_blacklist = {
        token for token, count in lexical_df.items()
        # A broad, data-derived cutoff removes words that occur in more than
        # roughly one third of the global slices.  Anchors remain visible and
        # are suppressed by weight instead of deleted.
        if count / n >= 0.35 and token not in anchors
    }

    def factor_for(feature: str) -> float:
        df = feature_df.get(feature, 1)
        p = df / n
        session_p = session_df.get(feature, 1) / session_n
        idf = 1.0 + math.log((n + 1) / (df + 1))
        session_factor = 0.35 + 0.65 * rarity(session_p)
        structural_factor = 1.0
        if feature.startswith(("order::", "resolution::relation|", "verification::relation|")):
            structural_factor = 0.45 + 0.55 * rarity(p)
        atoms = _feature_atoms(feature)
        anchor_factor = 0.25 if atoms.intersection(anchors) else 1.0
        return rarity(p) * idf * session_factor * structural_factor * anchor_factor

    factor_cache = {feature: factor_for(feature) for feature in feature_df}
    factor_values = list(factor_cache.values())
    evidence_cut = quantile(factor_values, 0.55) if factor_values else 0.0
    atom_cache = {
        feature: _feature_atoms(feature)
        for feature in factor_cache
    }
    for row in rows:
        weighted_views: dict[str, dict[str, float]] = {}
        relation_evidence: set[str] = set()
        motif_evidence: set[str] = set()
        factor_features: set[str] = set()
        for view in VIEWS:
            values: dict[str, float] = {}
            for feature, value in row["raw_views"][view].items():
                atoms = atom_cache.get(f"{view}::{feature}", _feature_atoms(feature))
                if atoms and all(atom in lexical_blacklist for atom in atoms):
                    continue
                full = f"{view}::{feature}"
                values[feature] = value * factor_cache.get(full, 0.0)
                if factor_cache.get(full, 0.0) >= evidence_cut:
                    factor_features.add(full)
                session_support = len(feature_sessions.get(full, set()))
                session_rate = session_support / session_n
                # Evidence must recur across independent sessions but should
                # not be a near-universal tool routine.  This keeps generic
                # Read/Edit/Answer patterns out of candidate Skill evidence
                # without naming or removing any application vocabulary.
                if (
                    feature.startswith("relation|")
                    and factor_cache.get(full, 0.0) > 0
                    and session_support >= 2
                    and session_rate <= 0.35
                ):
                    relation_evidence.add(full)
                if (
                    feature.startswith("order|")
                    and not _structural_order_feature(feature)
                    and factor_cache.get(full, 0.0) > 0
                    and session_support >= 2
                    # A one-operation transition such as Assistant ->
                    # Compile is a generic runtime routine.  Order evidence
                    # requires at least two operations so that it describes a
                    # transferable sequence rather than a channel boundary.
                    and _order_operation_count(feature) >= 2
                    and session_rate <= 0.25
                ):
                    motif_evidence.add(full)
            weighted_views[view] = _vector_norm(values)
        row["views"] = weighted_views
        row["relation_evidence"] = relation_evidence
        row["motif_evidence"] = motif_evidence
        row["feature_evidence"] = factor_features
        row["sequence_evidence"] = {
            symbol for symbol in row.get("sequence", [])
            if symbol not in {"U", "A", "H"}
            and 2 <= len(sequence_sessions.get(symbol, set()))
            and len(sequence_sessions.get(symbol, set())) / session_n <= 0.35
        }

        combined: dict[str, float] = {}
        for view in VIEWS:
            normalized = weighted_views[view]
            for feature, value in normalized.items():
                combined[f"{view}::{feature}"] = value * VIEW_WEIGHTS[view]
        row["combined_vector"] = _vector_norm(combined)

    config = {
        "unique_slice_count": len(rows),
        "unique_session_count": len(session_ids),
        "global_anchor_count": len(anchors),
        "lexical_blacklist_count": len(lexical_blacklist),
        "lexical_blacklist": sorted(lexical_blacklist),
        "feature_count": len(feature_df),
        "max_features_per_slice": MAX_FEATURES_PER_SLICE,
        "views": list(VIEWS),
        "view_weights": VIEW_WEIGHTS,
        "anchor_suppression_factor": 0.25,
        "session_rarity_enabled": True,
        "evidence_session_rate_max": 0.35,
        "sequence_evidence_min_sessions": 2,
        "feature_document_frequency": dict(sorted(feature_df.items())),
        "feature_session_frequency": {key: len(value) for key, value in sorted(feature_sessions.items())},
    }
    return rows, config


def _top_sparse_features(vector: dict[str, float], limit: int = MAX_FEATURES_PER_SLICE) -> dict[str, float]:
    return dict(sorted(vector.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _dense_from_rows(rows: list[dict[str, float]], vocabulary: list[str]) -> tuple[list[list[float]], list[dict[int, float]], list[list[tuple[int, float]]]]:
    index = {feature: i for i, feature in enumerate(vocabulary)}
    sparse_rows: list[dict[int, float]] = []
    columns: list[list[tuple[int, float]]] = [[] for _ in vocabulary]
    dense: list[list[float]] = []
    for row_index, row in enumerate(rows):
        sparse = {index[key]: value for key, value in row.items() if key in index}
        sparse_rows.append(sparse)
        dense_row = [0.0] * len(vocabulary)
        for column, value in sparse.items():
            dense_row[column] = value
            columns[column].append((row_index, value))
        dense.append(dense_row)
    return dense, sparse_rows, columns


def _nmf_factorize(
    sparse_rows: list[dict[int, float]],
    columns: list[list[tuple[int, float]]],
    feature_count: int,
    rank: int,
    seed: int,
    iterations: int = 28,
) -> tuple[list[list[float]], list[list[float]], float]:
    rng = random.Random(seed)
    n = len(sparse_rows)
    eps = 1e-10
    W = [[0.10 + rng.random() for _ in range(rank)] for _ in range(n)]
    H = [[0.10 + rng.random() for _ in range(feature_count)] for _ in range(rank)]
    for _ in range(iterations):
        hht = [[sum(H[a][j] * H[b][j] for j in range(feature_count)) for b in range(rank)] for a in range(rank)]
        for i, sparse in enumerate(sparse_rows):
            numerator = [0.0] * rank
            for j, value in sparse.items():
                for k in range(rank):
                    numerator[k] += value * H[k][j]
            for k in range(rank):
                denominator = sum(W[i][a] * hht[a][k] for a in range(rank)) + eps
                W[i][k] *= numerator[k] / denominator

        wtw = [[sum(W[i][a] * W[i][b] for i in range(n)) for b in range(rank)] for a in range(rank)]
        for j, entries in enumerate(columns):
            numerator = [sum(W[i][k] * value for i, value in entries) for k in range(rank)]
            for k in range(rank):
                denominator = sum(wtw[k][a] * H[a][j] for a in range(rank)) + eps
                H[k][j] *= numerator[k] / denominator

    error = 0.0
    for i, sparse in enumerate(sparse_rows):
        for j, value in sparse.items():
            estimate = sum(W[i][k] * H[k][j] for k in range(rank))
            error += (value - estimate) ** 2
    return W, H, error


def _pairwise_dense_cosine(rows: list[list[float]]) -> list[list[float]]:
    normalized = []
    for row in rows:
        norm = math.sqrt(sum(value * value for value in row))
        normalized.append([value / norm for value in row] if norm else [0.0] * len(row))
    matrix = [[0.0] * len(rows) for _ in rows]
    for left in range(len(rows)):
        matrix[left][left] = 1.0
        for right in range(left + 1, len(rows)):
            value = max(0.0, min(1.0, sum(a * b for a, b in zip(normalized[left], normalized[right]))))
            matrix[left][right] = matrix[right][left] = value
    return matrix


def _matrix_stability(left: list[list[float]], right: list[list[float]]) -> float:
    if not left or not right:
        return 0.0
    differences = [
        abs(left[i][j] - right[i][j])
        for i in range(len(left))
        for j in range(i + 1, len(left))
    ]
    return max(0.0, 1.0 - sum(differences) / max(len(differences), 1))


def learn_latent_space(
    rows: list[dict[str, Any]],
    feature_config: dict[str, Any],
) -> tuple[list[list[float]], dict[str, Any]]:
    combined_rows = [_top_sparse_features(row["combined_vector"]) for row in rows]
    vocabulary = sorted({feature for row in combined_rows for feature in row})
    _, sparse_rows, columns = _dense_from_rows(combined_rows, vocabulary)
    if not vocabulary:
        return [[1.0] for _ in rows], {"rank": 1, "vocabulary": [], "selection": []}

    max_rank = min(12, max(1, len(rows) - 1))
    rank_candidates = list(range(2, max_rank + 1)) if max_rank >= 2 else [1]
    selections: list[dict[str, Any]] = []
    best: tuple[float, int, list[list[float]], list[list[float]]] | None = None
    energy = sum(value * value for row in sparse_rows for value in row.values()) or 1.0
    feature_session_support = feature_config.get("feature_session_frequency", {})
    baseline_error: float | None = None
    for rank in rank_candidates:
        W, H, error = _nmf_factorize(sparse_rows, columns, len(vocabulary), rank, NMF_SEED + rank)
        W2, _, _ = _nmf_factorize(sparse_rows, columns, len(vocabulary), rank, NMF_SEED + rank + 1000, iterations=16)
        stability = _matrix_stability(_pairwise_dense_cosine(W), _pairwise_dense_cosine(W2))
        recurrence_values = []
        for factor in H:
            top = sorted(range(len(vocabulary)), key=lambda index: (-factor[index], vocabulary[index]))[:10]
            recurrence_values.append(
                sum(feature_session_support.get(vocabulary[index], 0) >= 2 for index in top) / max(len(top), 1)
            )
        recurrence = sum(recurrence_values) / max(len(recurrence_values), 1)
        fit = max(0.0, min(1.0, 1.0 - error / energy))
        if baseline_error is None:
            baseline_error = error
        relative_error_gain = max(0.0, (baseline_error - error) / max(baseline_error, 1e-12))
        # Sparse fit, pairwise stability and cross-session recurrence are
        # balanced directly.  The relative error gain is retained in the
        # audit record, while the small complexity penalty prevents extra
        # factors from splitting otherwise reusable Skill neighborhoods.
        score = 0.50 * fit + 0.30 * stability + 0.20 * recurrence - 0.01 * rank
        metadata = {
            "rank": rank,
            "fit": round(fit, 8),
            "stability": round(stability, 8),
            "cross_session_recurrence": round(recurrence, 8),
            "relative_error_gain": round(relative_error_gain, 8),
            "selection_score": round(score, 8),
            "reconstruction_error": round(error, 8),
        }
        selections.append(metadata)
        if best is None or score > best[0]:
            best = (score, rank, W, H)
    assert best is not None
    _, rank, W, H = best
    coordinates = [_vector_norm({f"factor:{index}": value for index, value in enumerate(row)}) for row in W]
    factor_payload = []
    for factor_index, factor in enumerate(H):
        top_indices = sorted(range(len(vocabulary)), key=lambda index: (-factor[index], vocabulary[index]))[:18]
        factor_payload.append({
            "factor_id": f"factor-{factor_index + 1:02d}",
            "top_features": [
                {
                    "feature": vocabulary[index],
                    "weight": round(factor[index], 8),
                    "session_support": feature_session_support.get(vocabulary[index], 0),
                }
                for index in top_indices
            ],
        })
    for row, coordinate in zip(rows, coordinates):
        row["latent_vector"] = coordinate
        top_factor_values = sorted(coordinate.items(), key=lambda item: (-item[1], item[0]))
        row["top_factors"] = [factor for factor, value in top_factor_values if value >= 0.20][:5]
    return [list(coordinate.values()) for coordinate in coordinates], {
        "rank": rank,
        "vocabulary_size": len(vocabulary),
        "selection": selections,
        "factors": factor_payload,
        "max_features_per_slice": MAX_FEATURES_PER_SLICE,
        "method": "deterministic-standard-library-nmf",
    }


def _latent_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return cosine(left, right)


def _shared_evidence(left: dict[str, Any], right: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    relations = _binary_intersection(left["relation_evidence"], right["relation_evidence"])
    motifs = _binary_intersection(left["motif_evidence"], right["motif_evidence"])
    factors = _binary_intersection(set(left.get("top_factors", [])), set(right.get("top_factors", [])))
    return relations, motifs, factors


def _skill_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    latent = _latent_similarity(left.get("latent_vector", {}), right.get("latent_vector", {}))
    relations, motifs, _ = _shared_evidence(left, right)
    relation_sim = _binary_cosine(left["relation_evidence"], right["relation_evidence"])
    motif_sim = _binary_cosine(left["motif_evidence"], right["motif_evidence"])
    order = lcs_similarity(left.get("sequence", []), right.get("sequence", []))
    return round(max(0.0, min(1.0, 0.50 * latent + 0.20 * relation_sim + 0.15 * motif_sim + 0.15 * order)), 8)


def build_similarity_matrix(rows: list[dict[str, Any]]) -> list[list[float]]:
    matrix = [[0.0] * len(rows) for _ in rows]
    for left in range(len(rows)):
        matrix[left][left] = 1.0
        for right in range(left + 1, len(rows)):
            value = _skill_similarity(rows[left], rows[right])
            matrix[left][right] = matrix[right][left] = value
    return matrix


def _pair_keys(pairs: list[tuple[int, int]]) -> set[tuple[int, int]]:
    return {tuple(sorted(pair)) for pair in pairs}


def cannot_link_edges(
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    values = [matrix[i][j] for i in range(len(rows)) for j in range(i + 1, len(rows))]
    cut = quantile(values, 0.10) if values else 0.0
    edges: list[dict[str, Any]] = []
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if matrix[left][right] > cut:
                continue
            relations, motifs, factors = _shared_evidence(rows[left], rows[right])
            if relations or motifs or factors:
                continue
            if set(rows[left].get("sequence", [])).intersection(rows[right].get("sequence", [])):
                continue
            edges.append({
                "left_slice_id": rows[left]["slice_id"],
                "right_slice_id": rows[right]["slice_id"],
                "left_session_id": rows[left]["session_id"],
                "right_session_id": rows[right]["session_id"],
                "skill_similarity": matrix[left][right],
                "reason": ["low_skill_similarity", "disjoint_relations", "disjoint_sequence"],
            })
    return edges, {
        "cut_p10": round(cut, 8),
        "cannot_link_count": len(edges),
    }


def _contains_conflict(group: list[int], conflicts: set[tuple[int, int]]) -> bool:
    return any(tuple(sorted((left, right))) in conflicts for offset, left in enumerate(group) for right in group[offset + 1:])


def _repair_route_conflicts(groups: list[list[int]], matrix: list[list[float]], conflicts: set[tuple[int, int]]) -> list[list[int]]:
    repaired: list[list[int]] = []
    for group in groups:
        if not _contains_conflict(group, conflicts):
            repaired.append(sorted(set(group)))
            continue
        ordered = sorted(group, key=lambda item: (-sum(matrix[item][other] for other in group if other != item), item))
        local: list[list[int]] = []
        for item in ordered:
            candidates = []
            for index, target in enumerate(local):
                if any(tuple(sorted((item, other))) in conflicts for other in target):
                    continue
                score = sum(matrix[item][other] for other in target) / max(len(target), 1)
                candidates.append((score, index))
            if candidates:
                _, index = max(candidates)
                local[index].append(item)
            else:
                local.append([item])
        repaired.extend(sorted((sorted(set(part)) for part in local), key=lambda part: (min(part), len(part))))
    return repaired


def _refine_oversized_routes(
    groups: list[list[int]],
    matrix: list[list[float]],
    target_capacity: int,
) -> tuple[list[list[int]], int]:
    """Recursively try data-derived local cuts for overloaded route packets."""
    refined: list[list[int]] = []
    pending = [sorted(set(group)) for group in groups if group]
    seen: set[tuple[int, ...]] = set()
    attempts = 0
    while pending:
        group = pending.pop()
        key = tuple(group)
        if key in seen:
            refined.append(group)
            continue
        seen.add(key)
        if len(group) <= max(target_capacity, 1):
            refined.append(group)
            continue
        local = [[matrix[left][right] for right in group] for left in group]
        ideal = max(2, math.ceil(len(group) / max(target_capacity, 1)))
        local_groups, _ = choose_forward_groups(
            local,
            ideal_groups=ideal,
            sharpness=4.0,
            load_weight=1.20 + 0.10 * math.log1p(len(group) / max(target_capacity, 1)),
            overlap_margin=0.0,
            reverse_groups=None,
            reverse_strategy_weight=0.0,
        )
        mapped = [sorted({group[index] for index in part}) for part in local_groups if part]
        if len(mapped) <= 1 or any(set(part) == set(group) for part in mapped):
            refined.append(group)
            continue
        attempts += 1
        pending.extend(mapped)
    return sorted(refined, key=lambda group: (min(group), len(group))), attempts


def choose_route_packages(
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
    cannot_edges: list[dict[str, Any]],
    target_capacity: int,
    overlap_margin: float,
) -> tuple[list[list[int]], dict[str, Any]]:
    conflicts = _pair_keys([
        (next(index for index, row in enumerate(rows) if row["slice_id"] == edge["left_slice_id"]),
         next(index for index, row in enumerate(rows) if row["slice_id"] == edge["right_slice_id"]))
        for edge in cannot_edges
    ])
    constrained = [row[:] for row in matrix]
    for left, right in conflicts:
        constrained[left][right] = constrained[right][left] = 0.0
    ideal_groups = max(1, math.ceil(len(rows) / max(target_capacity, 1)))
    # Load pressure is continuous: larger domains receive a slightly stronger
    # penalty, while small domains are not forced into a fixed number of
    # packets.  The value is data-derived from the requested capacity and the
    # current domain size rather than a size-based branch.
    load_weight = 1.0 + 0.10 * math.log1p(len(rows) / max(target_capacity, 1))
    groups, metadata = choose_forward_groups(
        constrained,
        ideal_groups=ideal_groups,
        sharpness=4.0,
        load_weight=load_weight,
        overlap_margin=overlap_margin,
        reverse_groups=None,
        reverse_strategy_weight=0.0,
    )
    groups = _repair_route_conflicts(groups, constrained, conflicts)
    groups, refinement_count = _refine_oversized_routes(groups, constrained, target_capacity)
    groups = _repair_route_conflicts(groups, constrained, conflicts)
    metadata["target_capacity"] = target_capacity
    metadata["conflict_repair_count"] = sum(
        1 for group in groups if len(group) == 1
    )
    metadata["capacity_refinement_count"] = refinement_count
    return groups, metadata


def _candidate_stability(
    members: list[int],
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
    threshold: float,
    repeats: int = 5,
) -> float:
    if len(members) < 2:
        return 0.0
    base_pairs = {(left, right) for offset, left in enumerate(members) for right in members[offset + 1:] if matrix[left][right] >= threshold}
    if not base_pairs:
        return 0.0
    retained: list[float] = []
    for repeat in range(repeats):
        rng = random.Random(9001 + repeat)
        kept_pairs = 0
        for left, right in base_pairs:
            left_rel = set(rows[left]["relation_evidence"])
            right_rel = set(rows[right]["relation_evidence"])
            left_motif = set(rows[left]["motif_evidence"])
            right_motif = set(rows[right]["motif_evidence"])
            for values in (left_rel, right_rel, left_motif, right_motif):
                for item in list(values):
                    if rng.random() < 0.10:
                        values.remove(item)
            evidence = len(left_rel.intersection(right_rel)) + len(left_motif.intersection(right_motif))
            adjusted = 0.50 * _latent_similarity(rows[left].get("latent_vector", {}), rows[right].get("latent_vector", {}))
            adjusted += 0.20 * _binary_cosine(left_rel, right_rel)
            adjusted += 0.15 * _binary_cosine(left_motif, right_motif)
            adjusted += 0.15 * lcs_similarity(rows[left].get("sequence", []), rows[right].get("sequence", []))
            if adjusted >= threshold and (evidence > 0 or matrix[left][right] >= min(0.95, threshold + 0.10)):
                kept_pairs += 1
        retained.append(kept_pairs / max(len(base_pairs), 1))
    return round(sum(retained) / max(len(retained), 1), 8)


def _representative_ids(rows: list[dict[str, Any]], members: list[int], matrix: list[list[float]], limit: int = 3) -> list[str]:
    ranked = sorted(
        members,
        key=lambda item: (-sum(matrix[item][other] for other in members if other != item) / max(len(members) - 1, 1), rows[item]["slice_id"]),
    )
    return [rows[item]["slice_id"] for item in ranked[:limit]]


def build_skill_candidates(
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
    cannot_edges: list[dict[str, Any]],
    max_size: int = 8,
) -> tuple[list[dict[str, Any]], list[int], dict[str, Any]]:
    values = [matrix[i][j] for i in range(len(rows)) for j in range(i + 1, len(rows))]
    threshold = quantile(values, 0.80) if len(values) >= 3 else 0.0
    conflicts = _pair_keys([
        (
            next(index for index, row in enumerate(rows) if row["slice_id"] == edge["left_slice_id"]),
            next(index for index, row in enumerate(rows) if row["slice_id"] == edge["right_slice_id"]),
        )
        for edge in cannot_edges
    ])
    candidates: set[tuple[int, ...]] = set()
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if rows[left]["session_id"] == rows[right]["session_id"]:
                continue
            if matrix[left][right] < threshold:
                continue
            if tuple(sorted((left, right))) in conflicts:
                continue
            relations, motifs, _ = _shared_evidence(rows[left], rows[right])
            if len(relations) + len(motifs) < 2:
                continue
            members = [left, right]
            changed = True
            while changed:
                changed = False
                if len(members) >= max(max_size, 2):
                    break
                for item in range(len(rows)):
                    if item in members or any(tuple(sorted((item, other))) in conflicts for other in members):
                        continue
                    scores = [matrix[item][other] for other in members]
                    if scores and min(scores) >= threshold:
                        members.append(item)
                        changed = True
                        if len(members) >= max(max_size, 2):
                            break
            if len({rows[item]["session_id"] for item in members}) < 2:
                continue
            candidates.add(tuple(sorted(members)))

    payload: list[dict[str, Any]] = []
    used: set[int] = set()
    accepted_members: list[set[int]] = []
    candidate_number = 1
    for member_tuple in sorted(candidates, key=lambda item: (-len(item), item)):
        members = list(member_tuple)
        evidence_rel = set.intersection(*(set(rows[item]["relation_evidence"]) for item in members)) if members else set()
        evidence_motif = set.intersection(*(set(rows[item]["motif_evidence"]) for item in members)) if members else set()
        evidence_sequence = set.intersection(*(set(rows[item].get("sequence_evidence", [])) for item in members)) if members else set()
        shared_evidence_count = len(evidence_rel) + len(evidence_motif)
        if shared_evidence_count < 2:
            continue
        member_set = set(members)
        # Keep overlap as an intentional capability, but drop near-duplicate
        # nested candidates that arise from several equivalent high-similarity
        # seeds.  A candidate is redundant when an accepted larger candidate
        # contains at least 80% of its members.
        if any(
            member_set <= accepted
            and len(member_set) / max(len(accepted), 1) >= 0.80
            for accepted in accepted_members
        ):
            continue
        stability = _candidate_stability(members, rows, matrix, threshold)
        if stability < 0.35:
            continue
        density = sum(matrix[left][right] for offset, left in enumerate(members) for right in members[offset + 1:]) / max(len(members) * (len(members) - 1) / 2, 1)
        item = {
            "candidate_id": f"skill-{candidate_number:02d}",
            "member_slice_ids": [rows[index]["slice_id"] for index in members],
            "member_session_ids": sorted({rows[index]["session_id"] for index in members}),
            "size": len(members),
            "distinct_session_count": len({rows[index]["session_id"] for index in members}),
            "shared_motif_count": shared_evidence_count,
            "shared_relation_features": sorted(evidence_rel),
            "shared_sequence_features": sorted(evidence_motif),
            "shared_sequence_symbols": sorted(evidence_sequence),
            "latent_density": round(density, 8),
            "perturbation_jaccard": stability,
            "representative_slice_ids": _representative_ids(rows, members, matrix),
            "factor_evidence": sorted(set.intersection(*(set(rows[index].get("top_factors", [])) for index in members))) if members else [],
            "sequence_evidence": sorted(evidence_sequence),
            "source_event_evidence": [
                {
                    "slice_id": rows[index]["slice_id"],
                    "first_user_text": rows[index].get("first_user_text", ""),
                    "source_path": rows[index]["source_path"],
                }
                for index in members
            ],
        }
        payload.append(item)
        candidate_number += 1
        accepted_members.append(member_set)
        used.update(members)
    residual = sorted(set(range(len(rows))) - used)
    return payload, residual, {
        "pair_threshold_p80": round(threshold, 8),
        "candidate_count": len(payload),
        "residual_count": len(residual),
        "candidate_seed_count": len(candidates),
        "candidate_max_size": max_size,
    }


def _saveable_vector(vector: dict[str, float], limit: int = 80) -> dict[str, float]:
    return {key: round(value, 8) for key, value in _top_sparse_features(vector, limit).items()}


def _cluster_report(
    domain_id: str,
    rows: list[dict[str, Any]],
    route_groups: list[list[int]],
    skill_candidates: list[dict[str, Any]],
    route_meta: dict[str, Any],
    skill_meta: dict[str, Any],
) -> str:
    lines = [
        f"# {domain_id} V5 Skill-space report",
        "",
        f"- Route packages: {len(route_groups)}",
        f"- Skill candidates: {len(skill_candidates)}",
        f"- Skill residual slices: {skill_meta['residual_count']}",
        f"- Route target capacity: {route_meta.get('target_capacity')}",
        f"- Route selection score: {route_meta.get('selection_score')}",
        "",
        "## Route packages",
        "",
        "| package | size | sessions | members |",
        "|---|---:|---:|---|",
    ]
    for number, group in enumerate(route_groups, start=1):
        sessions = len({rows[index]["session_id"] for index in group})
        members = ", ".join(rows[index]["slice_id"] for index in group[:8])
        if len(group) > 8:
            members += ", ..."
        lines.append(f"| route-{number:02d} | {len(group)} | {sessions} | {members} |")
    lines.extend(["", "## Skill candidates", "", "| candidate | size | sessions | motifs | density | stability |", "|---|---:|---:|---:|---:|---:|"])
    for candidate in skill_candidates:
        lines.append(
            f"| {candidate['candidate_id']} | {candidate['size']} | {candidate['distinct_session_count']} | "
            f"{candidate['shared_motif_count']} | {candidate['latent_density']} | {candidate['perturbation_jaccard']} |"
        )
    return "\n".join(lines) + "\n"


def run(
    slices_dir: Path,
    domains_path: Path,
    feature_cards_path: Path | None,
    output: Path,
    target_capacity: int = 8,
    route_overlap_margin: float = 0.02,
) -> dict[str, Any]:
    slices = load_slices(slices_dir)
    domains = load_domains(domains_path)
    cards = load_cards(feature_cards_path)
    rows, feature_config = build_global_features(slices, domains, cards)
    _, latent_config = learn_latent_space(rows, feature_config)
    output.mkdir(parents=True, exist_ok=True)
    shared = output / "shared"
    shared.mkdir(parents=True, exist_ok=True)

    write_json(shared / "latent-factors.json", latent_config)
    with (shared / "representations.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            serial = {
                "slice_id": row["slice_id"],
                "session_id": row["session_id"],
                "source_path": row["source_path"],
                "first_user_text": row["first_user_text"],
                "event_counts": row["event_counts"],
                "operations": row["operations"],
                "sequence": row["sequence"],
                "phase_sequence": row["phase_sequence"],
                "top_factors": row.get("top_factors", []),
                "latent_vector": _saveable_vector(row.get("latent_vector", {})),
                "views": {view: _saveable_vector(row["views"][view]) for view in VIEWS},
                "relation_evidence": sorted(row["relation_evidence"]),
                "motif_evidence": sorted(row["motif_evidence"]),
            }
            handle.write(json.dumps(serial, ensure_ascii=False) + "\n")

    motif_support: Counter[str] = Counter()
    motif_sessions: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for motif in row["motif_evidence"]:
            motif_support[motif] += 1
            motif_sessions[motif].add(row["session_id"])
    with (shared / "sequence-motifs.jsonl").open("w", encoding="utf-8") as handle:
        for motif in sorted(motif_support):
            handle.write(json.dumps({
                "feature": motif,
                "slice_support": motif_support[motif],
                "session_support": len(motif_sessions[motif]),
            }, ensure_ascii=False) + "\n")

    by_id = {row["slice_id"]: row for row in rows}
    domain_summaries = []
    cross_index: dict[str, dict[str, Any]] = {
        row["slice_id"]: {
            "slice_id": row["slice_id"],
            "route_package_ids": [],
            "skill_candidate_ids": [],
        }
        for row in rows
    }

    for domain in domains:
        did = domain["domain_id"]
        domain_rows = [by_id[sid] for sid in domain["members"] if sid in by_id]
        if not domain_rows:
            continue
        matrix = build_similarity_matrix(domain_rows)
        edges, edge_meta = cannot_link_edges(domain_rows, matrix)
        route_groups, route_meta = choose_route_packages(
            domain_rows,
            matrix,
            edges,
            target_capacity,
            route_overlap_margin,
        )
        skill_candidates, residual, skill_meta = build_skill_candidates(
            domain_rows,
            matrix,
            edges,
            max_size=max(target_capacity, 2),
        )
        domain_output = output / did
        domain_output.mkdir(parents=True, exist_ok=True)
        route_payload = []
        for number, group in enumerate(route_groups, start=1):
            route_id = f"route-{number:02d}"
            route_payload.append({
                "route_id": route_id,
                "member_slice_ids": [domain_rows[index]["slice_id"] for index in group],
                "member_session_ids": sorted({domain_rows[index]["session_id"] for index in group}),
                "size": len(group),
                "unique_session_count": len({domain_rows[index]["session_id"] for index in group}),
                "representative_slice_ids": _representative_ids(domain_rows, group, matrix),
                "load_pressure": round(math.log1p(len(group) / max(target_capacity, 1)), 8),
                "factor_evidence": sorted(set().union(*(set(domain_rows[index].get("top_factors", [])) for index in group))),
            })
            for index in group:
                cross_index[domain_rows[index]["slice_id"]]["route_package_ids"].append(f"{did}:{route_id}")
        for candidate in skill_candidates:
            for sid in candidate["member_slice_ids"]:
                cross_index[sid]["skill_candidate_ids"].append(f"{did}:{candidate['candidate_id']}")
        write_json(domain_output / "route-packages.json", {
            "domain_id": did,
            "target_capacity": target_capacity,
            "packages": route_payload,
            "metadata": route_meta,
        })
        write_json(domain_output / "skill-candidates.json", {
            "domain_id": did,
            "candidates": skill_candidates,
            "residual_slice_ids": [domain_rows[index]["slice_id"] for index in residual],
            "metadata": skill_meta,
        })
        (domain_output / "cannot-link.jsonl").write_text(
            "".join(json.dumps(edge, ensure_ascii=False) + "\n" for edge in edges),
            encoding="utf-8",
        )
        (domain_output / "report.md").write_text(
            _cluster_report(did, domain_rows, route_groups, skill_candidates, route_meta, skill_meta),
            encoding="utf-8",
        )
        domain_summaries.append({
            "domain_id": did,
            "slice_count": len(domain_rows),
            "route_package_count": len(route_payload),
            "route_size_min": min((item["size"] for item in route_payload), default=0),
            "route_size_mean": round(sum(item["size"] for item in route_payload) / max(len(route_payload), 1), 4),
            "route_size_max": max((item["size"] for item in route_payload), default=0),
            "skill_candidate_count": len(skill_candidates),
            "skill_residual_count": len(residual),
            "cannot_link_count": len(edges),
            "skill_metadata": skill_meta,
        })

    with (shared / "cross-view-index.jsonl").open("w", encoding="utf-8") as handle:
        for sid in sorted(cross_index):
            handle.write(json.dumps(cross_index[sid], ensure_ascii=False) + "\n")

    route_sizes = [item["size"] for domain in domain_summaries for item in [
        {"size": size} for size in []
    ]]
    for domain in domains:
        route_file = output / domain["domain_id"] / "route-packages.json"
        if route_file.exists():
            route_sizes.extend(item["size"] for item in read_json(route_file).get("packages", []))
    skill_count = sum(item["skill_candidate_count"] for item in domain_summaries)
    summary = {
        "algorithm_version": "behavior-logic-clustering-v5-global-multiview-skill-space",
        "source_slice_count": len(slices),
        "unique_slice_count": len(rows),
        "domain_count": len(domain_summaries),
        "representation_rows": sum(item["slice_count"] for item in domain_summaries),
        "route_package_count": sum(item["route_package_count"] for item in domain_summaries),
        "skill_candidate_count": skill_count,
        "route_size_min": min(route_sizes, default=0),
        "route_size_mean": round(sum(route_sizes) / max(len(route_sizes), 1), 4),
        "route_size_max": max(route_sizes, default=0),
        "route_size_p95": sorted(route_sizes)[min(len(route_sizes) - 1, max(0, math.ceil(len(route_sizes) * 0.95) - 1))] if route_sizes else 0,
        "feature_config": feature_config,
        "latent_config": latent_config,
        "target_capacity": target_capacity,
        "route_overlap_margin": route_overlap_margin,
        "domains": domain_summaries,
        "no_llm_or_embedding": True,
    }
    write_json(output / "summary.json", summary)
    write_json(output / "manifest.json", {
        "algorithm_version": summary["algorithm_version"],
        "slices_dir": str(slices_dir.resolve()),
        "domains": str(domains_path.resolve()),
        "feature_cards": str(feature_cards_path.resolve()) if feature_cards_path else None,
        "output": str(output.resolve()),
        "target_capacity": target_capacity,
        "route_overlap_margin": route_overlap_margin,
        "event_channels": ["user_text", "assistant_text", "assistant_thinking", "assistant_reasoning", "tool_call:*"],
        "excluded_channels": ["record:*", "tool_result", "user_image", "metadata"],
        "views": list(VIEWS),
        "latent_method": "deterministic-standard-library-nmf",
        "skill_membership": "overlapping",
        "route_coverage": "full per domain",
        "new_llm_or_embedding_calls": 0,
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--domains", type=Path, required=True)
    parser.add_argument("--feature-cards", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-capacity", type=int, default=8)
    parser.add_argument("--route-overlap-margin", type=float, default=0.02)
    args = parser.parse_args()
    print(json.dumps(run(
        args.slices_dir,
        args.domains,
        args.feature_cards,
        args.output,
        args.target_capacity,
        args.route_overlap_margin,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
