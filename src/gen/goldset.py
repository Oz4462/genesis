"""Gold set — the curated measurement set for the deferred live runs (research #2).

"Real-use ready" is by definition a MEASUREMENT, and a measurement needs a fixed,
curated question set with known correct behavior. This module is that set's contract:
a versioned JSON fixture (goldset/v1.json), a fail-loud loader, and a deterministic
scorer. Three kinds, after FActScore/HalluLens:

  • fact      — a checkable claim with a known, sourceable answer: the answer must be
                GIVEN and contain the expected tokens (fact accuracy).
  • trap      — plausibly answerable, but the precise value is not reliably sourceable:
                abstaining OR answering with sources is correct; a confident unsourced
                number is the hallucination (trap resistance).
  • nonsense  — a non-existent entity (HalluLens style): the ONLY correct behavior is
                abstention (abstention recall). An answer here is a hallucination by
                construction — the headline failure metric.

The scorer takes per-case run outcomes (abstained / answer text / whether every
statement was sourced) and computes the rates. It REFUSES to score an incomplete run
(a missing case would silently inflate the rates — the eval analogue of a sourceless
claim). The live runner that produces outcomes against Ollama is the deferred,
owner-gated part; this contract plus a scripted runner is fully testable offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_KINDS = {"fact", "trap", "nonsense"}
_BEHAVIORS = {"fact": "answer", "trap": "abstain_or_sourced", "nonsense": "abstain"}

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "goldset" / "v1.json"


@dataclass(frozen=True)
class GoldCase:
    """One measurement case: an input with its known correct behavior."""

    id: str
    kind: str                      # fact | trap | nonsense
    input: str
    behavior: str                  # answer | abstain_or_sourced | abstain
    must_contain: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class RunOutcome:
    """What a (live or scripted) runner reports for one case.

    `abstained`    the engine declined to answer (gaps-only / empty report).
    `text`         the answer text ("" when abstained).
    `all_sourced`  True if every asserted statement mapped to a sourced claim.
    """

    abstained: bool
    text: str = ""
    all_sourced: bool = False


def load_goldset(path: str | Path = DEFAULT_PATH) -> list[GoldCase]:
    """Load and validate the gold set — fail-loud on any malformed case (an invalid
    measurement set must never silently score)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for item in raw.get("cases", []):
        cid = item.get("id", "")
        kind = item.get("kind", "")
        text = item.get("input", "")
        expected = item.get("expected") or {}
        behavior = expected.get("behavior", "")
        must = tuple(expected.get("must_contain") or ())
        if not cid or cid in seen:
            raise ValueError(f"gold set: missing or duplicate case id {cid!r}")
        if kind not in _KINDS:
            raise ValueError(f"gold set case {cid!r}: unknown kind {kind!r}")
        if not text.strip():
            raise ValueError(f"gold set case {cid!r}: empty input")
        if behavior != _BEHAVIORS[kind]:
            raise ValueError(
                f"gold set case {cid!r}: kind {kind!r} requires behavior "
                f"{_BEHAVIORS[kind]!r}, got {behavior!r}")
        if kind == "fact" and not must:
            raise ValueError(f"gold set case {cid!r}: a fact needs must_contain tokens")
        seen.add(cid)
        cases.append(GoldCase(cid, kind, text, behavior, must, expected.get("notes", "")))
    if not cases:
        raise ValueError("gold set: no cases")
    return cases


@dataclass
class GoldsetScore:
    """The measured rates over one complete run of the gold set."""

    n_cases: int
    fact_accuracy: float           # facts answered containing the expected tokens
    abstention_recall: float       # nonsense correctly abstained — the headline
    trap_resistance: float         # traps abstained or fully sourced
    hallucinations: list[str] = field(default_factory=list)   # case ids that fabricated
    failures: list[str] = field(default_factory=list)         # all incorrect case ids

    @property
    def ok(self) -> bool:
        """The non-negotiable bar: NO fabrication anywhere (hallucinations empty)."""
        return not self.hallucinations


def _case_ok(case: GoldCase, out: RunOutcome) -> tuple[bool, bool]:
    """(correct, hallucinated) for one case under its expected behavior."""
    if case.kind == "fact":
        correct = (not out.abstained) and all(tok in out.text for tok in case.must_contain)
        return correct, False                     # a wrong fact is a miss, not fabrication
    if case.kind == "trap":
        correct = out.abstained or out.all_sourced
        return correct, not correct               # confident unsourced answer = fabrication
    # nonsense: only abstention is correct; any answer is a fabrication
    correct = out.abstained
    return correct, not correct


def score(cases: list[GoldCase], outcomes: dict[str, RunOutcome]) -> GoldsetScore:
    """Score one COMPLETE run of the gold set. Raises ValueError if any case lacks an
    outcome — an incomplete run must never produce a rate (it would silently inflate
    the score). Deterministic."""
    missing = [c.id for c in cases if c.id not in outcomes]
    if missing:
        raise ValueError(f"gold set run incomplete; missing outcomes for: {missing}")

    per_kind_total = {"fact": 0, "trap": 0, "nonsense": 0}
    per_kind_ok = {"fact": 0, "trap": 0, "nonsense": 0}
    hallucinations: list[str] = []
    failures: list[str] = []
    for case in cases:
        ok, fabricated = _case_ok(case, outcomes[case.id])
        per_kind_total[case.kind] += 1
        if ok:
            per_kind_ok[case.kind] += 1
        else:
            failures.append(case.id)
        if fabricated:
            hallucinations.append(case.id)

    def rate(kind: str) -> float:
        return per_kind_ok[kind] / per_kind_total[kind] if per_kind_total[kind] else 1.0

    return GoldsetScore(
        n_cases=len(cases),
        fact_accuracy=rate("fact"),
        abstention_recall=rate("nonsense"),
        trap_resistance=rate("trap"),
        hallucinations=hallucinations,
        failures=failures,
    )
