"""Flask application and HTTP routes for the CoWorker web console."""

from __future__ import annotations

from importlib import import_module
from inspect import isclass
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4
import json

from flask import Flask, jsonify, request, send_from_directory

from .core.base_environment import Environment
from .core.models import Task
from .infra.runtimes import SessionRuntime
from .infra.trace import TraceRecorder


def environment_type(app_name: str) -> type[Environment]:
    """Resolve the unique Environment implementation exported by one App."""
    if not app_name.isidentifier():
        raise ValueError(f"App 未找到：{app_name}")
    module_name = f"{__package__}.apps.{app_name}.environment"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name == module_name or error.name == f"{__package__}.apps.{app_name}":
            raise ValueError(f"App 未找到：{app_name}") from None
        raise
    candidates = [
        value
        for value in vars(module).values()
        if isclass(value)
        and value is not Environment
        and issubclass(value, Environment)
        and value.__module__ == module.__name__
    ]
    if len(candidates) != 1 or not callable(getattr(candidates[0], "from_environment", None)):
        raise ValueError(f"App 未找到：{app_name}")
    return candidates[0]


def discover_apps() -> list[dict[str, str]]:
    """Discover valid apps/<app_name>/environment.py modules for the Web market."""
    apps_root = Path(__file__).resolve().parent / "apps"
    discovered: list[dict[str, str]] = []
    for environment_path in sorted(apps_root.glob("*/environment.py")):
        app_name = environment_path.parent.name
        try:
            resolved_type = environment_type(app_name)
        except (ImportError, ValueError):
            continue
        description = " ".join((resolved_type.__doc__ or "CoWorker application workflow.").split())
        discovered.append({"name": app_name, "display_name": app_name.replace("_", " ").title(), "description": description})
    return discovered


def create_environment(app_name: str, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data")) -> Any:
    """Construct one configured application Environment by its CLI name."""
    return environment_type(app_name).from_environment(traces_root=traces_root, room_data_root=room_data_root)


class JobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self, app_name: str) -> str:
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"job_id": job_id, "app_name": app_name, "status": "running", "session_id": None, "content": None, "error": None}
        return job_id

    def update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(values)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None


def create_app(
    *,
    app_name: str = "incident_consultation",
    traces_root: Path = Path("traces"),
    room_data_root: Path = Path("room/data"),
    frontend_root: Path | None = None,
) -> Flask:
    frontend = frontend_root or Path(__file__).resolve().parents[2] / "frontend"
    app = Flask(__name__)
    jobs = JobStore()

    @app.get("/")
    def index() -> Any:
        return send_from_directory(frontend, "index.html")

    @app.get("/api/apps")
    def get_apps() -> Any:
        return jsonify({"apps": discover_apps(), "default_app": app_name})

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str) -> Any:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Job does not exist"}), 404
        return jsonify(job)

    @app.get("/api/sessions/<session_id>")
    def get_session(session_id: str) -> Any:
        try:
            return jsonify(session_snapshot(traces_root, room_data_root, session_id))
        except KeyError as error:
            return jsonify({"error": str(error)}), 404
        except json.JSONDecodeError:
            return jsonify({"error": "Session snapshot is temporarily unavailable; retry shortly."}), 503

    @app.post("/api/run")
    def run_task() -> Any:
        payload = request.get_json(silent=True) or {}
        content = payload.get("content")
        session_id = payload.get("session_id")
        selected_app = payload.get("app_name", app_name)
        if not isinstance(content, str) or not content.strip():
            return jsonify({"error": "content is required"}), 400
        if session_id is not None and not isinstance(session_id, str):
            return jsonify({"error": "session_id must be a string"}), 400
        if not isinstance(selected_app, str):
            return jsonify({"error": "app_name must be a string"}), 400
        try:
            environment_type(selected_app)
        except ValueError as error:
            return jsonify({"error": str(error)}), 404
        job_id = jobs.create(selected_app)
        Thread(
            target=_run_job,
            args=(jobs, job_id, selected_app, traces_root, room_data_root, content.strip(), session_id or None),
            daemon=True,
        ).start()
        return jsonify({"job_id": job_id, "status": "running"}), 202

    return app


def _run_job(
    jobs: JobStore,
    job_id: str,
    app_name: str,
    traces_root: Path,
    room_data_root: Path,
    content: str,
    session_id: str | None,
) -> None:
    try:
        environment = create_environment(app_name, traces_root=traces_root, room_data_root=room_data_root)
        result = SessionRuntime(trace=environment.session.trace).run(
            environment,
            task=Task(content),
            session_id=session_id,
            on_session_opened=lambda opened_session_id: jobs.update(job_id, session_id=opened_session_id),
        )
        jobs.update(
            job_id,
            status=result.status,
            session_id=result.session_id,
            content=result.content.content if result.content is not None else None,
            error=result.error,
        )
    except Exception as error:
        jobs.update(job_id, status="failed", error=str(error))


def session_snapshot(traces_root: Path, room_data_root: Path, session_id: str) -> dict[str, Any]:
    session_path = traces_root / session_id / "session.json"
    if not session_path.exists():
        raise KeyError(f"Session does not exist: {session_id}")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    room_metas = session.get("rooms")
    if not isinstance(room_metas, list):
        room_metas = [session["room"]] if isinstance(session.get("room"), dict) else []
    rooms: list[dict[str, Any]] = []
    recorder = TraceRecorder(traces_root)
    for metadata in room_metas:
        if not isinstance(metadata, dict):
            continue
        room_id, room_session_id = metadata.get("room_id"), metadata.get("session_id")
        if not isinstance(room_id, str) or not isinstance(room_session_id, str):
            continue
        room_path = room_data_root / room_session_id / "rooms" / f"{room_id}.json"
        if not room_path.exists():
            continue
        room = json.loads(room_path.read_text(encoding="utf-8"))
        room["messages"] = [message.model_dump(mode="json") for message in recorder.room_messages(session_id, room_id)]
        rooms.append(room)
    declared_public = session.get("public_room_id")
    selected = next((room for room in rooms if room.get("room_id") == declared_public), None)
    selected = selected or next((room for room in rooms if "public" in str(room.get("room_id"))), rooms[0] if rooms else None)
    profiles: dict[str, Any] = {}
    for room in rooms:
        room_session_id = room.get("session_id")
        if not isinstance(room_session_id, str):
            continue
        for name in room.get("participants", []):
            if not isinstance(name, str):
                continue
            profile_path = room_data_root / room_session_id / "agents" / f"{name}.json"
            if profile_path.exists():
                profiles[name] = json.loads(profile_path.read_text(encoding="utf-8"))
    return {"session": session, "room": selected, "rooms": rooms, "profiles": profiles}


def serve_web(*, app_name: str = "incident_consultation", host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the Flask development server for the local console."""
    print(f"CoWorker Web ({app_name}): http://{host}:{port}")
    create_app(app_name=app_name).run(host=host, port=port, threaded=True)
