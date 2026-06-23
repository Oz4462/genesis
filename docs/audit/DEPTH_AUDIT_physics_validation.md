# DEPTH_AUDIT — physics_validation.py (GATE δ-physics aggregator)

**Verdict: REAL.** No source edit required.

## What was audited
`src/gen/physics_validation.py` ties the 40 δ-layer validators into a single GATE.
Given a list of `PhysicsCheck`s (validator name + resolved numeric inputs), it runs
every one (`run_physics_checks`) and aggregates one `GateResult` (`gate_delta_physics`)
that passes ONLY if every check actually ran and reported `ok`.

## Facade hypothesis — and how it was killed
New test `tests/test_physics_validation_characterization.py` (11 tests, all green; legacy
`test_physics_validation.py` left untouched). It proves the gate is not a hollow stub:

- **Input-driven verdict.** The *same* `pressure_vessel` validator passes with yield 600
  MPa (SF=1.2 against the docstring anchor hoop=500 MPa) and FAILS with yield 300 MPa
  (SF=0.6) — a constant verdict could not depend on the input. A second validator
  (`plate_bending`, clamped anchor σ≈30 MPa) flips on its allowable stress too, proving
  per-validator dispatch into real code.
- **All three documented codes fire with EXACT strings:**
  `PHYSICS_UNKNOWN_VALIDATOR` (name absent from `VALIDATORS`),
  `PHYSICS_CHECK_ERROR` (pressure_vessel with non-positive radius → GeometryError
  surfaced, never swallowed), `PHYSICS_CHECK_FAILED` (ran but margin not cleared, with the
  computed `safety_factor` in `detail`).
- **Empty list passes vacuously**; a mixed batch collects every failure independently
  (one bad check never aborts the batch).
- **Registry integrity:** every value in `VALIDATORS` is callable (catches a key bound to
  a renamed/missing function — which would silently degrade every check naming it into
  `PHYSICS_UNKNOWN_VALIDATOR`).
- **Property test (Hypothesis):** for arbitrary pressure/yield, the gate passes a single
  pressure_vessel check exactly when the closed-form SF = yield/(p·r/t) ≥ 1, and emits
  exactly the `PHYSICS_CHECK_FAILED` code otherwise — pinning the verdict to real
  arithmetic across the input space, not a hand-picked pair.

## 4 Linsen
- **L1 (Wahrheit):** verdict is computed from the validators' closed forms (anchors match
  the validators' own docstrings); no fabricated pass. ✔
- **L2 (Drift):** failure codes match the docstring/source exactly; no drift between
  documented contract and behavior. ✔
- **L3 (Vollständigkeit/Naht):** all three failure paths + vacuous-empty + mixed-batch +
  registry seam covered; new test does not touch the legacy test (no churn). ✔
- **L4 (Realisierbarkeit):** offline, deterministic, no LLM/network; runs in ~2 s. ✔

**PLATFORM_PLAN alignment:** physics_validation is the δ-physics GATE that makes
auto-selected checks (physics_selection.RECIPES) a hard pass/fail condition, per the
"Verifikation ist ein Gate" Kernprinzip. Confirmed honest.
