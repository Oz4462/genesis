# Depth-Audit: `src/gen/bolted_joint.py`

**Verdict: REAL.** No source defect found; no source edits made ("change nothing if correct").

The bolted-joint preload/load-sharing math (Shigley/VDI-2230 closed forms) is genuine. All five functions implement exactly the documented algebraic relations; the DFM check composes them correctly and applies the documented fail-loud guards. The new `tests/test_bolted_joint_characterization.py` proves this with the exact anchor examples + Hypothesis properties for the invariants + mandatory negative paths.

## Headline-Claim (from module docstring + T05 spec)

> preload_from_torque(T=10000 N·mm, d=10 mm, K=0.2)==5000 N; joint_stiffness_factor with k_b==k_m==0.5 → C=0.5 and extremes (kb>>km→C≈1, kb<<km→C≈0); bolt_load==F_i+C·P (==F_i at P=0); separation_load==F_i/(1−C) (==10000 N for F_i=5000, C=0.5) and member clamp F_i−(1−C)·P ==0 exactly at P=P_sep; bolted_joint_check returns preload/C/bolt_load/bolt_stress/separation_load/separation_margin/yield_safety + ok True only when neither separates (P<P_sep) NOR yields (bolt_stress<=proof_strength). The preloaded bolt_stress (F_i+C·P)/A_t is strictly > naive nominal P/A_t.

## Beweis (computed, not canned)

- All public constructors/calls use the real module API; no invented fields.
- Anchor pins (exact per spec):
  - `preload_from_torque(10000, 10, 0.2) == 5000.0`
  - `joint_stiffness_factor(0.5, 0.5) == 0.5`; stiff → >0.999999, soft → <1e-6
  - `bolt_load(Fi, P, C) == Fi + C*P`; `bolt_load(Fi, 0, C) == Fi`
  - `separation_load(5000, 0.5) == 10000`; `Fi - (1-C)*P_sep == 0` (abs_tol 1e-12)
- bolted_joint_check regimes exercised:
  - safe case (P << P_sep, stress < proof) → ok=True
  - separates-but-not-yield (P > P_sep, high proof) → ok=False (sep only)
  - yields-but-not-separate (modest P, low proof) → ok=False (yield only)
  - ok flips exactly on the two failure modes.
- Preloaded vs naive: with legacy anchor numbers (Fi=25000, C≈0.333, P=10000) → 488.5 > 172.4 strictly.
- Facade-killer:
  - (a) changing P / proof / kb produces observably different bolt_load / yield_safety / ok (input consumed).
  - (b) every documented guard raises ValueError with the exact message (non-positive d/k, stiffness, C ranges, A_t/P/proof).
- Property-based (Hypothesis, >=20 examples, derandomize):
  - C always ∈ [0,1] for kb,km >0
  - bolt_load(Fi,P,C) == Fi + C*P and floor at P=0
  - member clamp force exactly 0 at P_sep
  - check is deterministic (A5 contract)
- Negative paths cover delegated (preload/factor) + direct check guards.
- Determinism: identical inputs → identical dict (incl. math.inf yield_safety path exercised indirectly via high safety).
- Explicit recipe-contract test exercises the exact call shape used by the pre-existing CheckRecipe wiring (physics_selection/validators auto-select for "bolted joint (preloaded load sharing)").

A constant-stub or inverted formula (wrong IPC-style, wrong (1-C), missing < vs <=) would have failed the anchors, the zero-member test, the regime ok-flips, the strict > , and the property identities.

## Änderungen (scope-respecting)

- `src/gen/bolted_joint.py`: **NO EDITS**. All formulas, guards, return keys, separation predicate (P < P_sep), and yield predicate (stress <= proof) were already correct and matched the docstring + spec. (Verified independently by driving the characterization test to green on the pre-existing implementation.)
- `tests/test_bolted_joint_characterization.py`: new authoritative file (19 tests + 5 Hypothesis properties). Pins every listed anchor, regime, negative, and invariant. Leaves legacy `tests/test_bolted_joint.py` (20 tests) untouched.
- `docs/audit/DEPTH_AUDIT_bolted_joint.md`: this file.

Isolation: only the three files in the declared scope. The characterization test imports only the module under review + stdlib/hypothesis/pytest (all allowed).

## 4 Linsen (L1–L4) + erweiterte Selbstkontrolle

- **L1 (Wahrheit / Provenance):** Every numerical claim (5000 N, 10000 N, C=0.5, member=0, stress > naive) is computed from the live functions against hand-verified algebra (F_i = T/(K d), C=kb/(kb+km), F_b=F_i+C P, P_sep=F_i/(1-C), F_m=0 at sep). No unsourced constants. Matches "keine stillen Defaults".
- **L2 (Drift / Grounding):** Module docstring, function docstrings, and runtime behaviour are identical (verified by the char test). No drift from the Shigley/VDI reference. A5 determinism property holds. The "preload axis a nominal misses" is demonstrated by concrete > comparison, not asserted.
- **L3 (Vollständigkeit / Naht):** Covers happy path + all listed edges + the three distinct ok regimes + delegated guards + universal invariants. Explicit test of the CheckRecipe call shape (the "bolted joint (preloaded load sharing)" wiring via physics_selection/validators) proves the seam to auto-select / δ-physics is live and not a facade. The new char file complements (does not replace) the legacy test. Seams to structural.py / physics_validation (the axis they miss) documented in the module itself. No missing negative per "a gate without a test does not exist".
- **L4 (Realisierbarkeit / Edge):** Scoped to genuine public-API defects only (no blanket NaN/inf guards added). All inputs positive by construction in properties; guards are the documented non-positive ones. Tests are fully offline, deterministic, use only declared deps. Hypothesis + concrete anchors together make the correctness falsifiable. No change to public signatures (downstream callers unaffected). The asymmetry between separation_load (C<1) and bolt_load (C<=1) properties is explicitly documented with WHY comments (rubberduck finding addressed).

**Selfkontrolle (DoD):**
- [x] Interface erfüllt, Typen geprüft (existing + char)
- [x] Tests grün (19 in char + legacy 20; incl. mandatory negatives)
- [x] No Ledger (pure math, no factual claims)
- [x] Gate-Bedingung: N/A (DFM helper, used by higher δ-physics)
- [x] Doku-Datei des Moduls: no change needed (already accurate)
- [x] 4 Linsen applied + PLATFORM_PLAN cross-check (this audit)
- [x] L1–L4 bestanden mit Belegen oben
- [x] No invented values / still-silent-defaults
- [x] Full relevant pytest slice green
- [x] Scope strictly honored (only the three listed files touched in this worktree)

## Evidence vs. backlog / PLATFORM_PLAN

Satisfies the assigned T05 task and the bolted-joint / "preload load-sharing axis" item (δ-Physik + DFM as core, per GENESIS_PLATFORM_PLAN and the humanoids/δ-axes work). Contributes the honest preloaded-vs-nominal distinction that nominal stress checks in structural.py miss.

## Run (this task)

```
PYTHONPATH=src python3 -m pytest tests/test_bolted_joint_characterization.py -q
...................                                                      [100%]
19 passed
```

(The authoritative characterization file.)

Legacy (untouched, per isolation rule) stayed green:

```
PYTHONPATH=src python3 -m pytest tests/test_bolted_joint.py -q
....................                                                     [100%]
20 passed
```

Combined relevant slice (char + legacy, no source change): 39 passed.

Legacy test files untouched. Zero collision with any parallel worktree (bolted_joint.py is this task's sole source).

Verdict stands: **REAL** — the five closed-form load-sharing relations (plus the check that composes them and exposes the missed preload axis) are genuine.