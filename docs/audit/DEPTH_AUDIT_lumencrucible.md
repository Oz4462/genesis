# Depth Audit — `grenzverschiebung/lumencrucible.py` (`process_dream`)

**Task:** T01 — make `hammer_omega_certificate` + `self_improvement` real.
**Verdict:** **PARTIAL-FACADE → REPAIRED.** The skeleton was wired but the headline
artifacts were silently hollow. Three concrete facades found and fixed; the δ⁺ reality
chain and the idempotent self-ascent were already real and are now characterized by a
dedicated test.

## What was genuinely real before
- `LumenHammer` is real and **input-sensitive** (jetpack canon → `EmberNest_Thrust_Rig`,
  other dreams → `FirstCrack_*`); `claim.text` tracks the produced hammer.
- The δ⁺ reality chain genuinely calls `reality.evaluate_reality` (corroborates the
  9.81 m/s² demo within tolerance) and `gate_delta_plus`; results surface via
  `reality_verdict` / `delta_plus_result` / `coverage_certificate` / `run_state`.
- The post-cert seam/memory_fabric/pareto/coverage objects are built and attached to the
  `RunState`, and `build_omega_certificate` + `gate_omega` run over the populated state.
- `_self_improve` was already idempotent on a configurable, isolated `work_queue_path`
  (dedup on the constant `_SELF_ASCENT_SUGGESTION`); no `APPEND_FAILED` on a writable path.

## Facades found (and fixed — `lumencrucible.py` only)
1. **The returned `OmegaCertificate` dropped the two spec-mandated notes.** The canonical
   post-cert override (`receipt = build_omega_certificate(run_state)`) rebuilds notes from
   `RunState` artifacts only, so the `self_ascent` and `delta_plus_reality` notes produced
   by `_build_omega_certificate` were thrown away — the returned cert had neither.
   **Fix:** pass them forward as real `extra_notes` (carrying the actual idempotency flag
   and the actual reality verdict status/tolerance), and persist `rs.reality_verdict` /
   `rs.delta_plus_result` so the state seam is no longer hollow.
2. **The `Claim` carried a bare string `status="VERIFIED"`** while the field is typed
   `status: ClaimStatus`. `memory_fabric.build` deposits only claims with
   `status is ClaimStatus.VERIFIED` (identity) — so with the string, **nothing was ever
   deposited; the memory fabric was empty.** **Fix:** `status=ClaimStatus.VERIFIED`. The
   fabric now deposits the claim and passes `gate_zeta`.
3. **`Claim.sources` were bare strings** while the field is typed `list[SourceRef]`
   (the non-empty invariant passed, masking the type error). **Fix:** ≥2 real `SourceRef`
   provenance entries (`retrieved=True`, `support=SUPPORTS`) pointing at the concrete
   in-repo producers (`process_dream`, `map_development_front`, `docs/HORIZON.md`).

## Evidence (new test: `tests/test_lumencrucible_characterization.py`, 15 tests, all green)
- Omega cert: ≥1 `GateReceipt`, ≥2 `LearningNote`, **includes** `self_ascent` AND
  `delta_plus_reality`; the δ⁺ note reflects the real `corroborated` verdict.
- Claim: `status is ClaimStatus.VERIFIED`, ≥2 `SourceRef` provenance.
- δ⁺ chain surfaced via the named result keys; `RunState` carries seam/memory/pareto/
  coverage + persisted reality verdict; `omega_gate.passed`.
- Memory fabric deposits the VERIFIED claim (≥1) and passes `gate_zeta` (regression for
  the hollow-deposit facade).
- Self-ascent: appends once, no `APPEND_FAILED`; **idempotent** across repeated runs
  (property-based, 1..6 runs → exactly one suggestion in the isolated queue).
- Input-sensitivity and the fail-loud `ValueError` on a too-vague dream are asserted.
- A property test confirms any sufficiently-concrete dream yields both mandated notes.

Run: `PYTHONPATH=src python3 -m pytest tests/test_lumencrucible_characterization.py`
(the repo's tests import the installed `gen` package, hence `PYTHONPATH=src`).

## Remainder (out of scope — not `lumencrucible.py`)
- `tests/test_lumencrucible.py` (legacy, deselected per the team no-churn rule) was already
  red on `main`: the jetpack case failed at the `self_ascent` assertion (the facade fixed
  here) and its `multi_domain.software` assertion depends on pipeline modules unavailable
  in this offline env. After the fix it advances past `self_ascent`/`delta_plus_reality`
  but its `claim.status in ("VERIFIED","verified")` line pre-dates the enum-correctness fix
  (it expects a string). The authoritative signal is the new characterization test; the
  legacy file is left untouched. Net legacy pass/fail count is unchanged by this task.
- `tests/test_phase_omega.py::test_e2e_full_cert_chain_..._from_lumen_...` fails on `main`
  and after the fix with a `SourceRef(...)` constructor bug **in the test itself** (missing
  `retrieved`) — a separate file, out of this task's scope.
