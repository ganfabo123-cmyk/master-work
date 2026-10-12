"""Discover domain term groups without a hand-written domain dictionary."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./+-]{2,}")
STRUCTURAL = {
    "the", "and", "for", "from", "with", "that", "this", "your", "have", "will",
    "would", "could", "should", "then", "when", "where", "what", "read", "now",
    "update", "make", "use", "using", "file", "files", "code", "project", "source",
    "true", "false", "null", "json", "text", "path", "name", "value", "output",
}


def tokenize(text: str) -> list[str]:
    terms = [token.lower().strip("._/+-") for token in TOKEN_RE.findall(text)]
    return [term for term in terms if len(term) >= 3 and term not in STRUCTURAL]


def read_slice(path: Path) -> tuple[list[str], Counter[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "token_frequencies" in payload:
        return [], Counter({str(key): int(value) for key, value in payload["token_frequencies"].items()})
    texts = []
    for event in payload.get("events", []):
        category = event.get("category", "")
        if category == "user_text" or category.startswith("tool_call:") or category == "assistant_text":
            for key in ("text", "input_text", "arguments", "tool_name"):
                value = event.get(key)
                if isinstance(value, str):
                    texts.append(value)
    tokens = []
    for text in texts:
        tokens.extend(tokenize(text))
    counts = Counter(tokens)
    # Add adjacent bigrams only from observed tokens; this is still unsupervised.
    for left, right in zip(tokens, tokens[1:]):
        if left != right:
            counts[f"{left}__{right}"] += 1
    return texts, counts


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    norm_left = math.sqrt(sum(value * value for value in left.values()))
    norm_right = math.sqrt(sum(value * value for value in right.values()))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def auto_similarity_threshold(term_vectors: dict[str, dict[int, float]], terms: list[str]) -> float:
    scores = []
    for index, left in enumerate(terms[:300]):
        for right in terms[index + 1:300]:
            score = cosine(term_vectors[left], term_vectors[right])
            if score >= 0.05:
                scores.append(score)
    if len(scores) < 2:
        return 0.55
    scores.sort()
    # Use a data-derived upper-quartile operating point.  The largest-gap
    # rule over-selected the extreme tail and produced almost no domains.
    threshold = scores[min(len(scores) - 1, int(len(scores) * 0.75))]
    return round(min(0.65, max(0.35, threshold)), 6)


def discover(slice_dir: Path, output: Path, max_terms: int, edge_threshold: float,
             min_support: int, min_coverage: float) -> dict:
    paths = sorted(slice_dir.glob("**/*.json"))
    rows = []
    for path in paths:
        slice_id = f"{path.parent.name}__{path.stem}"
        _texts, counts = read_slice(path)
        rows.append((slice_id, counts, str(path)))
    n = len(rows)
    if min_support <= 0:
        # Log-scaled support with a small-sample tolerance.  This avoids
        # deleting compact but repeatable domains in a 97-slice sample.
        min_support = max(3, math.ceil(math.log2(max(2, n))) - 2)
    df = Counter()
    for _slice_id, counts, _path in rows:
        df.update(counts.keys())
    allowed = {
        term for term, frequency in df.items()
        if len(term) >= 3
        and 2 <= frequency <= max(2, int(n * 0.40))
        and not term.isdigit()
        and term.lower() not in STRUCTURAL
    }
    idf = {term: math.log((n + 1) / (df[term] + 1)) + 1.0 for term in allowed}
    vectors = []
    top_terms_by_slice = []
    for _slice_id, counts, _path in rows:
        vector = {term: (1.0 + math.log(count)) * idf[term] for term, count in counts.items() if term in allowed}
        vectors.append(vector)
        top_terms_by_slice.append(sorted(vector, key=vector.get, reverse=True)[:80])
    ranked_terms = sorted(allowed, key=lambda term: sum(vector.get(term, 0.0) for vector in vectors), reverse=True)
    if max_terms <= 0:
        total_mass = sum(sum(vector.get(term, 0.0) for vector in vectors) for term in ranked_terms)
        target = total_mass * 0.90
        running = 0.0
        terms = []
        for term in ranked_terms:
            terms.append(term)
            running += sum(vector.get(term, 0.0) for vector in vectors)
            if running >= target:
                break
        # Keep complete-linkage computationally bounded; the cap is a
        # computational safeguard, not a domain-specific vocabulary.
        terms = terms[:500]
    else:
        terms = ranked_terms[:max_terms]
    if min_coverage <= 0:
        min_coverage = 1.0 / math.sqrt(max(1, len(terms)))
    term_vectors = {}
    for term in terms:
        term_vectors[term] = {index: vector[term] for index, vector in enumerate(vectors) if term in vector}
    # Complete-linkage merging is deliberately non-transitive: a bridge term
    # cannot connect otherwise unrelated domains.
    if edge_threshold < 0:
        edge_threshold = auto_similarity_threshold(term_vectors, terms)
    similarities = {}
    for index, left in enumerate(terms):
        for right in terms[index + 1:]:
            common = len(set(term_vectors[left]) & set(term_vectors[right]))
            score = cosine(term_vectors[left], term_vectors[right]) if common >= 2 else 0.0
            similarities[(left, right)] = score

    groups = [[term] for term in terms]
    while True:
        best = None
        for left_index, left_group in enumerate(groups):
            for right_index in range(left_index + 1, len(groups)):
                right_group = groups[right_index]
                pair_scores = [
                    similarities.get((a, b), similarities.get((b, a), 0.0))
                    for a in left_group for b in right_group
                ]
                score = min(pair_scores) if pair_scores else 0.0
                if score >= edge_threshold and (best is None or score > best[0]):
                    best = (score, left_index, right_index)
        if best is None:
            break
        _score, left_index, right_index = best
        merged = sorted(groups[left_index] + groups[right_index])
        groups = [group for index, group in enumerate(groups) if index not in (left_index, right_index)]
        groups.append(merged)
    groups = [sorted(group, key=lambda term: sum(vector.get(term, 0.0) for vector in vectors), reverse=True)
              for group in groups if len(group) >= 3]
    groups.sort(key=lambda group: (-len(group), group[0]))

    raw_domains = []
    for domain_id, group in enumerate(groups, 1):
        members = []
        coverages = []
        for index, (slice_id, _counts, _path) in enumerate(rows):
            domain_weight = sum(vectors[index].get(term, 0.0) for term in group)
            total_weight = sum(vectors[index].get(term, 0.0) for term in terms)
            coverage = domain_weight / total_weight if total_weight else 0.0
            if domain_weight > 0:
                members.append(slice_id)
                coverages.append(coverage)
        average_coverage = sum(coverages) / len(coverages) if coverages else 0.0
        if len(members) >= min_support and average_coverage >= min_coverage:
            raw_domains.append({
                "domain_id": f"D{len(raw_domains) + 1:03d}",
                "terms": group,
                "support": len(members),
                "average_information_coverage": round(average_coverage, 6),
                "members": members,
            })
    groups = [next(group for group in groups if set(group) == set(domain["terms"])) for domain in raw_domains]
    assignments = {}
    residual_terms = {}
    for index, (slice_id, _counts, _path) in enumerate(rows):
        scores = []
        for domain_id, group in enumerate(groups, 1):
            score = sum(vectors[index].get(term, 0.0) for term in group)
            if score:
                scores.append((score, domain_id))
        scores.sort(reverse=True)
        if scores:
            maximum = scores[0][0]
            assignments[slice_id] = [
                {"domain_id": f"D{domain_id:03d}", "score": round(score / maximum, 6)}
                for score, domain_id in scores if score / maximum >= 0.35
            ][:3]
        else:
            assignments[slice_id] = []
        residual_terms[slice_id] = [
            term for term in sorted(vectors[index], key=vectors[index].get, reverse=True)
            if term not in set(terms)
        ][:20]

    domains = raw_domains
    summary = {"algorithm_version": "unsupervised-domain-graph-v2-auto-params", "slice_count": n,
               "candidate_term_count": len(allowed), "retained_term_count": len(terms),
               "domain_count": len(domains), "unassigned_slice_count": sum(not values for values in assignments.values()),
               "edge_threshold": edge_threshold, "max_terms": max_terms,
               "min_support": min_support, "min_information_coverage": min_coverage}
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "domains.json").write_text(json.dumps(domains, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "assignments.json").write_text(json.dumps(assignments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "residual-terms.json").write_text(json.dumps(residual_terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-terms", type=int, default=0, help="0 = retain 90%% cumulative information mass")
    parser.add_argument("--edge-threshold", type=float, default=-1.0, help="negative = largest-gap calibration")
    parser.add_argument("--min-support", type=int, default=0, help="0 = ceil(log2(slice_count))")
    parser.add_argument("--min-coverage", type=float, default=0.0, help="0 = 1/sqrt(retained_term_count)")
    args = parser.parse_args()
    print(json.dumps(discover(args.slice_dir, args.output, args.max_terms, args.edge_threshold,
                              args.min_support, args.min_coverage), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
