# Depth-Audit: `src/gen/agents/synthesizer.py`

**Verdict: PARTIAL-FACADE (now fixed) → REAL.**

The synthesizer's headline claim — "groups VERIFIED claims into distinct, named
solution approaches, deduplicating duplicates while keeping genuinely-different
alternatives" — was only partially true. The grounding/abstention logic is real, but
the **deduplication had a silent-loss defect**.

## The defect (confirmed)

`Synthesizer.run` computed the dedup identity (`ap_id`) from the **verified-filtered**
`tradeoffs` list, *after* stripping any id the verifier rejected:

```python
tradeoffs = [cid for cid in raw_t if cid in verified and ...]   # strips unverified ids
ap_id = approach_id(run_id, name, grounding, tradeoffs)          # dedup on STRIPPED fields
```

Consequence: a proposal whose only distinguishing field was a *presented-but-unverified*
tradeoff id (e.g. `"c-extra"`) had that id stripped first, so its `ap_id` collapsed onto an
earlier approach and it was silently dropped as a "duplicate". A genuinely-different
alternative the model offered was lost — an L2-drift / "keine stillen Defaults" violation.

This was provable on `main`: the repo's own legacy test
`tests/test_synthesizer.py::test_duplicate_approach_is_dropped_and_logged` asserts
`len(approaches) == 2` for exactly this payload and **failed** (`assert 1 == 2`).

## The fix

Confined to `synthesizer.py`. The dedup identity now reflects the approach **as the model
presented it** — `name + presented grounding + presented tradeoffs` (deduplicated,
order-insensitive) — instead of the verified-filtered fields:

```python
presented_g = list(dict.fromkeys(raw_g))
presented_t = list(dict.fromkeys(raw_t))
ap_id = approach_id(run_id, name, presented_g, presented_t)
```

Crucially, **grounding validation is NOT weakened**: the emitted `Approach` still carries
only verified ids (`grounding`/`tradeoffs` built from the `verified` set), so no unverified
id is ever surfaced — the presented ids feed the hash digest only. True duplicates
(identical presented fields) still collapse to one and each drop is logged with the
`drop duplicate approach` line. Because distinct proposals now get distinct `ap_id`s, the
downstream architect (which anchors a `Specification` by `approach_id`) no longer risks two
approaches sharing one id.

## Evidence the module is now REAL (not a facade)

New test file `tests/test_synthesizer_characterization.py` drives the real
`Synthesizer.run` over a deterministic `ScriptedLLM` (the unit under test is never mocked):

- **Input-sensitivity** — flipping only the third proposal's presented tradeoff between a
  duplicate value and a distinct value moves the surviving count `1 → 2`, proving the field
  is genuinely consumed (`test_output_count_is_sensitive_to_presented_tradeoffs`).
- **Survival** — the distinct-by-unverified-tradeoff proposal survives, and the emitted
  approach surfaces only verified ids (`c-extra` never appears; ids are distinct).
- **Dedup still total** — N byte-identical proposals collapse to exactly one with `N-1`
  logged drops (`test_true_duplicates_still_collapse_and_log`, plus a Hypothesis
  idempotence property).
- **Fail-loud guard intact** — a fabricated approach whose grounding is entirely unverified
  is dropped and logged, never emitted (`test_fabricated_approach_without_verified_grounding_is_dropped`).
- **Property-based invariant** — distinct presented tradeoff *sets* always yield distinct
  ids while permutations of the same set do not (order-insensitivity), via Hypothesis.

All 10 new tests pass; the previously-failing legacy test now passes; the downstream
`test_phase_beta_acceptance`, `test_phase_gamma_acceptance`, and `test_architect` suites
(30 tests) remain green. Backlog tie-in: this hardens the β-chain synthesizer named in
`GENESIS_PLATFORM_PLAN.md` (Synthese-/Approach-Stufe) against silent option loss.
