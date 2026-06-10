"""Tests for `scout` — breadth without fabrication. No network, no real LLM."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.scout import Scout  # noqa: E402
from gen.core.errors import SearchBackendError  # noqa: E402
from gen.core.state import Question, RunState, SourceCandidate, SubQuestion  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeBackend:
    def __init__(self, name, urls, fail=False):
        self.name = name
        self._urls = urls
        self._fail = fail
        self.queries = []

    async def search(self, query, limit):
        self.queries.append(query)
        if self._fail:
            raise SearchBackendError(self.name, "boom")
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="r")
            for u in self._urls
        ][:limit]


def _state(raw="what is X?", subqs=None):
    st = RunState(question=Question(raw=raw, run_id="r1"))
    if subqs:
        st.sub_questions = [
            SubQuestion(id=f"s{i}", text=t, parent_run_id="r1") for i, t in enumerate(subqs)
        ]
    return st


def test_collects_and_dedupes_across_backends():
    b1 = FakeBackend("b1", ["https://a", "https://shared"])
    b2 = FakeBackend("b2", ["https://shared", "https://b"])
    scout = Scout([b1, b2])
    st = run(scout.run(_state()))
    urls = [c.url_or_id for c in st.candidates]
    assert urls == ["https://a", "https://shared", "https://b"]  # dedup, order kept


def test_uses_question_text_when_no_llm_and_no_subquestions():
    b = FakeBackend("b", ["https://a"])
    run(Scout([b]).run(_state(raw="how do plants grow?")))
    assert b.queries == ["how do plants grow?"]


def test_uses_subquestions_as_queries():
    b = FakeBackend("b", ["https://a"])
    run(Scout([b]).run(_state(subqs=["sub one", "sub two"])))
    assert b.queries == ["sub one", "sub two"]


def test_backend_failure_is_logged_and_run_continues():
    good = FakeBackend("good", ["https://a"])
    bad = FakeBackend("bad", [], fail=True)
    st = run(Scout([bad, good]).run(_state()))
    assert [c.url_or_id for c in st.candidates] == ["https://a"]  # good still ran
    assert any("bad" in line and "failed" in line for line in st.log)


def test_llm_formulates_queries_capped():
    b = FakeBackend("b", ["https://a"])
    llm = ScriptedLLM("gpt-4o", '["q1", "q2", "q3", "q4"]')
    scout = Scout([b], llm=llm, max_queries=2)
    run(scout.run(_state()))
    assert b.queries == ["q1", "q2"]  # capped at max_queries


def test_llm_parse_failure_falls_back_to_focus_text():
    b = FakeBackend("b", ["https://a"])
    llm = ScriptedLLM("gpt-4o", "not json at all")
    scout = Scout([b], llm=llm)
    run(scout.run(_state(raw="fallback focus")))
    assert b.queries == ["fallback focus"]


def test_scout_produces_no_claims():
    b = FakeBackend("b", ["https://a"])
    st = run(Scout([b]).run(_state()))
    assert st.claims == []  # scout never creates facts
