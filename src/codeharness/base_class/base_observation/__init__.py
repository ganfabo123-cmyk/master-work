"""Observation implementations grouped by input or protocol type."""

from .llm_observation import LLMObservation, SystemSignal

__all__ = ["LLMObservation", "SystemSignal"]
