# Depth Audit — `src/gen/memory_fabric.py` (GATE ζ)

**Verdict: REAL.** No source edit required ("change nothing if correct").

## Scope
`memory_fabric.py` is the audit layer above the verified-facts memory: it builds a
run-level receipt (`build_memory_fabric_certificate`) of what entered shared memory and
what prior facts were reused, then validates that receipt (`gate_zeta`). The module is
deterministic and LLM/DB-free — it only checks the receipts produced by lower layers.

## Facade-detection findings
Every headline output is genuinely **derived from inputs**, not canned:

- **Deposits are the VERIFIED subset of claims.** `build_memory_fabric_certificate`
  comprehends `state.claims`, keeping only `ClaimStatus.VERIFIED`, and preserves each
  claim's non-blank source ids via `_claim_sources`. The characterization test proves
  the deposit set *changes* when the VERIFIED subset changes (VERIFIED→REFUTED removes a
  deposit) and that a REFUTED claim alongside a VERIFIED one yields exactly one deposit.
- **`run_id` is copied from the live question**, not hardcoded — verified by building
  against a non-default run id (`run-derived-xyz`) and asserting `cert.run_id ==
  state.question.run_id`.
- **Recall links mirror the duck-typed recall results** (per-result query/tau, per-fact
  id/score/sources), with the query stripped — proving the mapping consumes structural
  input.
- **`gate_zeta` has teeth.** A fully-healthy certificate passes; introducing a single
  documented violation (recall score > tau) flips `passed` True→False with the exact
  `MEMORY_RECALL_OUTSIDE_BAND` code. The empty certificate passes only as honest
  abstention (`NOT_ENOUGH_BASELINE`, no deposits/recalls).

## Tests added (`tests/test_memory_fabric_characterization.py`)
Complements the comprehensive legacy `test_memory_fabric.py` with an adversarial,
facade-killing angle (11 tests):

1. Builder filters VERIFIED, drops REFUTED, preserves source ids, derives `run_id`
   (spec 1).
2. Deposit set reacts to a status change (input genuinely consumed).
3. Recall links derived from recall results.
4. Empty certificate → honest abstention pass, `NOT_ENOUGH_BASELINE` (spec 2).
5. Fail-loud: `MEMORY_DEPOSIT_NOT_VERIFIED`, `MEMORY_RUN_MISMATCH`,
   `MEMORY_DRIFT_ALERT` (spec 3).
6. Fail-loud: `MEMORY_RECALL_WITHOUT_CALIBRATION`, `MEMORY_RECALL_OUTSIDE_BAND`
   (spec 4).
7. Single-defect-flips-verdict (gate is not a rubber stamp).
8. Property-based (Hypothesis): for any status mix, deposits == VERIFIED ids AND the
   built certificate always passes its own gate.

## 4 Linsen
- **L1 (Wahrheit):** No fabricated facts — deposits trace to VERIFIED claims; the gate
  rejects non-VERIFIED deposits, run mismatch, drift, uncalibrated/out-of-band recalls.
- **L2 (Drift):** `run_id` and recall provenance are copied, not invented; the
  source-mismatch and run-mismatch gates guard against drift between layers.
- **L3 (Vollständigkeit/Naht):** Every documented `GateFailure.code` in the spec is
  exercised; the empty-abstention seam and the healthy→defect transition are both
  covered.
- **L4 (Realisierbarkeit):** Pure deterministic code, stdlib + already-declared deps
  (`hypothesis`); tests run offline with no network/DB.

## Result
`tests/test_memory_fabric_characterization.py`: 11 passed. Legacy
`tests/test_memory_fabric.py`: 29 passed. Source unchanged.
