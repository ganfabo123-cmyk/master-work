"""JSONL bridge for the DSH skill-hint plugin.

The bridge deliberately exposes only the existing ``AgentSession`` retrieval
entrypoint. It is a transport seam, not a second retrieval implementation.
One request is read from stdin and one JSON response is written to stdout.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from api import EmbeddingApiClient, EmbeddingApiConfig, SkillSystem
from manager import load_config
from runtime_audit import RuntimeAudit, audit_context, embedding_unavailable
import traceback
import uuid


def _log_ingress(audit, request):
    messages = request.get('messages', [])
    audit.emit('bridge_request_received', config_path=request.get('config_path'),
               message_count=len(messages) if isinstance(messages, list) else None)
    if isinstance(messages, list):
        for index, raw in enumerate(messages):
            audit.emit('bridge_trace_received', input_index=index, raw_trace=raw)
    else:
        audit.emit('bridge_invalid_messages', raw_messages=messages)


def _load_dotenv(root: Path) -> dict[str, str]:
    """Read local non-secret dotenv values without overriding the process env."""
    values: dict[str, str] = {}
    candidates = (root / ".env", root.parent / "dynamic-retrieval-test" / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip("\"'")
            values.setdefault(key.strip(), value)
    return values


def _embedding(request: dict[str, Any]) -> EmbeddingApiClient | None:
    root = Path(str(request["management_root"])).expanduser().resolve()
    dotenv = _load_dotenv(root)
    raw = request.get("embedding") or {}
    endpoint = str(raw.get("endpoint") or os.getenv("SKILL_EMBEDDING_ENDPOINT")
                   or os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_API_URL")
                   or dotenv.get("SKILL_EMBEDDING_ENDPOINT")
                   or dotenv.get("DYNAMIC_RETRIEVAL_EMBEDDING_API_URL", "")).strip()
    model = str(raw.get("model") or os.getenv("SKILL_EMBEDDING_MODEL")
                or os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_MODEL")
                or dotenv.get("SKILL_EMBEDDING_MODEL")
                or dotenv.get("DYNAMIC_RETRIEVAL_EMBEDDING_MODEL", "")).strip()
    if not endpoint or not model:
        return None
    api_key = (raw.get("api_key") or os.getenv("SKILL_EMBEDDING_API_KEY")
               or os.getenv("DYNAMIC_RETRIEVAL_EMBEDDING_API_KEY")
               or dotenv.get("SKILL_EMBEDDING_API_KEY")
               or dotenv.get("DYNAMIC_RETRIEVAL_EMBEDDING_API_KEY"))
    return EmbeddingApiClient(EmbeddingApiConfig(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        timeout_seconds=float(raw.get("timeout_seconds", 60.0)),
        use_system_proxy=bool(raw.get("use_system_proxy", False)),
    ))


def handle(request: dict[str, Any]) -> dict[str, Any]:
    with audit_context(request_id=uuid.uuid4().hex):
        root = Path(str(request.get('management_root', Path(__file__).parent))).expanduser().resolve()
        config_path = Path(request.get('config_path') or root/'config.json').resolve()
        try:
            config = load_config(config_path)
        except Exception as exc:
            audit = RuntimeAudit(root/'data')
            _log_ingress(audit, request)
            audit.emit('bridge_failed', stage='configuration', error_type=type(exc).__name__,
                       error=str(exc), embedding=embedding_unavailable('configuration_failed'))
            raise
        audit = RuntimeAudit(config['data_dir'])
        _log_ingress(audit, request)
        try:
            response = _handle(request, config)
            audit.emit('bridge_completed', status=response['status'],
                       has_results=bool(response['items']), returned_count=len(response['messages']))
            return response
        except Exception as exc:
            audit.emit('bridge_failed', error_type=type(exc).__name__, error=str(exc),
                       traceback=traceback.format_exc())
            raise


def _handle(request: dict[str, Any], config: dict) -> dict[str, Any]:
    root = Path(str(request["management_root"])).expanduser().resolve()
    config_path = request.get("config_path")
    system = SkillSystem(config=config,
                         embedding=_embedding(request))
    session = system.agent_session(retrieval_options=dict(request.get("retrieval_options") or {}))
    messages = list(request.get("messages", []))
    returned_messages, result = session.handle_messages(messages)
    items = []
    for hit in result.items:
        item = {
            "name": hit.document.title,
            "skill_id": hit.document.document_id,
            "description": hit.document.retrieval_content,
            "source_path": hit.document.source_path,
            "metadata": hit.metadata,
            "rank": hit.rank,
            "score": hit.score,
        }
        items.append(item)
    return {
        "status": result.status.value,
        "reason": result.reason,
        "items": items,
        "metadata": result.metadata,
        "query": result.query.query_text if result.query else None,
        "messages": returned_messages,
    }


def main() -> int:
    request = None
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            RuntimeAudit(Path(__file__).parent/'data').emit('bridge_invalid_input',
                input_type=type(request).__name__, raw_request=request,
                embedding=embedding_unavailable('request_must_be_object'))
            raise ValueError('bridge request must be an object')
        response = handle(request)
    except Exception as error:  # bridge errors are returned as structured data
        if request is None:
            RuntimeAudit(Path(__file__).parent/'data').emit('bridge_invalid_input',
                error_type=type(error).__name__, error=str(error),
                embedding=embedding_unavailable('invalid_json'))
        response = {"status": "error", "error": f"{type(error).__name__}: {error}"}
    sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
