# Depth-Audit: `src/gen/discovery/active_search.py`

**Verdikt: REAL.**

The InfoBAX-style uncertainty-sampling loop in `active_search.py` genuinely orders
evaluation by binary entropy (expected information gain), not by list iteration or
index. The gate is the sole oracle. Characterization test proves the contract.

## Headline-Claim (from module + PLATFORM_PLAN / HORIZON)

> "pick the next evaluation that most reduces uncertainty about ... which candidates
> the gate passes" via uncertainty sampling; "selection only chooses the ORDER of
> evaluation, never a verdict"; "Deterministic, offline, pure-python (math only)."

## Evidence (what the tests pin)

All assertions executed against the **real** module (no mocks of active_search):

- `binary_entropy(0.5) == 1.0`; `binary_entropy(0.0) == binary_entropy(1.0) == 0.0`.
- Property-based (Hypothesis): entropy always in [0,1], symmetric `H(p)==H(1-p)`, max==1.0 only at p=0.5.
- `PassModel([]).predict(any) == 0.5`; after gated examples, `predict` is inverse-distance-weighted and shifts toward the label of nearby examples (exact at match, ~0.5 at midpoint between opposing labels).
- `select_most_informative` returns argmax-EIG index; on ties returns lowest index.
- `active_select`:
  - `gate_calls == min(budget, len(candidates))` and stops at pool exhaustion (budget>>N yields exactly N calls).
  - Deterministic: identical input -> identical `ActiveResult` (gated order, passing set, count).
  - Order genuinely depends on features+labels: constructed 4-candidate case (feats at 0/100/1/50 with labels F/T on first two) yields gated order `[0,1,3]` (3 has EIG=1.0, 2 has low EIG) while uniform sequential would have produced `[0,1,2]`.
- Negative: `budget < 0` raises `ValueError("budget must be >= 0")` (exact match).

No edit to `active_search.py` was required — all properties already hold (per "change nothing if correct").

## Changes

- Added `tests/test_active_search_characterization.py` (new authoritative characterization test; legacy `test_active_search.py` untouched).
- Added `docs/audit/DEPTH_AUDIT_active_search.md` (this file).
- `src/gen/discovery/active_search.py` — **no changes**.

## Tests

`tests/test_active_search_characterization.py` (new) + pre-existing discovery tests:
- 12 new tests (examples + 1 Hypothesis property + negative + determinism + ordering-proof).
- All pass using only the module under test + stdlib + Hypothesis (already declared under dev extras).

Command: `python -m pytest tests/test_active_search_characterization.py -q --tb=short`

## 4 Linsen

- **L1 (Wahrheit):** Entropy math, IDW predict, EIG-max selection, budget accounting, and the exact error message are all asserted against live execution. No fabricated ordering.
- **L2 (Drift):** Two runs with same inputs produce identical trajectories (A5). Different feature/label assignments produce observably different gate order.
- **L3 (Vollständigkeit/Naht):** Proves the "selection by uncertainty not iteration" claim that the controller and campaign rely on; the public `select_most_informative` and `active_select` are both covered. No jetpack here; no protected demo to regress.
- **L4 (Realisierbarkeit):** Budget<0 fails loud; budget=0 and exhaustion are honest (0 calls, N calls). No NaN/inf guards added (none needed; math paths stay in [0,1] and produce correct EIGs); only genuine defect scope per team decisions.

## Relation to GENESIS_PLATFORM_PLAN / discovery STATUS

Satisfies the "active_search.py is real uncertainty-sampling" item (2026-06-23 decisions). Contributes to honest frontier / self-driving-lab budget allocation without silent iteration fallback.

**Result:** REAL. The uncertainty-sampling loop earns its description. No source modification.
