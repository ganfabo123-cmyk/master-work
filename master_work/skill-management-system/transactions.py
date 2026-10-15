"""Local single-writer boundary shared by the API and management commands."""

from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import os
import threading

_guard = threading.Lock()
_locks = {}


@contextmanager
def writer_lock(root):
    root = Path(root).resolve()
    with _guard:
        lock = _locks.setdefault(os.path.normcase(str(root)), threading.Lock())
    with lock:
        root.mkdir(parents=True, exist_ok=True)
        with (root / "WRITER.lock").open("a+b") as stream:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, 2) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                # Nonblocking acquisition: callers may retry, never silently lose an update.
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise RuntimeError("管理库正在写入，请重试") from exc
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def serialized(operation):
    @wraps(operation)
    def execute(config, *args, **kwargs):
        with writer_lock(config["data_dir"]):
            return operation(config, *args, **kwargs)
    return execute
