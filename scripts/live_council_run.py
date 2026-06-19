"""live_council_run — a LIVE cross-model council run: grok AND Claude propose, GENESIS gates.

Two paths, same gate:
  * In a native terminal (where the grok/claude CLIs reach the network), this runs FULLY LIVE via
    ``default_council()`` — it shells out to grok-build and claude-opus and gates their real-time
    proposals. Run it as:  python scripts/live_council_run.py --live
  * Without ``--live`` (and the default when the live CLIs are unreachable, e.g. inside an agent
    sandbox where a python-launched CLI grandchild is blocked), it gates the REAL proposals captured
    LIVE from grok + Claude on 2026-06-19 (verbatim below) — so the gating result is reproducible and
    the proposals are genuinely the models', not invented.

Either way GENESIS's deterministic gate — never a model — decides what survives. This is the honest
demonstration that grok and Claude work INSIDE GENESIS: they widen the candidate space, the gate is
the authority. No trading.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.discovery.benchmark import kepler_case, pendulum_case  # noqa: E402
from gen.discovery.symbiosis import GrokProposer, council_discover  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402

# --- REAL proposals captured live from the grok and claude CLIs (2026-06-19), verbatim -------------
_CAPTURED = {
    "Pendulum period": {
        "grok-build": '[{"exponents":{"L":0.5,"g":-0.5},"rationale":"T=2pi sqrt(L/g)"},'
                      '{"exponents":{"L":1,"g":-0.5},"rationale":"falsche lineare L-Abhaengigkeit"},'
                      '{"exponents":{"L":1,"g":-1},"rationale":"falsch"}]',
        "claude-opus-4-8": '[{"exponents":{"L":0.5,"g":-0.5},"rationale":"Dimensionsanalyse T=2pi sqrt(L/g)"},'
                           '{"exponents":{"L":1.0,"g":-0.5},"rationale":"dimensional inkonsistent, Rivale"},'
                           '{"exponents":{"L":0.5,"g":-1.0},"rationale":"dimensional inkonsistent, Kontrast"}]',
    },
    "Kepler III": {
        "grok-build": '[{"exponents":{"a":1.5,"mu":-0.5},"rationale":"Kepler III T=2pi sqrt(a^3/mu)"},'
                      '{"exponents":{"a":1.5},"rationale":"mu konstant, in C absorbiert"},'
                      '{"exponents":{"a":3,"mu":-1},"rationale":"Fehler: gilt fuer T^2"}]',
        "claude-opus-4-8": '[{"exponents":{"a":1.5,"mu":-0.5},"rationale":"Kepler 3 exakt, Dimension s"},'
                           '{"exponents":{"a":1.5,"mu":0},"rationale":"ohne mu, dimensional unvollstaendig"},'
                           '{"exponents":{"a":2.0,"mu":-0.5},"rationale":"steilere Bahnabhaengigkeit, Rivale"}]',
    },
}


def _proposers_for(case_name: str, live: bool):
    if live:
        from gen.discovery.symbiosis import default_council
        return default_council()
    cap = _CAPTURED[case_name]
    return [GrokProposer(client=ScriptedLLM(m, txt), model=m) for m, txt in cap.items()]


def main(live: bool) -> int:
    print("=" * 78)
    print("GENESIS — Cross-Model-Council:  grok + Claude schlagen vor, das GENESIS-Gate entscheidet")
    print(f"Modus: {'LIVE (grok + claude CLIs)' if live else 'echte Live-Vorschläge vom 2026-06-19, gegated'}")
    print("=" * 78)
    for case in (pendulum_case(), kepler_case()):
        print(f"\n### {case.name}: {case.problem.idea}")
        res = council_discover(case.problem, proposers=_proposers_for(case.name, live),
                               known_laws=case.known_laws)
        print(f"  cross_model={res.cross_model}  Familien={', '.join(res.families)}")
        print(f"  GENESIS eigen (ohne Modell): {len(res.own.validated)} validierte Formel(n)")
        for model, judged in res.judged_by_model.items():
            print(f"  Vorschlag {model}:")
            for j in judged:
                tag = "BESTÄTIGT " if j.verdict.passed else "verworfen "
                print(f"     {str(j.proposal.exponents):26s} -> Gate: {tag} "
                      f"(R²={j.verdict.candidate.r_squared:.4f})")
        if res.validated:
            best = res.validated[0]
            print(f"  ==> validiert: {best.candidate.expression}  (R²={best.candidate.r_squared:.5f})")
    print("\nGate-Autorität: ein Modell — grok ODER Claude — erweitert nur den Kandidatenraum;")
    print("die deterministische Prüfung (Dimensionen + Fit + Rivalen) entscheidet allein.")
    return 0


if __name__ == "__main__":
    sys.exit(main(live="--live" in sys.argv))
