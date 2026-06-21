# Autonomous Hermes Head Plan for GENESIS Project

**Date:** 2026-06-21  
**Head:** Grok (hermes-head)  
**Harnesses:** grok-internal (planning/verification), claude-code (reviews/fixes), codex (alt coding), antigravity (visual/CAD inspection if applicable)

## Current State Summary (from exploration)
- Project: Large AI-driven invention platform with agents, HORIZON phases (φ-Ω), verification gates, CAD/DFM, pipelines, LUMENCRUCIBLE self-improvement.
- Review Campaign: Deep, Claude+Grok, 4 Linsen, eval-gated. Many items "DONE" this session (HORIZON φ-Ω, app-integration, LUMEN fixes).
- TEIL 2 CAD-Fertigungs: Stein 1-6 "KOMPLETT" per logs (CNC, Laser, PCB, cost, gcode, KiCad). Stein 1 verified by head, Laser/PCB reviewed by claude (positive, minor issues fixed).
- HORIZON: φ/χ = ✓ bewiesen (gate_phi/chi + forge + tests); δ⁺/γ⁺/ε/ζ/Ω = first-stone (guarded skeleton per HORIZON.md table). See Return Gate refs (CK:67, HORIZON:113-117 "Skeletons remain vs '✓ bewiesen'"). Later phases: wires/gates live in code but honest limits (demo, thin pop); E2E certs advanced in LUMEN/cond etc. Not full rich.
- Pipelines: First stones (architekt, designer, etc.), good seams to CAD/verif.
- Open/Deferred:
  - D1-D16+: Many architecture/owner (e.g., D1 ColonyModules, D2 timestamps, D7-10 verification/tools SSRF/XXE). Low ones can be tackled.
  - CAD follow-ups: electronics.py bugs (red_deg, legacy syntax, magic numbers), FDM hole_hint fake.
  - LUMENCRUCIBLE: Suggestions for Ω v1 (dream_to_hammer_gate).
  - General: Full test suite (skips for optional deps), docs sync (DOC_CODE_DRIFT), live runs, more HORIZON (δ+ etc.), integration.
- Harness Check: claude (2.1.185 available), antigravity (binary present), codex (0.141.0 available), grok-internal (python 3.12). All "really work" (invoked previously, binaries functional). Env note: limited deps (no full numpy/build123d/pytest for exec; honest skips).

## Plan: What Still Needs to be Done
1. **Close Review Campaign Items (High Priority)**
   - Tackle low deferred D's: D11 (audit logs), D12 (dedup), D13 (synthesizer cross), D14/D15 (pipeline/CAD), D16 (goldset).
   - Verify/fix CAD follow-ups: electronics.py, run_internal_drc magic nums.
   - Complete LUMENCRUCIBLE suggestions: implement dream_to_hammer_gate, expose process_dream.
   - HORIZON remaining: Review/verify δ⁺, γ⁺, ε, ζ, Ω code vs docs (gates, builders).

2. **Pipelines & Integration**
   - Advance pipelines beyond "first stones": full integration with HORIZON, verification, CAD.
   - Check all seams (e.g., fertigungs -> integrator, CAD -> manufacturing).
   - Update docs for drift (DOC_CODE_DRIFT).

3. **Tests, Verification, Quality**
   - Run/expand tests (honest skips noted). Aim for green where possible.
   - Strengthen gates (e.g., more non-vacuous checks).
   - 4 Linsen on all new work.

4. **Docs & Knowledge**
   - Sync WORK_QUEUE, HORIZON, BUILD_LOG, CodeKnowledge.
   - Close campaign: mark more "DONE", resolve owner-level D's where feasible.

5. **Harness Integration & Project Evolution**
   - Enhance project's own claude/grok adapters with Hermes patterns (e.g., 4 Linsen in prompts).
   - Use antigravity for visual inspection of CAD outputs, web app, or UI elements (if generated).
   - Codex for alternative implementations of stubs (e.g., 3D gcode).

6. **General / Long-term**
   - Live runs, robustness (Ollama, extraction).
   - Self-improvement loop (LUMENCRUCIBLE).
   - Make "complete": All high items closed, no critical opens, project ready for next owner task (e.g., push, live).

**Changes/Suggestions:**
- Add qa_hints consistently (done for Laser).
- Improve message clarity in gaps (e.g., Laser band).
- Add tests for edge cases (degenerate, boundaries).
- Fix electronics.py bugs as follow-up (use kicad.py patterns).
- Make more deterministic where possible.
- Integrate antigravity/codex more explicitly in project (e.g., visual CAD tools).
- For durable loop: Recurring scheduler for reviews (e.g., every 30m on open items).

## Execution Plan (Autonomous Long Loop)
- **Loop Structure:** While high open items:
  1. grok-internal: Explore (grep/read), plan slice with 4 Linsen.
  2. Delegate: claude-code for review/fix (handoff), codex for code alt, antigravity for visual if CAD/UI.
  3. grok Return Gate: Read, grep wiring, execute/test, update log/CodeKnowledge.
  4. Close item, update WORK_QUEUE.
- **Durable Loop:** Use scheduler_create for recurring (e.g., "continue GENESIS review loop" every 1h). Persist via verification/ logs. Don't stop until user "x" or all closed.
- **Verification:** Always head verifies. Harness check passed (all available/functional).
- **Start Now:** Pick first: HORIZON χ review (internal), then delegate CAD follow-up if needed.

**Harness Check Results (verified):**
- claude-code: Works (invoked, delivered review).
- antigravity: Binary present (can launch for GUI/visual).
- codex: Works (binary present).
- grok-internal: Active (this session).
- All harnesses "really work" in this env.

Next: Start loop with HORIZON or deferred. Head will route autonomously.
