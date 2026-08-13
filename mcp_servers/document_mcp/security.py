"""Read-only path validation for local MCP tools."""

from __future__ import annotations

import os
from pathlib import Path


class PathAccessError(ValueError):
    pass


def allowed_roots() -> tuple[Path, ...]:
    candidates = [Path.cwd()]
    claude_root = os.getenv("CLAUDE_PROJECT_DIR")
    if claude_root:
        candidates.append(Path(claude_root))
    configured = os.getenv("DOCUMENT_MCP_ROOTS", "")
    candidates.extend(Path(value) for value in configured.split(os.pathsep) if value.strip())
    roots: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def resolve_readable_file(path: str, *, suffixes: set[str]) -> Path:
    candidate = Path(path).expanduser().resolve()
    if not any(candidate == root or root in candidate.parents for root in allowed_roots()):
        raise PathAccessError(f"path is outside allowed roots: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"file does not exist: {candidate}")
    if candidate.suffix.lower() not in suffixes:
        allowed = ", ".join(sorted(suffixes))
        raise PathAccessError(f"unsupported file type {candidate.suffix!r}; allowed: {allowed}")
    return candidate
