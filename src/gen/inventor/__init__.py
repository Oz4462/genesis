"""gen.inventor — the autonomous invention loop (offline ScriptedLLM spine, deterministic gate as backbone).

The loop (INVENTOR §3): a PROPOSER (LLM council) widens to bold concepts; a deterministic non-LLM GATE
grounds and verifies each (physics, prior-art novelty, safety) — "extend / order / verify, never decide except
the gate". This package is built interface-first so the offline ScriptedLLM/fixture path is the test backbone
and any live model/tool/oracle is an injectable seam (the external layer in ``gen.external`` / ``gen.tools``).

Built so far (TC5): the optimization and evolution SEAMS — ``optimize`` (Pareto / external multi-objective)
and ``evolve_engine`` (in-house MAP-Elites / external evolutionary engine). The brief/generate/ground/score/
loop/novelty/safety modules land in the I/N/E/S phases.
"""

__all__: list[str] = []
