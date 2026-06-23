# DEPTH_AUDIT — `src/gen/future_ideas.py`

**Verdict: REAL.** Task T01 (depth-audit + fix the five gated future-product specs).

## Headline claim under audit
Each of the five builders (`delivery_drone_spec`, `home_battery_spec`, `harvest_arm_spec`,
`hydraulic_boom_spec`, `exo_knee_spec`) returns a COMPLETE, GENUINELY DATA-DRIVEN, GATED
`Specification`, run through the SAME `pipeline.assess_specification` machinery as every other
spec, firing its real δ-physics axes to an HONEST verdict — never a masked pass.

## What was checked (facade-detector, `tests/test_future_ideas_characterization.py`)
The new characterization test is deliberately distinct from the legacy `test_future_ideas.py`
(happy-path verdict + artifact bundle). It attacks the two facade failure modes:

**(a) Driving input is genuinely consumed — the specs are computed + wired, not hollow:**
- `test_derived_values_recompute_from_their_declared_inputs` — every `DERIVED` quantity's
  `derivation.inputs` resolve to real quantities, and re-evaluating the formula with the SAME
  safe evaluator the γ-gate uses reproduces the declared value (rel 1e-9). Catches a derived
  value that is secretly a hand-typed constant divorced from its formula, and a dangling
  derivation input.
- `test_scaling_the_load_scales_the_bending_stress` — **property-based (Hypothesis)**: the
  cantilever stress `q_sigma_nom = 6·F·L/(b·h²)` is exactly linear in its load `q_force`;
  scaling the force by an arbitrary k ∈ [0.1, 10] scales the recomputed stress by k. A canned
  constant would ignore the input and break this invariant. This is the formal facade-killer.
- `test_grounded_values_and_all_references_resolve` — no dangling ids anywhere: every
  `GROUNDED` quantity's claim ids, every BOM grounding, every `claim_ids_used`, and every
  geometry-param / component-quantity / material-density / constraint reference resolves to a
  real id in the same spec.
- `test_each_spec_fires_real_physics_axes_and_is_honestly_verified` — each spec fires ≥1
  δ-physics axis (never zero = a vacuous spec-level pass), runs every indicated check with no
  gap, no constraint contradiction, and earns `physics_ok` + `overall == "physics_verified"`.

**(b) Fail-loud / abstention — the mandatory NEGATIVE tests (the gate is no rubber stamp):**
- `test_dropping_a_required_input_yields_an_honest_gap_not_a_masked_pass` — drop the drone's
  take-off mass (`q_mass`, an input to the rotor-hover check whose trigger `rotor.max_total_thrust`
  remains). `select_physics_checks` reports the axis as INDICATED-BUT-UNRUNNABLE (a gap), and
  the overall verdict is NOT `physics_verified` (it falls to an honest non-pass — `physics_incomplete`
  or `needs_clarification`). The gate cannot pass over a hole.
- `test_a_hollow_grounded_quantity_fails_loud_at_construction` — the data layer refuses a
  `GROUNDED` value with no backing claim (`UngroundedValueError`), so a future facade quantity
  cannot silently masquerade as grounded. Guards "kein faktischer Output ohne Quelle" at its root.

## Result of the audit
Every invariant held on all five specs on first inspection — exploratory scripts found **zero**
defects: no dangling derivation inputs, no derived/declared mismatch, no dangling grounding
claims, no dangling `claim_ids_used`/BOM grounding, no unresolved geometry/component/constraint
references, no duplicate quantity or claim ids, no conflicting same-measurand values, and every
spec fires its full signature axis set (drone 4, battery 2, harvest 5, hydraulic 3, exo 6) with
no gap and an honest `physics_verified`.

## Source change made (minimal, behavior-preserving)
Per "change nothing if correct," **no behavioral edit** was made — the module is REAL. The only
source change tightens type annotations to satisfy the project convention ("Jede neue Funktion
braucht Typ-Annotationen") and the task DoD ("add/keep type hints"): the imprecise `-> list`
return hints on `_dfm_quantities`, `_struct_quantities`, `_dfm_claims` and the five public
`*_claims()` builders are narrowed to `list[Quantity]` / `list[Claim]`, and `_link`'s
quantity-id parameters are annotated `: str`. Imports of `Claim` and `Quantity` were added for
these hints. All annotations are 100 % behavior-preserving (verified: legacy suite + consumers
stay green).

## 4 Linsen
- **L1 Wahrheits-Linse:** The five specs are honest — every grounded value resolves to a real
  VERIFIED claim, every derived value recomputes from its inputs, and the δ-physics verdict is
  earned (proven by the recompute + grounding-resolution tests). No fabricated constant survives.
- **L2 Drift-Linse:** Docstrings match behaviour (each spec really fires the axes it advertises;
  the negative test proves the gate can't drift into a masked pass). No claim/code divergence
  found. The only change (type hints) is annotation-level, no drift introduced.
- **L3 Vollständigkeits-/Naht-Linse:** All references at every seam resolve (geometry params →
  quantities, component quantity_ids/material_density → quantities, constraints → quantities,
  BOM/`claim_ids_used` → claims). The dropped-input negative test proves the spec↔selector↔gate
  seam surfaces a hole rather than swallowing it. Legacy + consumer (visionary_ideas, bundle)
  tests stay green.
- **L4 Realisierbarkeits-Linse:** Specs are deterministic, offline, no LLM; the property test
  explores the load space rather than one point; the gate honestly abstains when an input is
  missing. Tied to `GENESIS_PLATFORM_PLAN.md` "Fach-Pipelines / future-product specs" — these are
  the deterministic stand-in for the live-LLM architect, run through the real δ-gate, exactly as
  the plan requires.

## Backlog alignment
Satisfies the platform-plan intent that authored future-product specs are NOT a demo facade but
genuinely gated artifacts. The module's own declared open items (PLA-prototype vs production
material, first-order closed-form physics, historical `flight.*` measurand naming on the
energy axes) remain documented `gaps[...]` in each spec — honest, surfaced, out of scope for a
correctness audit.
