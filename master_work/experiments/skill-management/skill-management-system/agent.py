"""Agent Trace entrypoint with replaceable trigger and query strategies."""

from agent_protocol import (Trajectory, RetrievalQuery, RetrievalDocument, RetrievalHit,
    RetrievalResult, RetrievalStatus, process_raw_trace, developer_trace_converter,
    developer_should_retrieve, developer_build_query)
from pathlib import Path
import traceback
import uuid
from agent_protocol import _content_to_text
from runtime_audit import audit_context, embedding_state, embedding_unavailable, record_embedding


def build_skill_hint(result: RetrievalResult) -> str | None:
    """Render the model-facing user-input hint from managed retrieval hits."""
    entries = []
    seen = set()
    for hit in result.items:
        source_path = hit.document.source_path
        if not source_path:
            continue
        path = str(Path(source_path).expanduser().resolve())
        if path not in seen:
            seen.add(path)
            entries.append((hit.document.title or hit.document.document_id or "managed skill",
                            path, hit.document.retrieval_content.strip()))
    if not entries:
        return None
    lines = ["检测到当前上下文命中知识库中的知识。系统自动推荐以下 skill，你可以选择查看其 SKILL.md，以辅助完成当前任务：",
             "如果要查看以下推荐的 skill，不要调用 skill 工具；请直接调用 read 工具，读取对应绝对路径下的 SKILL.md 文件。"]
    for name, path, description in entries:
        lines.extend([f"- {name}", f"  路径：{path}", f"  description：{description}"])
    return "\n".join(lines)


