#!/usr/bin/env python3
"""Build LLM-facing feature cards for complete-session domain clusters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_member(member: str) -> str:
    value = member.removeprefix("segments__")
    return value


def load_term_support(token_root: Path) -> dict[str, int]:
    support: dict[str, int] = {}
    for path in token_root.glob("*.json"):
        payload = read(path)
        for token in payload.get("token_frequencies", {}):
            support[token] = support.get(token, 0) + 1
    return support


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domains", type=Path, required=True)
    parser.add_argument("--raw-session-inputs", type=Path, required=True)
    parser.add_argument("--session-token-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    domains = read(args.domains)
    term_support = load_term_support(args.session_token_dir)
    cards = []
    for domain in domains:
        members = [normalize_member(member) for member in domain.get("members", [])]
        terms = list(domain.get("terms", []))
        cards.append({
            "cluster_id": domain["domain_id"],
            "core_terms": terms[:12],
            "top_terms_by_frequency": terms[:20],
            "term_support_count": {term: term_support.get(term, 0) for term in terms[:20]},
            # Raw session user fields contain repeated synthetic context in this
            # dataset, so omitting them is safer than presenting them as intent.
            "representative_first_user_inputs": [],
            "support": domain.get("support", len(members)),
            "session_count": len(members),
            "information_coverage": domain.get("average_information_coverage", 0.0),
            "member_session_ids": members,
        })
    output = {
        "algorithm_version": "session-domain-feature-cards-v1",
        "source_domains": str(args.domains),
        "cluster_count": len(cards),
        "cards": cards,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "domain-feature-cards.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "summary.json").write_text(
        json.dumps({"cluster_count": len(cards), "card_fields": list(cards[0]) if cards else []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"cluster_count": len(cards), "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
