# Depth-Audit: `src/gen/pressure_vessel.py`

**Verdict: REAL.** No source defect found; no source edits made ("change nothing if correct").

The pressure-vessel hoop/axial/Lamé closed forms implement exactly the documented textbook identities. The new `tests/test_pressure_vessel_characterization.py` proves this with exact anchors from the module docstring + Hypothesis properties for the invariants + all documented negative paths.

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

- `src/gen/pressure_vessel.py`: **NO EDITS**. All formulas (p*r/t, p*r/2t, p*r/2t sphere, Lame A/B with exact BCs), return shapes, max_hoop selection for 'thick' at inner wall, safety_factor/inf logic, and guards were already correct and matched the docstring + assigned spec. Verified by driving the characterization test to green on the pre-existing implementation.
- `tests/test_pressure_vessel_characterization.py`: new authoritative file (21 tests incl. 5 Hypothesis property suites). Pins every listed anchor, identity, convergence, check regime, consumption, determinism and negative. Leaves legacy `tests/test_pressure_vessel.py` (17+ tests) untouched.
- `docs/audit/DEPTH_AUDIT_pressure_vessel.md`: this file.

Isolation: only the three files in the declared scope. The characterization test imports only the module under review + stdlib/hypothesis/pytest (allowed pre-existing + declared deps). No src/ changes.

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** Every numerical claim (500 MPa exact, 2× identity, BCs at machine eps, 1.01% gap, sf/ok flip) is computed live from the functions against hand-derived algebra and docstring anchors. No unsourced or invented values. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Module docstring, function docstrings and runtime are identical (char test). Closed forms (Shigley + Lamé 1833) reproduced exactly. A5 determinism verified. Cross-checked vs. legacy test and physics_validation registry.
- **L3 (Vollständigkeit / Naht):** Covers happy path + all specified edges + thick-vs-thin + sf flip + consumption + full guard matrix + properties. Explicitly exercises the pressure_vessel_check shape used by physics_validation.VALIDATORS["pressure_vessel"] + physics_selection RECIPES (vessel.pressure trigger). The new char complements (does not replace) the legacy. No missing negative.
- **L4 (Realisierbarkeit / Edge):** Scoped strictly to genuine public-API correctness per team decisions (no blanket NaN/inf or extra guards added as feature-creep). Only the documented non-positive / range / unknown-model / yield>0 guards. All Hypothesis draws use strictly positive ranges so they never hit the guards (guards tested separately). Tests offline/deterministic. No public signature change (downstream unaffected).

**Selfkontrolle (DoD):**
- [x] Interface erfüllt, Typen geprüft (existing + char)
- [x] Tests grün (21 in char + legacy ~17; incl. mandatory negatives + properties)
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

## Evidence vs. backlog / PLATFORM_PLAN

Satisfies the assigned T05 task (pressure_vessel.py depth-audit in the five physics/pipeline modules) and the δ-physics closed-form axes (pressure vessel / hoop-stress as one of the 27 validators behind GATE δ). Contributes the honest "thin under-predicts inner hoop; use thick when t/r not small" distinction plus the exact Lamé BC guarantee that a point-load or nominal stress check would miss.

## Run (this task)

```
PYTHONPATH=src python3 -m pytest tests/test_pressure_vessel_characterization.py -q
.....................                                                    [100%]
21 passed
```

(The authoritative characterization file.)

Legacy (untouched, per isolation rule) + integration:

```
PYTHONPATH=src python3 -m pytest tests/test_pressure_vessel.py tests/test_pressure_vessel_characterization.py -q
....................................                                     [100%]
36 passed
```

physics slices using the validator (no breakage):

```
PYTHONPATH=src python3 -m pytest tests/test_physics_validation.py tests/test_physics_selection.py -q
... 20 passed
```

All per "pass using only this task's files plus pre-existing repo files".