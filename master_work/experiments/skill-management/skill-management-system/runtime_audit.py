"""Durable, correlated diagnostics independent of management snapshot commits."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import math
import os
from pathlib import Path
import time
import traceback
import uuid

from transactions import writer_lock

_context = ContextVar('runtime_audit_context', default={})
_attempt = ContextVar('runtime_audit_attempt', default=None)
_sensitive = {'api_key', 'apikey', 'authorization', 'password', 'secret', 'access_token'}


def redact(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if str(k).lower() in _sensitive else redact(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


@contextmanager
def audit_context(**fields):
    token = _context.set(dict(_context.get(), **fields))
    try:
        yield
    finally:
        _context.reset(token)


def embedding_unavailable(reason):
    return {'status': 'unavailable', 'reason': reason, 'top_similarity': None,
            'candidates': []}


class RuntimeAudit:
    def __init__(self, data_dir):
        self.directory = Path(data_dir) / 'logs'
        self.path = self.directory / 'runtime.jsonl'

    def emit(self, event, **fields):
        now = datetime.now(timezone.utc)
        record = dict(version=1, ts=now.isoformat(),
                      local_time=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
                      event=event, **_context.get())
        record.update(redact(fields))
        line = json.dumps(record, ensure_ascii=False, allow_nan=False, default=str) + '\n'
        # A separate lock directory avoids deadlock with snapshot writes. Retry only
        # lock acquisition, never a write that might already have appended a line.
        deadline = time.monotonic() + 5
        lock = None
        while lock is None:
            candidate = writer_lock(self.directory)
            try:
                candidate.__enter__()
                lock = candidate
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.01)
        try:
            with self.path.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            lock.__exit__(None, None, None)


def record_embedding(audit, details):
    attempt = _attempt.get()
    while attempt is not None:
        attempt['embedding'] = details
        attempt = attempt.get('parent')
    audit.emit('embedding_similarity', embedding=details)


@contextmanager
def embedding_state():
    state = {'embedding': embedding_unavailable('not_evaluated'), 'parent': _attempt.get()}
    token = _attempt.set(state)
    try:
        yield state
    finally:
        _attempt.reset(token)


def audited_retrieval(operation):
    @wraps(operation)
    def execute(self, query, **options):
        started = time.monotonic()
        state = {'embedding': embedding_unavailable('embedding_not_started'), 'parent': _attempt.get()}
        token = _attempt.set(state)
        with audit_context(retrieval_id=uuid.uuid4().hex):
            try:
                self.audit.emit('retrieval_started', query=query,
                                parameters={"min_similarity": .5, "top_k": 3, "tau": .5, "m": 1,
                                            "signature_audit_rate": .1, **options})
                result = operation(self, query, **options)
                self.audit.emit('retrieval_completed', success=True,
                                has_results=bool(result['items']), items=[
                                    {k: hit.get(k) for k in ('skill_id','name','score','rank','node_id','source_path')}
                                    for hit in result['items']],
                                channel=result['channel'], embedding=state['embedding'],
                                published_generation=result['published_generation'],
                                elapsed_ms=round((time.monotonic()-started)*1000, 3))
                return result
            except Exception as exc:
                self.audit.emit('retrieval_failed', success=False, has_results=False,
                                error_type=type(exc).__name__, error=str(exc),
                                traceback=traceback.format_exc(), embedding=state['embedding'],
                                elapsed_ms=round((time.monotonic()-started)*1000, 3))
                raise
            finally:
                _attempt.reset(token)
    return execute
