"""V6 domain-local, quality-first Skill-family clustering.

The unit of this experiment is one existing fine-domain slice set.  The
outer runner invokes :func:`run_domain` once for each of the eight domains;
domains are never concatenated into one clustering input.

V6 deliberately has no route-package or batching stage.  The only size
related input is the continuous split-pressure term.  It adjusts the
data-derived pair threshold for a domain with more slices.  Every other
calculation exists to preserve auditable, cross-session Skill evidence:
problem/resolution/verification/order features, latent similarity, sequence
evidence, stability, and cannot-link constraints.

No LLM or new embedding call is made.  V5 remains unchanged as the baseline.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Any

try:
    import behavior_logic_clustering_v5 as v5
except ImportError:  # pragma: no cover
    from . import behavior_logic_clustering_v5 as v5


VIEWS = v5.VIEWS


def _row_source_paths(row: dict[str, Any]) -> list[str]:
    return list(row.get("source_paths", [row.get("source_path", "")]))


def _shared_evidence(left: dict[str, Any], right: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    return v5._shared_evidence(left, right)


def _pair_evidence_count(left: dict[str, Any], right: dict[str, Any]) -> int:
    relations, motifs, _ = _shared_evidence(left, right)
    # Latent factors help rank pairs but are not semantic evidence by
    # themselves.  Only repeated relation or sequence evidence can seed a
    # Skill candidate.
    return len(relations) + len(motifs)


def _pair_key(left: int, right: int) -> tuple[int, int]:
    return tuple(sorted((left, right)))


def _split_pressure(domain_slice_count: int, target_capacity: int) -> dict[str, float]:
    """Return a smooth, domain-local tendency to split larger inputs."""
    scale = max(int(target_capacity), 1)
    ratio = domain_slice_count / scale
    pressure = math.log1p(ratio)
    tendency = pressure / (1.0 + pressure)
    # Size changes only the data-derived threshold.  It is not a group-size
    # cap; quality evidence remains the dominant decision.
    pair_quantile = min(0.88, max(0.70, 0.80 + 0.03 * tendency))
    return {
        "domain_slice_count": float(domain_slice_count),
        "target_capacity_scale": float(scale),
        "ratio": round(ratio, 8),
        "pressure": round(pressure, 8),
        "tendency": round(tendency, 8),
        "pair_quantile": round(pair_quantile, 8),
    }


def _conflict_pairs(rows: list[dict[str, Any]], cannot_edges: list[dict[str, Any]]) -> set[tuple[int, int]]:
    index = {row["slice_id"]: number for number, row in enumerate(rows)}
    return {
        tuple(sorted((index[edge["left_slice_id"]], index[edge["right_slice_id"]])))
        for edge in cannot_edges
        if edge["left_slice_id"] in index and edge["right_slice_id"] in index
    }


def _has_conflict(member_indexes: list[int], conflicts: set[tuple[int, int]], candidate: int | None = None) -> bool:
    values = list(member_indexes)
    if candidate is not None:
        values.append(candidate)
    return any(tuple(sorted((left, right))) in conflicts for offset, left in enumerate(values) for right in values[offset + 1:])


def _representative_indexes(rows: list[dict[str, Any]], members: list[int], matrix: list[list[float]]) -> list[int]:
    return sorted(
        members,
        key=lambda index: (
            -sum(matrix[index][other] for other in members if other != index) / max(len(members) - 1, 1),
            rows[index]["slice_id"],
        ),
    )[: min(3, len(members))]


def _supporting_features(rows: list[dict[str, Any]], members: list[int], field: str) -> list[str]:
    support: Counter[str] = Counter()
    for index in members:
        support.update(set(rows[index].get(field, set())))
    # Half-family support keeps a candidate tied to a repeated pattern instead
    # of allowing one generic operation to bridge unrelated members.
    minimum = max(1, math.ceil(len(members) * 0.50))
    return sorted(feature for feature, count in support.items() if count >= minimum)


def _restrict_generic_evidence(rows: list[dict[str, Any]], feature_config: dict[str, Any]) -> dict[str, int]:
    """Remove only high-session-rate evidence from candidate support.

    The underlying weighted vectors remain intact.  This affects only the
    evidence used to form Skill families, so ubiquitous procedures cannot
    connect otherwise unrelated slices.  The cut is computed inside this
    domain and never names an application or programming language.
    """
    session_count = max(int(feature_config.get("unique_session_count", 1)), 1)
    frequencies = feature_config.get("feature_session_frequency", {})
    removed = {"relation": 0, "motif": 0, "sequence": 0}
    sequence_sessions: dict[str, set[str]] = {}
    for row in rows:
        for symbol in row.get("sequence_evidence", set()):
            sequence_sessions.setdefault(symbol, set()).add(row["session_id"])
    for row in rows:
        relation_keep = set()
        for feature in row.get("relation_evidence", set()):
            rate = frequencies.get(feature, 0) / session_count
            relation_body = feature.split("relation|", 1)[-1]
            left, _, right = relation_body.partition("=>")
            # A pure operation-to-operation relation is structural evidence.
            # It needs much stronger recurrence than a relation containing a
            # data-derived object or problem token.
            structural_operation_relation = left.startswith("op:") and right.startswith("op:")
            max_rate = 0.10 if structural_operation_relation else 0.25
            if rate <= max_rate:
                relation_keep.add(feature)
            else:
                removed["relation"] += 1
        motif_keep = set()
        for feature in row.get("motif_evidence", set()):
            rate = frequencies.get(feature, 0) / session_count
            if rate <= 0.20:
                motif_keep.add(feature)
            else:
                removed["motif"] += 1
        sequence_keep = set()
        for symbol in row.get("sequence_evidence", set()):
            rate = len(sequence_sessions.get(symbol, set())) / session_count
            if rate <= 0.20:
                sequence_keep.add(symbol)
            else:
                removed["sequence"] += 1
        row["relation_evidence"] = relation_keep
        row["motif_evidence"] = motif_keep
        row["sequence_evidence"] = sequence_keep
    return removed


def _candidate_from_members(
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
    members: list[int],
    candidate_number: int,
    conflicts: set[tuple[int, int]],
    stability_threshold: float,
) -> dict[str, Any] | None:
    if len(members) < 2 or _has_conflict(members, conflicts):
        return None
    session_ids = sorted({rows[index]["session_id"] for index in members})
    if len(session_ids) < 2:
        return None

    # A family is allowed to contain some variation.  Requiring an exact
    # intersection across every member made larger, otherwise useful families
    # disappear.  Evidence is retained when it supports a data-derived
    # fraction of the family.
    shared_relations = set(_supporting_features(rows, members, "relation_evidence"))
    shared_motifs = set(_supporting_features(rows, members, "motif_evidence"))
    shared_sequence = set(_supporting_features(rows, members, "sequence_evidence"))
    shared_factors = set(_supporting_features(rows, members, "top_factors"))
    # Factors remain visible for audit, but do not make a candidate pass.
    shared_evidence_count = len(shared_relations) + len(shared_motifs) + len(shared_sequence)
    if shared_evidence_count < 2:
        return None

    pair_values = [matrix[left][right] for offset, left in enumerate(members) for right in members[offset + 1:]]
    density = sum(pair_values) / max(len(pair_values), 1)
    stability = v5._candidate_stability(members, rows, matrix, stability_threshold)
    if stability < 0.35:
        return None
    representative = _representative_indexes(rows, members, matrix)
    return {
        "candidate_id": f"skill-{candidate_number:03d}",
        "representation_unit": "domain_slice",
        "member_slice_ids": [rows[index]["slice_id"] for index in members],
        "member_session_ids": session_ids,
        "size": len(members),
        "distinct_session_count": len(session_ids),
        "shared_motif_count": shared_evidence_count,
        "shared_relation_features": sorted(shared_relations),
        "shared_sequence_features": sorted(shared_motifs),
        "shared_sequence_symbols": sorted(shared_sequence),
        "shared_factor_features": sorted(shared_factors),
        "latent_density": round(density, 8),
        "perturbation_jaccard": stability,
        "representative_slice_ids": [rows[index]["slice_id"] for index in representative],
        "factor_evidence": _supporting_features(rows, members, "top_factors"),
        "sequence_evidence": sorted(shared_sequence),
        "source_event_evidence": [
            {
                "slice_id": rows[index]["slice_id"],
                "session_id": rows[index]["session_id"],
                "first_user_text": rows[index].get("first_user_text", ""),
                "source_paths": _row_source_paths(rows[index]),
                "operations": rows[index].get("operations", []),
            }
            for index in members
        ],
        "capacity_applied": False,
        "nested_candidates_retained": True,
    }


def build_quality_skill_candidates(
    rows: list[dict[str, Any]],
    matrix: list[list[float]],
    cannot_edges: list[dict[str, Any]],
    target_capacity: int,
) -> tuple[list[dict[str, Any]], list[int], dict[str, Any]]:
    """Build overlapping quality candidates directly from one domain's slices."""
    values = [matrix[left][right] for left in range(len(rows)) for right in range(left + 1, len(rows))]
    pressure = _split_pressure(len(rows), target_capacity)
    quantile_cut = pressure["pair_quantile"]
    pair_threshold = v5.quantile(values, quantile_cut) if len(values) >= 3 else 0.0
    # Family growth must remain at the same quality level as its seed pair.
    # The candidate is allowed to grow without a size cap, but weak links are
    # never admitted merely because a family is large.
    growth_quantile = quantile_cut
    growth_threshold = pair_threshold
    conflicts = _conflict_pairs(rows, cannot_edges)
    # Evidence is immutable for this domain.  Cache it once so candidate
    # expansion spends its time evaluating quality, rather than reparsing the
    # same set intersections for every seed family.
    pair_evidence = {
        (left, right): _pair_evidence_count(rows[left], rows[right])
        for left in range(len(rows))
        for right in range(left + 1, len(rows))
    }

    seed_pairs: list[tuple[int, int]] = []
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if rows[left]["session_id"] == rows[right]["session_id"]:
                continue
            pair = (left, right)
            if pair in conflicts or matrix[left][right] < pair_threshold:
                continue
            if pair_evidence[pair] < 2:
                continue
            seed_pairs.append(pair)

    member_sets: set[tuple[int, ...]] = set()
    for left, right in seed_pairs:
        members = [left, right]
        changed = True
        while changed:
            changed = False
            for item in range(len(rows)):
                if item in members or _has_conflict(members, conflicts, item):
                    continue
                scores = [matrix[item][other] for other in members]
                if not scores:
                    continue
                high_support = sum(score >= growth_threshold for score in scores)
                if high_support < max(1, math.ceil(len(scores) * 0.5)):
                    continue
                if sum(scores) / len(scores) < growth_threshold:
                    continue
                if max(pair_evidence[_pair_key(item, other)] for other in members) < 2:
                    continue
                members.append(item)
                changed = True
        member_sets.add(tuple(sorted(members)))

    payload: list[dict[str, Any]] = []
    used: set[int] = set()
    for number, members_tuple in enumerate(sorted(member_sets, key=lambda item: (-len(item), item)), start=1):
        candidate = _candidate_from_members(
            rows,
            matrix,
            list(members_tuple),
            number,
            conflicts,
            pair_threshold,
        )
        if candidate is None:
            continue
        payload.append(candidate)
        used.update(members_tuple)

    return payload, sorted(set(range(len(rows))) - used), {
        "pair_threshold": round(pair_threshold, 8),
        "growth_threshold": round(growth_threshold, 8),
        "pair_quantile": round(quantile_cut, 8),
        "growth_quantile": round(growth_quantile, 8),
        "seed_pair_count": len(seed_pairs),
        "candidate_seed_count": len(member_sets),
        "candidate_count": len(payload),
        "pair_evidence_cache_size": len(pair_evidence),
        "capacity_applied": False,
        "split_pressure": pressure,
    }


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "slice_id": row["slice_id"],
        "session_id": row["session_id"],
        "source_path": row.get("source_path", ""),
        "first_user_text": row.get("first_user_text", ""),
        "event_counts": row.get("event_counts", {}),
        "operations": row.get("operations", []),
        "sequence": row.get("sequence", []),
        "top_factors": row.get("top_factors", []),
        "latent_vector": v5._saveable_vector(row.get("latent_vector", {})),
        "views": {view: v5._saveable_vector(row.get("views", {}).get(view, {})) for view in VIEWS},
        "relation_evidence": sorted(row.get("relation_evidence", set())),
        "motif_evidence": sorted(row.get("motif_evidence", set())),
        "sequence_evidence": sorted(row.get("sequence_evidence", set())),
    }


