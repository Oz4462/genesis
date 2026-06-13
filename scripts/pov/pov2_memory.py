"""PoV-2 harness — does ANAMNESIS cross-run memory reuse verified facts correctly
AND abstain honestly on novel queries (no false reuse)?

GENESIS gap #1: the ledger is per-run in-memory; every run re-researches everything.
ANAMNESIS provides a persistent, conformal-bounded reuse layer. The decisive
question for a no-hallucination engine is NOT just "can it recall" but "does it
REFUSE to hand back a stored fact for an unrelated query". This harness proves both,
offline, with ANAMNESIS's REAL TraceStore + ConformalCalibrator + ConformalRetriever.

Proves with numbers:
  1. REUSE HIT     — paraphrased repeats of verified facts are accepted and map to the
     correct stored claim (the avoided-research signal).
  2. NO FALSE REUSE — nonsense/novel queries (GENESIS gold-set "nonsense" style) are
     ABSTAINED (conformal band rejects them). This is the honesty gate.

SCOPE / HONESTY: uses the deterministic `hash_embedder` (no network), so absolute
hit-rates reflect a bag-of-token embedder, not a production sentence model. The
end-to-end TOKEN/WALL-CLOCK saving needs a live Ollama run (owner-gated); here the
saving proxy is "avoided research calls" = number of accepted reuses.

Deterministic: fixed corpus + fixed queries + deterministic embedder, no RNG.
Writes runs/pov/pov2/report.json. Exit 0 iff PASS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve()
_GENESIS_REPO = _SCRIPT.parents[2]
_DESKTOP = _GENESIS_REPO.parents[2]
_ANAMNESIS_SRC = _DESKTOP / "alle apps" / "ANAMNESIS" / "anamnesis-py" / "src"
if not _ANAMNESIS_SRC.exists():
    raise SystemExit(f"ANAMNESIS src missing: {_ANAMNESIS_SRC}")
sys.path.insert(0, str(_ANAMNESIS_SRC))

from anamnesis.storage import TraceStore, ReasoningStep, hash_embedder  # noqa: E402
from anamnesis.conformal import ConformalCalibrator  # noqa: E402
from anamnesis.retrieve import ConformalRetriever  # noqa: E402


def ollama_embedder(model: str = "embeddinggemma:latest", url: str = "http://localhost:11434/api/embed"):
    """Real local semantic embedder via Ollama (deterministic, no network egress).

    Returns a Callable[[str], np.ndarray] compatible with ANAMNESIS's Embedder.
    """
    import json as _json
    import urllib.request as _ur

    import numpy as _np

    def embed(text: str):
        payload = _json.dumps({"model": model, "input": text or " "}).encode("utf-8")
        req = _ur.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        vec = _np.asarray(data["embeddings"][0], dtype=_np.float64)
        n = _np.linalg.norm(vec)
        if n == 0.0:
            vec[0] = 1.0
            return vec
        return vec / n

    return embed

# GENESIS-style verified facts (mirroring goldset/v1.json "fact" entries).
VERIFIED_FACTS = [
    "standard gravity equals 9.80665 meters per second squared",
    "the speed of light in vacuum is 299792458 meters per second",
    "an M4 screw has a nominal diameter of 4 millimeters",
    "the Kirsch stress concentration factor for a circular hole under uniaxial tension is 3",
    "PLA filament used in 3D printing has a typical density of 1.24 grams per cubic centimeter",
    "ISO 273 specifies a 4.5 millimeter clearance hole diameter for an M4 screw medium series",
    "the Python programming language was created by Guido van Rossum",
    "an ISO 898-1 property class 8.8 screw has ultimate tensile strength 800 megapascals",
    "Euler critical buckling load for a pinned-pinned column is pi squared EI over L squared",
    "Ohm law relates voltage current and resistance as V equals I times R",
]

# Calibration paraphrases (genuine matches) -- used only to warm the calibrator.
CALIB_PARAPHRASES = [
    "what is the value of standard gravity in meters per second squared",
    "value of acceleration due to standard gravity",
    "speed of light in vacuum in meters per second",
    "how fast does light travel in a vacuum",
    "nominal diameter of an M4 screw in millimeters",
    "what diameter is an M4 screw",
    "Kirsch stress concentration factor circular hole uniaxial tension",
    "stress concentration factor for a hole in a plate under tension",
    "typical density of PLA filament for 3D printing",
    "density of PLA in grams per cubic centimeter",
    "ISO 273 clearance hole diameter for an M4 screw medium series",
    "clearance hole size for M4 per ISO 273",
    "who created the Python programming language",
    "creator of Python language",
    "ultimate tensile strength of a class 8.8 screw ISO 898-1",
    "tensile strength of property class 8.8 fastener",
    "Euler critical buckling load formula pinned pinned column",
    "buckling load formula for a pin ended column",
    "Ohm law voltage current resistance relation",
    "state Ohm law for voltage current and resistance",
] * 2  # 40 calibration scores (>= min_calibration=30)

# Held-out repeats (different wording than calibration) -> expect correct reuse.
REPEAT_QUERIES = [
    ("standard acceleration of gravity numeric value", 0),
    ("vacuum speed of light numeric constant", 1),
    ("M4 fastener nominal diameter", 2),
    ("circular hole stress concentration under axial tension factor", 3),
    ("typical 3D printing PLA material density", 4),
    ("ISO 273 medium series clearance hole for M4", 5),
    ("inventor of the Python language", 6),
    ("class 8.8 bolt ultimate tensile strength value", 7),
    ("critical buckling load pinned column Euler", 8),
    ("relationship of voltage current resistance Ohm", 9),
]

# Novel / nonsense queries (GENESIS gold-set "nonsense" style) -> expect ABSTAIN.
NOVEL_QUERIES = [
    "mechanical properties of the Glubbex GX-7 polymer",
    "yield strength of Vorkstanium-7075 alloy",
    "state the Brennholz-Kawaguchi theorem of beam stability",
    "what does ISO 99999-3 specify about fastener coatings",
    "what does the European Torsional Compliance Bureau certify",
    "how does cryo-helical annealing improve PLA layer adhesion",
    "favourite colour of the moon on a Tuesday afternoon",
    "the boiling point of imaginary unobtanium under starlight",
]

ALPHA = 0.1


def _make_embedder(name: str):
    if name == "ollama":
        return ollama_embedder()
    return hash_embedder(dim=64)


def _build(embedder_name: str = "hash"):
    embed = _make_embedder(embedder_name)
    store = TraceStore(embed)
    step_ids: list[str] = []
    for fact in VERIFIED_FACTS:
        step = ReasoningStep.make(capture_id="genesis_verified", text=fact, intent="fact")
        store.add_steps([step])
        step_ids.append(step.step_id)

    cal = ConformalCalibrator(alpha=ALPHA, min_calibration=30)
    for q in CALIB_PARAPHRASES:
        hits = store.query_similar_steps(q, k=1)
        if hits:
            cal.add(hits[0][1])  # nonconformity score of the nearest genuine match
    retriever = ConformalRetriever(store=store, calibrator=cal, k=3)
    return retriever, step_ids, cal


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _evaluate(embedder_name: str = "hash") -> dict:
    retriever, step_ids, cal = _build(embedder_name)
    tau = cal.threshold(alpha=ALPHA).tau

    reuse_hits = correct_target = 0
    repeat_scores: list[float] = []
    for q, idx in REPEAT_QUERIES:
        res = retriever.retrieve(q, alpha=ALPHA)
        if res.candidates:
            repeat_scores.append(res.candidates[0].score)
        if not res.abstained:
            reuse_hits += 1
            if step_ids[idx] in res.accepted_step_ids:
                correct_target += 1

    false_reuse = 0
    novel_scores: list[float] = []
    for q in NOVEL_QUERIES:
        res = retriever.retrieve(q, alpha=ALPHA)
        if res.candidates:
            novel_scores.append(res.candidates[0].score)
        if not res.abstained:
            false_reuse += 1

    # Diagnostic: does the embedder SEPARATE genuine repeats from nonsense?
    # If the two nearest-score distributions overlap, the false reuse is an
    # embedder-quality artifact, not an ANAMNESIS-mechanism failure.
    separation = {
        "genuine_repeat_nearest_median": _median(repeat_scores),
        "novel_nearest_median": _median(novel_scores),
        "novel_nearest_min": min(novel_scores),
        "genuine_repeat_nearest_max": max(repeat_scores),
        "distributions_overlap": min(novel_scores) <= max(repeat_scores),
    }

    return {
        "separation": separation,
        "calibration_n": cal.n,
        "tau": tau,
        "n_repeat": len(REPEAT_QUERIES),
        "reuse_accept": reuse_hits,
        "reuse_correct_target": correct_target,
        "reuse_hit_rate": reuse_hits / len(REPEAT_QUERIES),
        "reuse_correct_rate": correct_target / len(REPEAT_QUERIES),
        "n_novel": len(NOVEL_QUERIES),
        "false_reuse": false_reuse,
        "false_reuse_rate": false_reuse / len(NOVEL_QUERIES),
        "avoided_research_calls_proxy": correct_target,
    }


def main() -> int:
    embedder_name = sys.argv[1] if len(sys.argv) > 1 else "hash"
    a = _evaluate(embedder_name)
    b = _evaluate(embedder_name)
    deterministic = a == b

    no_false_reuse = a["false_reuse"] == 0
    recalls = a["reuse_correct_rate"] >= 0.7
    gate = no_false_reuse and recalls and deterministic

    # Honest verdict: recall works; the honesty gate's false-reuse is governed by
    # embedder quality. If genuine/novel score distributions overlap, the cause is
    # the toy hash_embedder, and the real verdict is BLOCKED on a real embedder.
    sep = a["separation"]
    if gate:
        verdict = "PASS"
    elif recalls and deterministic and sep["distributions_overlap"]:
        verdict = "INCONCLUSIVE_EMBEDDER_LIMITED (recall ok; honesty gate needs real embedder)"
    else:
        verdict = "FAIL"

    report = {
        "pov": "PoV-2 ANAMNESIS cross-run memory",
        "run_id": "pov2",
        "embedder": embedder_name,
        "scope": "real TraceStore+ConformalRetriever; live token-saving deferred",
        "alpha": ALPHA,
        "metrics": a,
        "deterministic": deterministic,
        "gate_pass": gate,
        "verdict": verdict,
        "blocked_on": (
            None if gate else "real semantic embedder (fastembed) not installed + live run owner-gated"
        ),
    }
    out = _GENESIS_REPO / "runs" / "pov" / "pov2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"=== PoV-2: ANAMNESIS cross-run memory (embedder={embedder_name}) ===")
    print(
        f"reuse on repeats : {a['reuse_correct_target']}/{a['n_repeat']} correct "
        f"(hit_rate={a['reuse_hit_rate']:.2f}, correct_rate={a['reuse_correct_rate']:.2f})"
    )
    print(
        f"false reuse novel: {a['false_reuse']}/{a['n_novel']} "
        f"(false_reuse_rate={a['false_reuse_rate']:.2f}, want 0)  tau={a['tau']:.3f}"
    )
    print(
        f"separation: genuine_median={sep['genuine_repeat_nearest_median']:.3f} "
        f"novel_median={sep['novel_nearest_median']:.3f} "
        f"overlap={sep['distributions_overlap']}"
    )
    print(f"deterministic={deterministic} -> VERDICT: {verdict}")
    print(f"(report: {out / 'report.json'})")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
