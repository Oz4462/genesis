"""GENESIS LLM boundary: vendor-agnostic completion + tolerant parsing."""

from __future__ import annotations

from .base import LLMClient, LLMResponse, ScriptedLLM
from .parsing import extract_json

__all__ = ["LLMClient", "LLMResponse", "ScriptedLLM", "extract_json"]
