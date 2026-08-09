"""Generic observation metadata shared by all runtime scenarios."""

from __future__ import annotations


class BaseObservation:
    """Common identity and correlation metadata for one observation."""

    def __init__(
        self,
        observation_id: str,
        task_id: str,
        session_id: str,
        *,
        feedback_types: tuple[str, ...] = (),
    ) -> None:
        self.observation_id = observation_id
        self.task_id = task_id
        self.session_id = session_id
        self.feedback_types = feedback_types

    def feedback(self, feedback_type: str, *args: object, **kwargs: object) -> object:
        """Dispatch one supported feedback type to its concrete implementation."""
        if feedback_type not in self.feedback_types:
            available = ", ".join(self.feedback_types) or "无"
            raise ValueError(f"Unsupported feedback type {feedback_type!r}; 可用类型：{available}。")

        handler = getattr(self, f"_feedback_{feedback_type}", None)
        if handler is None:
            raise NotImplementedError(f"Feedback type {feedback_type!r} has no implementation")
        return handler(*args, **kwargs)
