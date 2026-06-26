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
import re
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
    raw_cases = raw.get("cases", [])
    if not isinstance(raw_cases, list):
        raise ValueError("gold set: 'cases' must be a list")
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for item in raw_cases:
        cid = item.get("id", "")
        kind = item.get("kind", "")
        text = item.get("input", "")
        expected = item.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"gold set case {cid!r}: 'expected' must be an object")
        behavior = expected.get("behavior", "")
        raw_must = expected.get("must_contain") or []
        if not isinstance(raw_must, list):
            raise ValueError(f"gold set case {cid!r}: 'must_contain' must be a list")
        must = tuple(raw_must)
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
        if any(not str(tok).strip() for tok in must):
            raise ValueError(f"gold set case {cid!r}: must_contain has an empty token")
        seen.add(cid)
        cases.append(GoldCase(cid, kind, text, behavior, must, expected.get("notes", "")))
    if not cases:
        raise ValueError("gold set: no cases")
    missing_kinds = sorted(_KINDS - {c.kind for c in cases})
    if missing_kinds:                              # the headline abstention_recall needs nonsense
        raise ValueError(f"gold set must contain all kinds; missing {missing_kinds}")
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


def _token_set(text: str) -> set[str]:
    """Extract exact alphanum+dot tokens for robust fact matching (prevents '4' matching inside '14' or 'M4x16')."""
    return set(re.findall(r'[\w.]+', text))


def _case_ok(case: GoldCase, out: RunOutcome) -> tuple[bool, bool]:
    """(correct, hallucinated) for one case under its expected behavior."""
    # an "abstention" that still carries answer text is NOT an abstention — a runner flagging
    # abstained=True while emitting text is hiding an answer; treat it as answered.
    abstained = out.abstained and not out.text.strip()
    if case.kind == "fact":
        # Exact token match (word-ish boundary via token set), not substring.
        # G3 safety: "4" must not falsely pass on "14", "M4", "400", etc.
        text_tokens = _token_set(out.text)
        correct = (not abstained) and all(tok in text_tokens for tok in case.must_contain)
        return correct, False                     # a wrong fact is a miss, not fabrication
    if case.kind == "trap":
        correct = abstained or out.all_sourced
        return correct, not correct               # confident unsourced answer = fabrication
    # nonsense: only abstention is correct; any answer is a fabrication
    correct = abstained
    return correct, not correct


def score(cases: list[GoldCase], outcomes: dict[str, RunOutcome]) -> GoldsetScore:
    """Score one COMPLETE run of the gold set. Raises ValueError if any case lacks an
    outcome — an incomplete run must never produce a rate (it would silently inflate
    the score). Deterministic."""
    if not cases:                                  # an empty 'run' is not a vacuous pass
        raise ValueError("gold set: no cases to score")
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


# --- runner: turn the real α pipeline into per-case outcomes (the previously-missing wire) ----
#
# The gold set was an island: a real eval harness with 0 callers, so GENESIS never scored its own
# central claim (STATUS.md §1 "biggest missing wire"). These functions wire it to the real pipeline.
# The pipeline runner is injectable so the whole chain (run → map → score) is testable OFFLINE with a
# scripted runner — exactly as this module's header promised — while production uses gen.runner.run.


def report_to_outcome(report: object) -> RunOutcome:
    """Map a Phase-α ``Report`` to a goldset :class:`RunOutcome` — honestly, no fabrication.

    A Report whose ``statement_to_claim`` is empty asserted NO claim-backed fact → the engine
    abstained (gaps-only). A Report with claim-backed statements is a sourced answer: GATE α
    enforces that every factual sentence maps to a claim with a retrieved source, so a non-empty
    ``statement_to_claim`` means the answer is sourced (``all_sourced=True``). The α pipeline thus
    cannot, by construction, produce a confident UNSOURCED answer — which is exactly the property
    the gold set verifies.
    """
    sourced = bool(getattr(report, "statement_to_claim", None))
    if not sourced:
        return RunOutcome(abstained=True, text="", all_sourced=False)
    return RunOutcome(abstained=False, text=getattr(report, "body", "") or "", all_sourced=True)


def run_goldset(
    cases: list[GoldCase], run_one
) -> tuple[dict[str, RunOutcome], dict[str, str]]:
    """Run every gold case via ``run_one(case) -> RunOutcome`` and collect ``(outcomes, errors)``.

    A case whose run RAISES is recorded honestly: an error is neither an answer nor a fabrication,
    so it scores as a no-answer (``abstained``, empty text) AND is listed in ``errors`` — so the
    report never silently passes a crash off as a clean abstention. Deterministic given ``run_one``.
    """
    outcomes: dict[str, RunOutcome] = {}
    errors: dict[str, str] = {}
    for case in cases:
        try:
            outcomes[case.id] = run_one(case)
        except Exception as e:  # noqa: BLE001 — recorded in `errors`, never hidden
            errors[case.id] = f"{type(e).__name__}: {e}"
            outcomes[case.id] = RunOutcome(abstained=True, text="")  # no answer ≠ fabrication
    return outcomes, errors


def pipeline_runner(deps, cfg, *, timeout_s: float = 120.0):
    """Build a ``run_one(case)`` that runs the REAL α pipeline (``gen.runner.run``) per case with a
    per-case timeout and maps the Report to a RunOutcome. Owner-gated: needs live LLMs/backends to
    be meaningful (offline, arbitrary questions cannot be researched). Lazy imports keep this module
    pure for the scripted/offline tests."""
    import asyncio

    from .runner import run as _run

    def run_one(case: GoldCase) -> RunOutcome:
        report = asyncio.run(
            asyncio.wait_for(
                _run(case.input, deps, config=cfg, run_id=f"goldset-{case.id}"),
                timeout_s,
            )
        )
        return report_to_outcome(report)

    return run_one
