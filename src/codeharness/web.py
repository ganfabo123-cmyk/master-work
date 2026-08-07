"""Local, scenario-neutral Web view for CodeHarness sessions and ROOM messages."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.parse import unquote, urlparse
from uuid import uuid4

from .models import Task
from .orchestrator import Orchestrator
from .trace import TraceRecorder


def serve_web(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the local ROOM console until interrupted by the user."""
    handler = _handler_factory(Path("traces"), Path("room/data"))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"CodeHarness Web: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _handler_factory(traces_root: Path, room_data_root: Path) -> type[BaseHTTPRequestHandler]:
    jobs = _JobStore()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self._send_text(HTTPStatus.OK, _PAGE, "text/html; charset=utf-8")
                return
            if path.startswith("/api/sessions/"):
                session_id = unquote(path.removeprefix("/api/sessions/"))
                try:
                    self._send_json(HTTPStatus.OK, _session_snapshot(traces_root, room_data_root, session_id))
                except KeyError as error:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Session snapshot is temporarily unavailable; retry shortly."})
                return
            if path.startswith("/api/jobs/"):
                job_id = unquote(path.removeprefix("/api/jobs/"))
                job = jobs.get(job_id)
                if job is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Job does not exist"})
                else:
                    self._send_json(HTTPStatus.OK, job)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/run":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                content = payload.get("content")
                session_id = payload.get("session_id")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("content is required")
                if session_id is not None and not isinstance(session_id, str):
                    raise ValueError("session_id must be a string")
                job_id = jobs.create()
                Thread(
                    target=_run_job,
                    args=(jobs, job_id, traces_root, room_data_root, content.strip(), session_id or None),
                    daemon=True,
                ).start()
                self._send_json(HTTPStatus.ACCEPTED, {"job_id": job_id, "status": "running"})
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            self._send_text(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

        def _send_text(self, status: HTTPStatus, content: str, content_type: str) -> None:
            encoded = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


class _JobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self) -> str:
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"job_id": job_id, "status": "running", "session_id": None, "content": None, "error": None}
        return job_id

    def update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None