class AgentSession:
    """Create one session per Agent conversation; the SkillSystem may be shared."""

    def __init__(self, system, *, trace_converter=developer_trace_converter,
                 trigger_strategy=developer_should_retrieve, query_builder=developer_build_query,
                 retrieval_options=None):
        self.system = system
        self.audit = system.audit
        self.trace_converter = trace_converter
        self.trigger_strategy = trigger_strategy
        self.query_builder = query_builder
        self.retrieval_options = dict(retrieval_options or {})
        self.trajectory = Trajectory()

    def feedback(self, **rating):
        return self.system.feedback(**rating)

    def handle_messages(self, messages):
        """Return messages with a hint from the last triggered retrieval, ignoring trailing control events."""
        returned = list(messages)
        with audit_context(batch_id=uuid.uuid4().hex):
            self.audit.emit('messages_received', count=len(returned))
            ids = [uuid.uuid4().hex for _ in returned]
            # Record the entire arrival before processing: an error in an early
            # event must not hide later events that were in the same request.
            for index, (trace_id, message) in enumerate(zip(ids, returned)):
                with audit_context(trace_id=trace_id):
                    self.audit.emit('trace_received', batch_index=index, raw_trace=message)
            result = None
            trigger_result = None
            source_trace_id = None
            processed = 0
            try:
                for trace_id, message in zip(ids, returned):
                    processed += 1
                    result = self._handle_audited(message, trace_id)
                    if self._audit_triggered:
                        trigger_result = result
                        source_trace_id = trace_id
                if result is None:
                    raise ValueError('messages must contain at least one event')
                if trigger_result is not None:
                    result = trigger_result
                hint = build_skill_hint(result)
                appended = bool(hint and result.items)
                if appended:
                    returned.append({'type': 'user_input', 'role': 'user', 'content': hint})
                self.audit.emit('hint_decision', source_trace_id=source_trace_id or ids[-1],
                                generated=appended, hint=hint,
                                result_status=result.status.value, hit_count=len(result.items))
                self.audit.emit('messages_completed', success=True, returned_count=len(returned))
                return returned, result
            except Exception as exc:
                for trace_id in ids[processed:]:
                    with audit_context(trace_id=trace_id):
                        self.audit.emit('trace_not_processed', reason='earlier_event_failed',
                                        embedding={'status':'unavailable','reason':'earlier_event_failed',
                                                   'top_similarity':None,'candidates':[]})
                self.audit.emit('messages_failed', has_results=False, hint_generated=False,
                                error_type=type(exc).__name__, error=str(exc))
                raise

    def handle_raw_trace(self, raw_trace):
        trace_id = uuid.uuid4().hex
        with audit_context(trace_id=trace_id):
            self.audit.emit('trace_received', raw_trace=raw_trace)
        return self._handle_audited(raw_trace, trace_id)

    def _handle_audited(self, raw_trace, trace_id):
        with audit_context(trace_id=trace_id), embedding_state() as state:
            self._audit_triggered = None
            self._audit_stage = 'conversion'
            try:
                result = self._process_raw_trace(raw_trace)
                self.audit.emit('trace_completed', triggered=self._audit_triggered,
                                status=result.status.value, has_results=bool(result.items),
                                reason=result.reason, embedding=state['embedding'])
                return result
            except Exception as exc:
                if state['embedding'].get('reason') == 'not_evaluated':
                    state['embedding'] = embedding_unavailable(f'{self._audit_stage}_failed: {exc}')
                self.audit.emit('trace_failed', triggered=self._audit_triggered,
                                stage=self._audit_stage,
                                has_results=False, error_type=type(exc).__name__, error=str(exc),
                                traceback=traceback.format_exc(), embedding=state['embedding'])
                raise

    def _process_raw_trace(self, raw_trace):
        process_raw_trace(raw_trace, self.trajectory, self.trace_converter)
        latest = self.trajectory.latest_event
        self.audit.emit('trace_converted', event_type=latest.event_type, content=latest.content,
                        trajectory_length=len(self.trajectory.events))
        self._audit_stage = 'trigger'
        triggered = self.trigger_strategy(self.trajectory)
        if type(triggered) is not bool:
            raise TypeError("trigger_strategy必须返回bool")
        self._audit_triggered = triggered
        self.audit.emit('trigger_decision', triggered=triggered, event_type=latest.event_type,
                        strategy=getattr(self.trigger_strategy,'__name__',type(self.trigger_strategy).__name__))
        if not triggered:
            diagnostic_content = latest.content
            if isinstance(raw_trace, dict):
                message = raw_trace.get('message')
                diagnostic_content = raw_trace.get('content')
                if diagnostic_content is None and isinstance(message, dict):
                    diagnostic_content = message.get('content')
            if diagnostic_content is None:
                record_embedding(self.audit, embedding_unavailable('no_message_content'))
            else:
                self.system.diagnostic_similarity(_content_to_text(diagnostic_content),
                    min_similarity=self.retrieval_options.get('min_similarity', .5))
            return RetrievalResult(status=RetrievalStatus.NOT_TRIGGERED, reason="触发策略决定本次不检索")
        self._audit_stage = 'query'
        query = self.query_builder(self.trajectory)
        if not isinstance(query, RetrievalQuery):
            raise TypeError("query_builder必须返回RetrievalQuery")
        if not query.query_text.strip():
            self.system.diagnostic_similarity('')
            return RetrievalResult(status=RetrievalStatus.EMPTY_QUERY, query=query, reason="查询文本为空")
        if query.filters:
            raise ValueError("当前35项skill检索尚不支持filters，不能静默忽略")
        options = dict(self.retrieval_options, top_k=query.top_k)
        self.audit.emit('query_built', query=query.query_text, top_k=query.top_k, filters=query.filters)
        self._audit_stage = 'retrieval'
        result = self.system.retrieve(query.query_text, **options)
        self._audit_stage = 'result_conversion'
        items = []
        for hit in result["items"]:
            document = RetrievalDocument(retrieval_content=hit["description"], full_content=hit["full_content"],
                document_id=hit["skill_id"], source_type="managed_skill", title=hit["name"],
                source_path=hit.get("source_path"),
                metadata={"snapshot_generation": result["snapshot_generation"]})
            items.append(RetrievalHit(document=document, score=hit["score"], rank=hit["rank"],
                matched_content=hit["body"], metadata={"event_id": result["event_id"],
                "skill_id": hit["skill_id"], "node_id": hit["node_id"], "channel": result["channel"]}))
        metadata = {key: value for key, value in result.items() if key not in ("items", "query")}
        return RetrievalResult(status=RetrievalStatus.COMPLETED, query=query, items=items,
            strategy_name="managed_skill_retrieval", metadata=metadata)