def _domain_report(domain_id: str, candidates: list[dict[str, Any]], residual: list[str], metadata: dict[str, Any]) -> str:
    lines = [
        f"# {domain_id} V6 domain-local Skill candidates",
        "",
        "This report is generated from this fine domain's slices only. No route-package or cross-domain batching stage is used.",
        "",
        f"- Skill candidates: {len(candidates)}",
        f"- Residual slices: {len(residual)}",
        f"- Pair quantile: {metadata.get('pair_quantile')}",
        f"- Split pressure: {metadata.get('split_pressure', {}).get('pressure')}",
        "",
        "| candidate | slices | sessions | evidence | density | stability |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for candidate in candidates:
        lines.append(
            f"| {candidate['candidate_id']} | {candidate['size']} | {candidate['distinct_session_count']} | "
            f"{candidate['shared_motif_count']} | {candidate['latent_density']} | {candidate['perturbation_jaccard']} |"
        )
    return "\n".join(lines) + "\n"


def run_domain(
    domain: dict[str, Any],
    slices: dict[str, dict[str, Any]],
    card: dict[str, Any] | None,
    output_domain: Path,
    target_capacity: int = 8,
) -> dict[str, Any]:
    """Process exactly one fine domain and its slice members."""
    domain_slice_ids = [sid for sid in domain.get("members", []) if sid in slices]
    domain_slices = {sid: slices[sid] for sid in domain_slice_ids}
    domain_id = domain["domain_id"]
    rows, feature_config = v5.build_global_features(
        domain_slices,
        [domain],
        {domain_id: card} if card else {},
    )
    removed_generic_evidence = _restrict_generic_evidence(rows, feature_config)
    _, latent_config = v5.learn_latent_space(rows, feature_config)
    matrix = v5.build_similarity_matrix(rows)
    cannot_edges, cannot_meta = v5.cannot_link_edges(rows, matrix)
    candidates, residual_indexes, skill_meta = build_quality_skill_candidates(
        rows,
        matrix,
        cannot_edges,
        target_capacity,
    )
    skill_meta["removed_generic_evidence"] = removed_generic_evidence
    residual_slice_ids = [rows[index]["slice_id"] for index in residual_indexes]

    output_domain.mkdir(parents=True, exist_ok=True)
    with (output_domain / "representations.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_serialize_row(row), ensure_ascii=False) + "\n")
    v5.write_json(output_domain / "latent-factors.json", latent_config)
    v5.write_json(output_domain / "skill-candidates.json", {
        "domain_id": domain_id,
        "input_slice_ids": domain_slice_ids,
        "candidates": candidates,
        "residual_slice_ids": residual_slice_ids,
        "metadata": skill_meta,
    })
    (output_domain / "cannot-link.jsonl").write_text(
        "".join(json.dumps(edge, ensure_ascii=False) + "\n" for edge in cannot_edges),
        encoding="utf-8",
    )
    (output_domain / "report.md").write_text(
        _domain_report(domain_id, candidates, residual_slice_ids, skill_meta),
        encoding="utf-8",
    )
    return {
        "domain_id": domain_id,
        "slice_count": len(domain_slice_ids),
        "session_count": len({row["session_id"] for row in rows}),
        "skill_candidate_count": len(candidates),
        "skill_residual_slice_count": len(residual_slice_ids),
        "skill_candidate_max_slices": max((item["size"] for item in candidates), default=0),
        "cannot_link_count": len(cannot_edges),
        "cannot_link_metadata": cannot_meta,
        "feature_count": feature_config.get("feature_count", 0),
        "latent_rank": latent_config.get("rank", 0),
        "split_pressure": skill_meta["split_pressure"],
    }


def run(
    slices_dir: Path,
    domains_path: Path,
    feature_cards_path: Path | None,
    output: Path,
    target_capacity: int = 8,
) -> dict[str, Any]:
    """Invoke the domain-local algorithm once per existing fine domain."""
    slices = v5.load_slices(slices_dir)
    domains = v5.load_domains(domains_path)
    cards = v5.load_cards(feature_cards_path)
    output.mkdir(parents=True, exist_ok=True)

    domain_summaries = []
    total_candidates = 0
    total_residual = 0
    total_slices = set()
    total_sessions = set()
    for domain in domains:
        domain_id = domain["domain_id"]
        summary = run_domain(
            domain,
            slices,
            cards.get(domain_id),
            output / domain_id,
            target_capacity,
        )
        domain_summaries.append(summary)
        total_candidates += summary["skill_candidate_count"]
        total_residual += summary["skill_residual_slice_count"]
        total_slices.update(sid for sid in domain.get("members", []) if sid in slices)
        total_sessions.update(v5.session_id_for_slice(sid) for sid in domain.get("members", []) if sid in slices)

    summary = {
        "algorithm_version": "behavior-logic-clustering-v6-domain-local-quality",
        "invocation_model": "one_domain_slice_set_per_run_domain_call",
        "source_slice_count": len(slices),
        "unique_slice_count": len(total_slices),
        "unique_session_count": len(total_sessions),
        "domain_count": len(domain_summaries),
        "skill_candidate_count": total_candidates,
        "residual_slice_count_sum_over_domains": total_residual,
        "target_capacity_scale": target_capacity,
        "capacity_applied_to_skill_candidates": False,
        "route_packages": None,
        "candidate_membership": "overlapping-and-nested",
        "primary_objective": "minimize_skill_loss_and_preserve_group_quality",
        "domain_isolation": True,
        "no_llm_or_embedding": True,
        "domains": domain_summaries,
    }
    v5.write_json(output / "summary.json", summary)
    v5.write_json(output / "manifest.json", {
        "algorithm_version": summary["algorithm_version"],
        "slices_dir": str(slices_dir.resolve()),
        "domains": str(domains_path.resolve()),
        "feature_cards": str(feature_cards_path.resolve()) if feature_cards_path else None,
        "output": str(output.resolve()),
        "event_channels": ["user_text", "assistant_text", "assistant_thinking", "assistant_reasoning", "tool_call:*"],
        "excluded_channels": ["record:*", "tool_result", "user_image", "metadata"],
        "representation_unit": "domain_slice",
        "domain_processing": "each domain receives only its own slice members; run_domain is called once per domain",
        "skill_discovery": "domain-local overlapping candidate families with evidence and stability gates",
        "capacity_role": "split_pressure_scale_only",
        "split_pressure": "log1p(domain_slice_count / target_capacity), used to adjust domain-local pair quantile",
        "route_packages_removed": True,
        "new_llm_or_embedding_calls": 0,
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--domains", type=Path, required=True)
    parser.add_argument("--feature-cards", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-capacity", dest="target_capacity", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(run(
        args.slices_dir,
        args.domains,
        args.feature_cards,
        args.output,
        args.target_capacity,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
