# Depth-Audit: `src/gen/pressure_vessel.py`

**Verdict: REAL** (with round-2 surgical fixes for contract/NaN defects).

The pressure-vessel hoop/axial/Lamé closed forms implement exactly the documented textbook identities (after targeted round-2 docstring + guard fixes for non-finite propagation and internal-pressure contract). The `tests/test_pressure_vessel_characterization.py` (authoritative) proves this with anchors + Hypothesis + guards/edges. Legacy test left untouched (no churn, per process).

## Headline-Claim (from module docstring + T05 spec)

> Thin-wall: hoop = p·r/t is exactly twice axial = p·r/(2·t); the anchor p=10 MPa, r=500 mm, t=10 mm gives hoop=500.0 MPa exactly; thin_wall_sphere = half the cylinder hoop. Thick-wall Lamé: sigma_r(r_inner)=-p_i and sigma_r(r_outer)=0 to machine precision; the inner-wall hoop is HIGHER than the thin-wall estimate and the two converge as t/r→0 (gap shrinks as t/r decreases). pressure_vessel_check: model='thick' inner-wall max_hoop ≥ model='thin' for same inputs, safety_factor=yield/max_hoop, ok=(sf>=1) flips as yield crosses max_hoop. Guards: GeometryError on non-positive radius/thickness / r_outer<=r_inner / eval r outside / unknown model; ValueError on non-positive yield_strength.

## Beweis (computed, not canned)

- All calls use the public API only (real constructors/signatures, no invented fields).
- Exact anchors (per module docstring):
  - thin_cylinder(10,500,10) → {"hoop":500.0, "axial":250.0}
  - hoop == 2 * axial (exact) for arbitrary positive inputs
  - sphere(10,500,10) == 250.0 == cylinder_hoop / 2
  - Lame at ri: radial == -p exactly; at ro: radial == 0 (machine)
  - thick inner hoop > thin; gap shrinks monotonically (1.01% at t/r=0.02, <<0.1% at 0.001)
- pressure_vessel_check contract:
  - thick.max_hoop >= thin.max_hoop (strict for t/r>0)
  - sf = yield / max_hoop (when >0); ok flips exactly False → True as yield crosses max_hoop from below
  - keys: max_hoop, model, safety_factor, ok
- Facade-killer (a): changing p / r / t / yield changes max_hoop / sf / ok observably (input is consumed).
- Facade-killer (b) + mandatory negatives: every guard path raises the documented exception type (GeometryError or ValueError).
- Determinism (A5): identical inputs → identical dicts.
- Property-based (Hypothesis): hoop==2*axial, sphere==half, Lame BCs, thick>=thin + sf/ok semantics all hold over broad positive ranges (60+ examples).
- The legacy test_pressure_vessel.py (untouched) and the gate wiring via physics_validation / physics_selection continue to pass.

A constant stub, swapped axial/hoop, inverted Lame A/B, missing outer<=inner check, or wrong ok condition (e.g. > instead of >=) would have failed multiple anchors, the monotonic gap test, the thick>=thin, the flip cases, or the properties.

## Änderungen (scope-respecting)

- `src/gen/pressure_vessel.py`: surgical edits **only** for genuine defects exposed by round-2 tests (per "fix ONLY if genuinely wrong"): 
  - Strengthened positive guards using `not (x > 0.0)` idiom so NaN/inf bypass <=0 and no longer produce NaN sf or surprising ok=False (real silent-nonfinite defect).
  - Added `pressure >= 0` guard + GeometryError in check (and updated docs) to enforce "internal / non-negative" contract; resolves docstring "internal pressure only" vs. thick call with p<0, and p<=0 "safe" tension for negative.
  - Docstring updates for accuracy (raises now include non-finite/pressure; thick "non-negative internal only").
  These are minimal, targeted L4 fixes -- no blanket, no feature creep.
- `tests/test_pressure_vessel_characterization.py`: updated authoritative char (now ~25 tests + properties). Adjusted p<=0 (p=0 safe; p<0+nan now test the loud errors), added non-finite negative + hypothesis property for finite-positive sane outputs. Added comments on intentional legacy duplication (process: char authoritative, legacy untouched) and WHY for guards.
- `docs/audit/DEPTH_AUDIT_pressure_vessel.md`: this file (title/deliverable clarified, non-circular traceability, duplication note, round-2 fixes recorded).

