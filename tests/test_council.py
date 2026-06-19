"""The cross-model COUNCIL: grok AND Claude propose candidate formulas live inside GENESIS, and the
deterministic gate — never a model — decides what survives. This pins the integration LOGIC offline
and reproducibly with ScriptedLLM proposers of two different families; the live run (real grok + claude
CLIs) is `gen --mode council`.

Run:  pytest tests/test_council.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.discovery.benchmark import pendulum_case  # noqa: E402
from gen.discovery.symbiosis import GrokProposer, council_discover  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402

# grok proposes the CORRECT pendulum exponents (T = 2π·L^0.5·g^-0.5); Claude proposes a WRONG guess.
_GROK_JSON = '[{"exponents": {"L": 0.5, "g": -0.5}, "rationale": "dimensional analysis"}]'
_CLAUDE_JSON = '[{"exponents": {"L": 1.0, "g": -1.0}, "rationale": "first guess"}]'


def _council():
    return [
        GrokProposer(client=ScriptedLLM("grok-build", _GROK_JSON), model="grok-build"),
        GrokProposer(client=ScriptedLLM("claude-opus-4-8", _CLAUDE_JSON), model="claude-opus-4-8"),
    ]


def test_council_is_cross_model_and_gates_every_proposal():
    """Both families propose; the gate judges each. cross_model is True (xAI + anthropic), the CORRECT
    proposal passes the gate, the WRONG one does not — the model never decides, the gate does."""
    case = pendulum_case()
    res = council_discover(case.problem, proposers=_council(), known_laws=case.known_laws)
    assert res.cross_model and len(res.families) == 2          # two distinct model families took part
    assert set(res.judged_by_model) == {"grok-build", "claude-opus-4-8"}
    grok_passed = [j for j in res.judged_by_model["grok-build"] if j.verdict.passed]
    claude_passed = [j for j in res.judged_by_model["claude-opus-4-8"] if j.verdict.passed]
    assert grok_passed and not claude_passed                   # gate confirmed grok, rejected Claude
    assert res.validated and all(v.passed for v in res.validated)   # only gate-passed formulas survive


def test_council_is_deterministic_given_scripted_proposers():
    """Same scripted proposers → identical validated formulas: the gating is reproducible (live CLIs
    are non-deterministic, which is exactly why the offline test uses ScriptedLLM)."""
    case = pendulum_case()
    a = council_discover(case.problem, proposers=_council(), known_laws=case.known_laws)
    b = council_discover(case.problem, proposers=_council(), known_laws=case.known_laws)
    assert [v.candidate.expression for v in a.validated] == [v.candidate.expression for v in b.validated]


def test_council_runs_with_no_proposers_genesis_alone():
    """GENESIS still works with NO model at all — its own dimensional discovery runs; the council
    only ever ADDS gated breadth, it is never required."""
    case = pendulum_case()
    res = council_discover(case.problem, proposers=[], known_laws=case.known_laws)
    assert not res.cross_model and res.judged_by_model == {}
    assert res.own is not None                                 # GENESIS's own discovery still ran
