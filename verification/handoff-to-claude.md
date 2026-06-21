# Handoff to claude-code from Hermes Head (Grok)

**Date:** 2026-06-21  
**Project:** GENESIS ( /home/genesis/genesis )  
**From:** Hermes Head (grok-internal)  
**To:** claude-code

## Exact sub-goal + acceptance criteria

Review the current implementation of `check_advanced_dfm` in `src/gen/cad/manufacturing_check.py`, with focus on the Laser and PCB blocks (the multi-process advanced DFM first stone).

Apply the project's 4 Linsen (L1 Truth, L2 Drift, L3 Seam, L4 Realizability) + GENESIS principles (honest gaps, sourced rules, no vacuous passes).

Suggest any small, bounded improvements or additional test cases if needed. Do **not** make large refactors.

Scope: only this function + related calls in the file + the test in `tests/test_manufacturing_check.py` for advanced_dfm.

## Relevant context / file list

- src/gen/cad/manufacturing_check.py (the check_advanced_dfm function, ProcessDFM, AdvancedDFMReport)
- src/gen/dfm.py (Laser and PCB constants and gap functions)
- tests/test_manufacturing_check.py (the advanced_dfm tests)
- Cross reference: pipelines/fertigungs.py and integrator.py for how the report is used (for seam context, but do not change them)

Current state from Head's internal review:
- Stein 1 (CNC) verified as solid (sourced, honest gaps).
- Laser block: thickness check, gaps for in-plane/form, min feature, bridging, kerf.
- PCB: all as gaps (correct, since no copper geometry in mechanical spec).
- Overall: builds the report with total_gaps, issues, cost stub, gcode for CNC.

## Data contracts / constraints

- Keep the "necessary, not sufficient" stance (gaps vs issues).
- All numbers must stay sourced (no new fabricated values).
- Follow existing style (dataclasses, clear comments).

## Explicit requirements

- Documentation updated as you go (small updates in code comments if needed).
- Use 4 Linsen in your reasoning (document L1-L4 in your output).
- If you find a small bounded improvement (e.g. additional test case, clearer gap message, missing edge), propose it precisely.
- Run ruff format/check on changed files.
- Output: summary of review (4 Linsen), list of findings (good/bad), specific suggestions for small changes if any, updated test ideas.

**After you finish, the Hermes Head (Grok) will read everything, grep wiring, run tests where possible, update verification-log and CodeKnowledge, and apply full DoD.**

## Required output format

- Your reasoning with 4 Linsen.
- Summary of current state.
- Findings (positive + any issues/gaps).
- Specific, small, bounded suggestions (with code snippets if change).
- Any test ideas.
- Confirmation that ruff is clean on touched files.

Must satisfy the project's 4 Linsen and our Hermes DoD (evidence, honest gaps, sources).

## Scope boundaries

Only the advanced DFM first stone area. No changes to other stones or big architecture unless explicitly small.

If scope creeps, stop and note.

This is a review + suggest small bounded improvement task. If no improvement needed, say so clearly.

After you, Head will verify and decide next routing.

Good luck. Report back the artifacts.