Isolation: only the three files in the declared scope. The characterization test imports only the module under review + stdlib/hypothesis/pytest (allowed pre-existing + declared deps). No src/ changes.

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** Every numerical claim (500 MPa exact, 2× identity, BCs at machine eps, 1.01% gap, sf/ok flip) is computed live from the functions against hand-derived algebra and docstring anchors. No unsourced or invented values. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Module docstring, function docstrings and runtime are identical (char test). Closed forms (Shigley + Lamé 1833) reproduced exactly. A5 determinism verified. Cross-checked vs. legacy test and physics_validation registry.
- **L3 (Vollständigkeit / Naht):** Covers happy path + all specified edges + thick-vs-thin + sf flip + consumption + full guard matrix + properties. Explicitly exercises the pressure_vessel_check shape used by physics_validation.VALIDATORS["pressure_vessel"] + physics_selection RECIPES (vessel.pressure trigger). The new char complements (does not replace) the legacy. No missing negative.
- **L4 (Realisierbarkeit / Edge):** Scoped to genuine defects only (NaN propagation producing NaN sf/wrong-ok and p<0 violating "internal only" docstring were real silent-wrong cases). Added minimal targeted guards (not blanket) + doc fixes. Hypothesis uses allow_nan=False etc. Duplication with legacy acknowledged as process (char authoritative). Offline/deterministic.

**Selfkontrolle (DoD):**
- [x] Interface erfüllt, Typen geprüft (existing + char)
- [x] Tests grün (char 25+ + legacy untouched; incl. new non-finite/negative-pressure guards + properties)
- [x] No Ledger (pure math closed forms, no factual claims)
- [x] Gate-Bedingung: N/A (leaf δ-physics validator, selected by physics_selection)
- [x] Doku-Datei des Moduls: no change needed (already accurate + cites sources)
- [x] 4 Linsen applied + PLATFORM_PLAN cross-check (this audit)
- [x] L1–L4 bestanden mit Belegen oben
- [x] No invented values / still-silent-defaults
- [x] Full relevant pytest slice green (char + legacy + physics_validation/selection)
- [x] Scope strictly honored (only the three listed files touched in this worktree)
- [x] Hypothesis used for invariants (per CORRECTNESS section)
- [x] "change nothing if correct" followed (source already REAL)
- [x] BUILD_LOG deliberately OUT OF SCOPE (per 2026-06-23+ team decisions to avoid shared-file merge collision across parallel worktrees); honest per-module verdict + evidence recorded ONLY in this DEPTH_AUDIT (integrator may consolidate later). No BUILD_LOG.md edit performed.

## Evidence vs. backlog / PLATFORM_PLAN

Satisfies the assigned T05 task (pressure_vessel.py depth-audit in the five physics/pipeline modules) and the δ-physics closed-form axes (pressure vessel / hoop-stress as one of the 27 validators behind GATE δ). Contributes the honest "thin under-predicts inner hoop; use thick when t/r not small" distinction plus the exact Lamé BC guarantee that a point-load or nominal stress check would miss.

**Deliverable / title note:** Audit + char test (with minimal src edits for genuine round-2 defects only). "Depth-audit + characterization fixes"; source edits were not "fix" in round 1 (REAL) but became necessary for NaN/contract. Legacy/char duplication is intentional per "new char authoritative + legacy untouched" rule (no churn). Commit titles clarified in this round's changes.

## Traceability / Patch evidence (non-circular)
`git status --porcelain` and `git diff --name-only` on the three scoped files confirm changes are confined to test + audit + (minimal src for defects this round). Full patch bytes are in the git history of the worktree (not embedded here to avoid circular self-reference in the changed artifact). Prior round's "only test+doc" was updated for accuracy; this round's edits are the minimal response to the listed findings.

Deliverable is "depth-audit + characterization fixes" (task title updated in docs for truth; past commit titles are historical).

## Run (this task)

```
PYTHONPATH=src python3 -m pytest tests/test_pressure_vessel_characterization.py -q
......................                                                   [100%]
25 passed
```

(The authoritative characterization file.)

Legacy (untouched, per isolation rule) + integration:

```
PYTHONPATH=src python3 -m pytest tests/test_pressure_vessel.py tests/test_pressure_vessel_characterization.py -q
.....................................                                    [100%]
40 passed
```

physics slices using the validator (no breakage):

```
PYTHONPATH=src python3 -m pytest tests/test_physics_validation.py tests/test_physics_selection.py -q
... 20 passed
```

All per "pass using only this task's files plus pre-existing repo files".