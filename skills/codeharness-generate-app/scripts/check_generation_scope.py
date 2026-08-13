from __future__ import annotations

import argparse
from pathlib import Path
import json
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that generation changed only one App and its focused tests.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("mode", choices=("snapshot", "check"))
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    current = {raw[3:].strip().replace("\\", "/") for raw in result.stdout.splitlines()}
    if args.mode == "snapshot":
        args.snapshot.write_text(json.dumps(sorted(current), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(current)} pre-existing worktree paths.")
        return 0
    if not args.snapshot.exists():
        parser.error("snapshot file does not exist; run snapshot before generation")
    baseline = set(json.loads(args.snapshot.read_text(encoding="utf-8")))
    new_changes = current - baseline
    allowed_app = f"src/coworker/apps/{args.app_id}/"
    allowed_test = f"tests/test_{args.app_id}_"
    violations: list[str] = []
    for path in sorted(new_changes):
        if path == "APP_DESIGN.md" or path.startswith(allowed_app) or path.startswith(allowed_test):
            continue
        violations.append(path)
    if violations:
        print("Generation introduced out-of-scope paths:")
        for path in violations:
            print(f"- {path}")
        return 1
    print("Generation scope is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
