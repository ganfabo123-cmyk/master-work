"""Agent Trace entrypoint with replaceable trigger and query strategies."""

from agent_protocol import (Trajectory, RetrievalQuery, RetrievalDocument, RetrievalHit,
    RetrievalResult, RetrievalStatus, process_raw_trace, developer_trace_converter,
    developer_should_retrieve, developer_build_query)


class AgentSession:
    """Create one session per Agent conversation; the SkillSystem may be shared."""

    def __init__(self, system, *, trace_converter=developer_trace_converter,
                 trigger_strategy=developer_should_retrieve, query_builder=developer_build_query,
                 retrieval_options=None):
        self.system = system
        self.trace_converter = trace_converter
        self.trigger_strategy = trigger_strategy
        self.query_builder = query_builder
        self.retrieval_options = dict(retrieval_options or {})
        self.trajectory = Trajectory()

    def feedback(self, **rating):
        return self.system.feedback(**rating)

    def handle_raw_trace(self, raw_trace):
        process_raw_trace(raw_trace, self.trajectory, self.trace_converter)
        triggered = self.trigger_strategy(self.trajectory)
        if type(triggered) is not bool:
            raise TypeError("trigger_strategy必须返回bool")
        if not triggered:
            return RetrievalResult(status=RetrievalStatus.NOT_TRIGGERED, reason="触发策略决定本次不检索")
        query = self.query_builder(self.trajectory)
        if not isinstance(query, RetrievalQuery):
            raise TypeError("query_builder必须返回RetrievalQuery")
        if not query.query_text.strip():
            return RetrievalResult(status=RetrievalStatus.EMPTY_QUERY, query=query, reason="查询文本为空")
        if query.filters:
            raise ValueError("当前35项skill检索尚不支持filters，不能静默忽略")
        options = dict(self.retrieval_options, top_k=query.top_k)
        result = self.system.retrieve(query.query_text, **options)
        items = []
        for hit in result["items"]:
            document = RetrievalDocument(retrieval_content=hit["description"], full_content=hit["full_content"],
                document_id=hit["skill_id"], source_type="managed_skill", title=hit["name"],
                metadata={"snapshot_generation": result["snapshot_generation"]})
            items.append(RetrievalHit(document=document, score=hit["score"], rank=hit["rank"],
                matched_content=hit["body"], metadata={"event_id": result["event_id"],
                "skill_id": hit["skill_id"], "node_id": hit["node_id"], "channel": result["channel"]}))
        metadata = {key: value for key, value in result.items() if key not in ("items", "query")}
        return RetrievalResult(status=RetrievalStatus.COMPLETED, query=query, items=items,
            strategy_name="managed_skill_retrieval", metadata=metadata)