def _run_job(
    jobs: _JobStore,
    job_id: str,
    traces_root: Path,
    room_data_root: Path,
    content: str,
    session_id: str | None,
) -> None:
    try:
        orchestrator = Orchestrator.from_environment(traces_root=traces_root, room_data_root=room_data_root)
        result = orchestrator.run(
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


def _session_snapshot(traces_root: Path, room_data_root: Path, session_id: str) -> dict[str, Any]:
    session_path = traces_root / session_id / "session.json"
    if not session_path.exists():
        raise KeyError(f"Session does not exist: {session_id}")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    room_metas = session.get("rooms")
    if not isinstance(room_metas, list):
        room_metas = [session["room"]] if isinstance(session.get("room"), dict) else []
    rooms: list[dict[str, Any]] = []
    for room_meta in room_metas:
        if not isinstance(room_meta, dict) or not isinstance(room_meta.get("session_id"), str) or not isinstance(room_meta.get("room_id"), str):
            continue
        room_path = room_data_root / room_meta["session_id"] / "rooms" / f"{room_meta['room_id']}.json"
        if room_path.exists():
            room = json.loads(room_path.read_text(encoding="utf-8"))
            room["messages"] = [
                message.model_dump(mode="json")
                for message in TraceRecorder(traces_root).room_messages(session_id, room_meta["room_id"])
            ]
            rooms.append(room)
    declared_public_room_id = session.get("public_room_id")
    room = next(
        (candidate for candidate in rooms if candidate.get("room_id") == declared_public_room_id),
        next((candidate for candidate in rooms if "public" in str(candidate.get("room_id"))), rooms[0] if rooms else None),
    )
    visible_rooms = [room] if room is not None else []
    profiles: dict[str, Any] = {}
    for candidate in visible_rooms:
        room_session_id = candidate.get("session_id")
        if isinstance(room_session_id, str):
            for name in candidate.get("participants", []):
                if isinstance(name, str):
                    profile_path = room_data_root / room_session_id / "agents" / f"{name}.json"
                    if profile_path.exists():
                        profiles[name] = json.loads(profile_path.read_text(encoding="utf-8"))
    return {"session": session, "room": room, "rooms": visible_rooms, "profiles": profiles}


_PAGE = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><title>CodeHarness ROOM</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#ededed;color:#111;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.app{width:min(760px,100vw);height:100vh;margin:auto;background:#f5f5f5;display:flex;flex-direction:column;box-shadow:0 0 30px #bbb}.head{height:58px;flex:none;background:#f7f7f7;border-bottom:1px solid #ddd;display:flex;align-items:center;padding:0 18px;gap:12px}.group-avatar{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#46a2ff,#7867e6);display:grid;place-items:center;color:#fff;font-weight:700}.title{font-size:16px;font-weight:600}.subtitle{font-size:12px;color:#888;margin-top:2px}.members{margin-left:auto;display:flex}.mini{width:25px;height:25px;border-radius:50%;border:2px solid #f7f7f7;margin-left:-6px;color:#fff;display:grid;place-items:center;font-size:10px;font-weight:700}.chat{flex:1;overflow:auto;padding:18px 16px;background:#f5f5f5}.empty{text-align:center;color:#aaa;margin-top:60px}.line{display:flex;gap:10px;margin:14px 0;align-items:flex-start}.line.self{flex-direction:row-reverse}.avatar{width:39px;height:39px;flex:none;border-radius:7px;color:#fff;display:grid;place-items:center;font-weight:700}.agent-button{border:0;padding:0;background:transparent;cursor:pointer}.agent-button:hover{filter:brightness(.9);transform:scale(1.04)}.body{max-width:75%}.name{font-size:12px;color:#888;margin:0 0 4px 2px}.self .name{text-align:right;margin-right:2px}.bubble{white-space:pre-wrap;word-break:break-word;line-height:1.55;background:#fff;border-radius:5px;padding:9px 11px;box-shadow:0 1px 1px #ddd}.self .bubble{background:#95ec69}.time{font-size:11px;color:#aaa;margin-top:4px}.self .time{text-align:right}.compose{flex:none;border-top:1px solid #ddd;background:#f7f7f7;padding:10px 14px}.compose-row{display:flex;gap:9px;align-items:flex-end}textarea{width:100%;height:62px;resize:none;border:0;border-radius:5px;padding:10px;font:inherit;outline:none;background:#fff}button{border:0;border-radius:4px;background:#07c160;color:#fff;padding:10px 14px;font:inherit;cursor:pointer}button:disabled{opacity:.55}.status{font-size:12px;color:#888;margin:7px 0 0}.details{flex:none;background:#fff;border-top:1px solid #ddd;color:#666}.details summary{cursor:pointer;padding:8px 14px}.details input{width:100%;border:1px solid #ddd;border-radius:4px;padding:7px}.details pre{max-height:130px;overflow:auto;margin:0;padding:0 14px 10px;font-size:11px;white-space:pre-wrap}dialog{border:0;border-radius:12px;padding:0;max-width:360px;width:calc(100vw - 42px);box-shadow:0 12px 45px #333}dialog::backdrop{background:#0008}.profile{padding:20px}.profile-top{display:flex;gap:12px;align-items:center}.profile-title{font-size:17px;font-weight:700}.profile-role{color:#777;margin-top:3px}.profile dl{margin:18px 0 0}.profile dt{font-size:12px;color:#888;margin-top:12px}.profile dd{margin:4px 0;white-space:pre-wrap;word-break:break-word}.profile button{float:right;background:#eee;color:#333}@media(max-width:760px){.app{width:100%}}
</style><div class="app"><header class="head"><div class="group-avatar">CH</div><div><div class="title">CodeHarness ROOM</div><div class="subtitle" id="subtitle">等待创建群聊</div></div><div class="members" id="memberAvatars"></div></header><main class="chat" id="messages"><div class="empty">发送一条请求，Agent 的 ROOM 对话会显示在这里</div></main><footer class="compose"><div class="compose-row"><textarea id="content" placeholder="直接输入你的任务或问题"></textarea><button id="run">发送</button></div><div class="status" id="result">前端只负责传话，Orchestrator 决定协作方式。</div></footer><details class="details"><summary>会话详情与恢复</summary><label>Session ID（留空创建新会话）</label><input id="session" placeholder="session_..."><pre id="sessionData">尚未加载</pre></details></div>
<dialog id="profileDialog"><div class="profile" id="profileContent"></div></dialog><script>
const $=id=>document.getElementById(id);let profiles={};const colors=['#4f8cff','#f28b54','#7e6ce0','#17a673','#d56b91','#a8793e'];function esc(v){const d=document.createElement('div');d.textContent=v;return d.innerHTML}function label(name){return profiles[name]?.display_name||name}function identity(name){let n=0;for(const c of name)n+=c.charCodeAt(0);return {label:(name||'?').slice(0,2).toUpperCase(),color:colors[n%colors.length]}}function avatar(name,small=false){const a=identity(label(name));return `<button class="agent-button" data-agent="${esc(name)}" title="查看 ${esc(label(name))} 的资料"><span class="${small?'mini':'avatar'}" style="background:${a.color}">${esc(a.label)}</span></button>`}function recipients(at){return Array.isArray(at)?at.map(label).join('、'):label(at)}function isNearBottom(node){return node.scrollHeight-node.scrollTop-node.clientHeight<72}function render(data){const chat=$('messages');const follow=isNearBottom(chat);profiles=data.profiles||{};$('sessionData').textContent=JSON.stringify(data.session,null,2);const room=data.room;if(!room){$('subtitle').textContent='此 session 暂无 ROOM';$('memberAvatars').textContent='';chat.innerHTML='<div class="empty">等待 Agent 加入 ROOM</div>';return}const people=room.participants||[];$('subtitle').textContent=`${people.length} 位 Agent 正在群聊`;$('memberAvatars').innerHTML=people.map(n=>avatar(n,true)).join('');const list=room.messages||[];chat.innerHTML=list.length?list.map(m=>{const self=m.name==='user';const at=recipients(m.at);return `<article class="line ${self?'self':''}">${avatar(m.name)}<div class="body"><div class="name">${esc(label(m.name))}${at==='all'?'':' → '+esc(at)}</div><div class="bubble">${esc(m.txt||'[非文本消息]')}</div><div class="time">${new Date(m.created_at).toLocaleTimeString()}</div></div></article>`}).join(''):'<div class="empty">Agent 已加入，等待第一条消息</div>';if(follow)chat.scrollTop=chat.scrollHeight}function showProfile(name){const p=profiles[name];if(!p){$('profileContent').innerHTML=`<button onclick="profileDialog.close()">关闭</button><div class="profile-title">${esc(name)}</div><p>此发送者没有可用的 ROOM Profile。</p>`}else{$('profileContent').innerHTML=`<button onclick="profileDialog.close()">关闭</button><div class="profile-top">${avatar(name)}<div><div class="profile-title">${esc(label(name))}</div><div class="profile-role">${esc(p.role||'agent')}</div></div></div><dl><dt>Agent ID</dt><dd>${esc(p.name)}</dd><dt>介绍</dt><dd>${esc(p.introduction||'—')}</dd><dt>技能</dt><dd>${esc((p.skill||[]).join('、')||'—')}</dd><dt>扩展信息</dt><dd>${esc(JSON.stringify(p.kwargs||{},null,2))}</dd></dl>`}$('profileDialog').showModal()}document.addEventListener('click',event=>{const target=event.target.closest('[data-agent]');if(target)showProfile(target.dataset.agent)});function showFinal(content){const chat=$('messages');const follow=isNearBottom(chat);const item=document.createElement('article');item.className='line';item.innerHTML=avatar('Orchestrator')+`<div class="body"><div class="name">Orchestrator · 最终回复</div><div class="bubble">${esc(content||'[无最终文本]')}</div></div>`;chat.append(item);if(follow)chat.scrollTop=chat.scrollHeight}async function load(id){const r=await fetch('/api/sessions/'+encodeURIComponent(id));const data=await r.json();if(!r.ok)throw Error(data.error);render(data)}async function watch(jobId,button){const r=await fetch('/api/jobs/'+jobId);const job=await r.json();if(!r.ok)throw Error(job.error);if(job.session_id){$('session').value=job.session_id;await load(job.session_id)}if(job.status==='running'){setTimeout(()=>watch(jobId,button),700);return}button.disabled=false;if(job.status==='failed')throw Error(job.error||'run failed');$('result').textContent='协作完成';showFinal(job.content);$('content').value=''}$('run').onclick=async()=>{const button=$('run');button.disabled=true;$('result').textContent='Orchestrator 正在运行，群聊会自动刷新…';try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:$('content').value,session_id:$('session').value||null})});const data=await r.json();if(!r.ok)throw Error(data.error||'run failed');await watch(data.job_id,button)}catch(e){$('result').textContent='Error: '+e.message;button.disabled=false}};$('session').onchange=async()=>{if($('session').value)try{await load($('session').value)}catch(e){$('result').textContent='Error: '+e.message}};
</script><script>
let activeRooms=[],activeRoomId=null,lastSnapshot=null;
function render(data){const chat=$('messages');const follow=isNearBottom(chat);lastSnapshot=data;profiles=data.profiles||{};activeRooms=data.rooms||[];const room=activeRooms.find(item=>item.room_id===activeRoomId)||activeRooms.find(item=>String(item.room_id).includes('public'))||data.room;if(!room){$('subtitle').textContent='此 session 暂无 ROOM';$('memberAvatars').textContent='';chat.innerHTML='<div class="empty">等待 Agent 加入 ROOM</div>';return}activeRoomId=room.room_id;let selector=$('roomSelector');if(!selector){selector=document.createElement('select');selector.id='roomSelector';selector.style.cssText='margin-left:auto;border:1px solid #ddd;border-radius:4px;padding:6px;background:#fff';$('memberAvatars').before(selector)}selector.innerHTML=activeRooms.map(item=>`<option value="${esc(item.room_id)}">${esc(item.room_id)}</option>`).join('');selector.value=room.room_id;selector.onchange=()=>{activeRoomId=selector.value;render(lastSnapshot)};$('sessionData').textContent=JSON.stringify(data.session,null,2);const people=room.participants||[];$('subtitle').textContent=`${room.room_id} · ${people.length} 位 Agent`;$('memberAvatars').innerHTML=people.map(n=>avatar(n,true)).join('');const list=room.messages||[];chat.innerHTML=list.length?list.map(m=>{const self=m.name==='user';const at=recipients(m.at);return `<article class="line ${self?'self':''}">${avatar(m.name)}<div class="body"><div class="name">${esc(label(m.name))}${at==='all'?'':' → '+esc(at)}</div><div class="bubble">${esc(m.txt||'[非文本消息]')}</div><div class="time">${new Date(m.created_at).toLocaleTimeString()}</div></div></article>`}).join(''):'<div class="empty">Agent 已加入，等待第一条消息</div>';if(follow)chat.scrollTop=chat.scrollHeight}
</script></html>"""
