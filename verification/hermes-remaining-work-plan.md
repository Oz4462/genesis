# Hermes Head — Remaining Work Plan for GENESIS
**Head:** Grok (hermes-head orchestrator)  
**Date:** 2026-06-21  
**Project:** /home/genesis/genesis (private github.com/Oz4462/genesis)  
**Goal:** Finish the project end-to-end via autonomous durable loop. Close high items using 4 Linsen (L1 Truth, L2 Drift, L3 Seam, L4 Realizability) + project DoD + Return Gate. Never stop until high-priority backlog resolved. Full Code Knowledge maintained.

## 1. Harnesses Verification — Confirmed Working (Evidence 2026-06-21)
All requested harnesses "really work":

- **claude-code**: 
  - Path: /home/genesis/.local/bin/claude → v2.1.185 (Claude Code)
  - Functional smoke: `claude -p 'respond with exactly: HARNESS-OK-CODE-42'` → responded exactly "HARNESS-OK-CODE-42". Prior full reviews (Laser/PCB DFM) delivered 4-Linsen reports.
  - Project usage: src/gen/llm/claude_cli.py + factory + tests/test_llm_cli_adapters.py (live cross-model pair test with grok).

- **grok-internal**:
  - Active this session + personas (thorough-researcher, loop-planner, careful-implementer, strict-reviewer...) + structured-cycle + vibe-verify + scheduler.
  - Used for all head planning/verification/4-Linsen/Return Gates/CodeKnowledge. Full wiring proofs.

- **antigravity**:
  - Binaries: /home/genesis/Downloads/Antigravity-x64/antigravity (206MB) + /usr/bin/antigravity (symlink).
  - Launches successfully (DevTools ws://... , IDE wizard shown in prior run). GUI harness for visual/CAD/UI inspection.

- **codex**:
  - Path: /home/genesis/.local/bin/codex → codex-cli 0.141.0
  - **KOMBI 2026-06-21 live:** `codex exec --skip-git-repo-check --output-last-message` → exact "HARNESS-OK-CODEX-42". Full CodexCLI implemented + tested.
  - Routed via make_llm + "codex" family in cross_model.

- **grok**:
  - Confirmed /home/genesis/.local/bin/grok , live probe returned exact token.

- **Project's own harness adapters**:
  - Explicit: llm/{grok,claude,codex}_cli.py + factory.py (family-routed make_llm) + cross_model.
  - **KOMBI complete:** All 3 LLM harnesses live-probed + unit tests extended (CodexCLI + codex family). Antigravity = visual GUI (Electron).
  - Tests now cover codex (skipif honest).  compile + isolated + live verified.

**Conclusion:** Harnesses fully operational and ready. Head (grok) routes grok-internal (planning/vibe/review), claude/codex for delegated slices, antigravity visual. Kombi + D16 G3 done — immediate continuation possible.

**Scheduler update (2026-06-21):** Loops shortened to every 10 minutes per user directive (old 30m tasks cancelled, new 10m recurring active).

## 2. Current State (Evidence-Based Summary)
- **CAD TEIL 2 (Stein 1-6)**: KOMPLETT. CNC/Laser/PCB DFM sourced+real rules (dfm.py, manufacturing_check.py), cost_model, gcode (2.5D verified), kicad netlist/schematic. Stein verified by grok + claude review. qa_hints added. BUILD_LOG + logs confirm.
  - Follow-ups noted: electronics.py (bugs in export_placement + run_internal_drc magic nums), FDM hole_hint fake.
- **HORIZON φ–Ω**: first-stone / guarded skeleton (per docs/HORIZON.md §4 table 2026-06-21): φ/χ = ✓ bewiesen (gate_phi/chi + forge + tests); δ⁺/γ⁺/ε/ζ/Ω = first-stone (skeleton) — wires/gates live (reality/coverage/inverse/seams/memory/omega/conductor/lumen etc) but demo values, thin reviewed, no rich real-E2E ingest. φ/χ/ε/ζ/Ω + cert pop + dream_to_hammer_gate 4L proofed. See Return Gate 2026-06-21 Verdict in verification/CodeKnowledge.md:67 ("FAIL for full claims. First-stone / guarded skeleton... Skeletons remain vs '✓ bewiesen'"), HORIZON.md:113-117, BUILD_LOG, verification-log (exact severity cites). Later phases code present. LUMEN attach + Ω advanced.
- **Review Campaign**: Deep Claude×Grok 4-Linsen + eval-gated. 
  - DONE: core/*, verification/* (gates fixes), ledger, llm, tools, agents (full), pipeline.py + Quality-Engine (11/11, 8 fixed), D15 (geometry wired), D16 (goldset exact token), LUMEN cert attach + dream_to_hammer_gate + exposure, HORIZON ε/ζ/Ω + buckling/fem validator review.
  - Open: Step 7 physics individual validators full depth (fem3d, modal, circuit, structural, brep, mesh_integrity, orientation etc.), pipelines full seam (export/costing/completeness/software), CAD follow-ups, low D11/D12/D13 + owner D1-D10.
- **Deferred D's** (from WORK_QUEUE + reviews):
  - D14 (pipeline printability/physics order — some unreachable per analysis).
  - D15 (grounding + **geometry_verification.py NOT wired in main pipeline** despite README §6 claims + phases; exists, solid cross-checks brep vs analytic, tested, but seam gap).
  - D16 (goldset/telemetry/calibration/rat tails).
  - D11 (audit logs for extra judges), D12 (inter-judge dedup), D13 (synthesizer/forge approach id + caps).
  - Owner/arch: D1-10 (colony modules, timestamps, protocols, SSRF/XXE hardening, etc.).
- **LUMENCRUCIBLE**: Module exists (grenzverschiebung/lumencrucible.py). process_dream + self_improve + WORK_QUEUE appends + dedup fix done. Suggestions for Ω v1: expose process_dream as HORIZON entry, new `dream_to_hammer_gate`.
- **Docs/Code**: DOC_CODE_DRIFT.md tracks over/under-claims (many corrected; some stale like old test counts). WORK_QUEUE updated per session. README mentions 1185 tests etc. need sync.
- **Pipelines**: First stones (architekt, designer, fertigungs, integrator, physiker etc.) + seams to CAD/verif/ledger. assess_printability uses some but not geometry_verif.
- **Tests**: 1200+ passed /9 skipped (honest for optionals like build123d/numpy in this env). Ruff clean often. Full E2E live owner-gated.

**Philosophy match**: Extremely high — Gates, Ledger, Cross-Model (skeptic), 4 Linsen (explicit in project + our overlay), honest gaps/abstention, determinism. Perfect for Hermes Head.

## 3. What Still Needs to be Done (Prioritized)
### High (Close Review Campaign + Core Seams)
1. **Physics Validation Layer (Step 7)**: Core gate/select + buckling/fem reviewed (4L + doc). Remaining individual validators full depth (fem3d, modal, circuit, structural, brep, mesh_integrity, orientation, dfm etc.). Ensure non-vacuous, proper gaps, integration.
2. **Pipelines + Integration full seam review (Step 8-9)**: Export, costing, completeness, software + grenz/LUMEN seams. Cert pop + LUMEN multi-domain advanced.
3. **HORIZON later phases proof (head 4-Linsen)**: δ⁺/γ⁺ deeper + full vs docs (ε/ζ/Ω + E2E certs + dream_to_hammer recently proofed).
4. **CAD electronics follow-ups**: electronics drc magic, hole_hint, kicad polish.
5. **Low D's + owner**: D11/D12/D13 (audit/dedup), D1-D10 (owner/arch). D14/D15/D16 tails mostly closed.
6. **LUMEN conductor/inventor exposure**: process_dream as first-class HORIZON entry (gate done).

### Medium / Follow-ups
- CAD electronics follow-ups (electronics.py bugs: rot_deg, legacy (module), magic numbers in drc, use kicad.py patterns + verifier).
- FDM hole_hint fake fix.
- Audit/Dedup improvements (D11/D12).
- More robust error paths, better gap messages (e.g. consistent qa_hints).
- External seams (KiCad full graphic, FreeCAD) — keep honest as "external" per design.

### Low / Owner / Long-term
- D1-D10 owner-level (big refactors like ColonyModules out, timestamp determinism, SSRF deep, XXE).
- Live robustness (Ollama extraction bottleneck per docs).
- Full E2E runs + goldset.
- Docs sync (README, BUILD_LOG, WORK_QUEUE, HORIZON, DOC_CODE_DRIFT continuous).
- Push / release (owner-gated).

## 4. Suggested Changes / Improvements (Could / Should)
- **Consistent qa_hints + gap messages** across all ProcessDFM (Laser had drift; make uniform).
- **Wire geometry_verification** (D15) — adds real "built CAD == declared" seam. Conservative (after guards).
- **Dream-to-Hammer** first-class: makes LUMEN self-improvement visible in HORIZON φ/χ flow.
- **4-Linsen prompts** baked into project's claude/grok adapters (enhance harness integration).
- **Antigravity + visual** in CAD workflows (e.g. after prototype_cad_builder, open artifacts in antigravity for inspector).
- **Better telemetry for harnesses**: log which LLM family used in cross-model.
- **Determinism hardening**: wall-clock → run_id based where D2 impacts.
- **Non-vacuous everywhere**: ensure 0-check cases always surfaced explicitly (no_physics_indicated etc. already good).
- **Test more boundaries**: degenerate geometry, NaN guards, rotation AABB, empty BOM PCB.
- **Self-apply loop**: periodically run our own structured/vibe-verify on genesis code.

All changes must pass: project gates + our 4 Linsen + ruff + tests (honest skips) + Return Gate by head + updates to verification-log/CodeKnowledge/WORK_QUEUE.

## 5. Execution Strategy (Hermes Head Rules — Non-Negotiable)
1. **Head owns brain**: grok-internal for research, architecture, all final verification, Code Knowledge, 4 Linsen, DoD.
2. **Delegate surgically**:
   - claude-code / codex: precise handoff.md (exact files, scope, output required, "head will verify").
   - antigravity: instructions for visual/CAD work, then head inspects outputs.
3. **Always Return Gate** (after any work or delegation):
   - Head reads primary files.
   - Grep wiring (imports/calls/state/config/ledgers).
   - Execute relevant (pytest slice, python -c, scripts).
   - 4 Linsen explicit.
   - Update verification-log.md + CodeKnowledge.md + WORK_QUEUE.
   - Prove "it runs + wired + understood".
4. **Track**: todo_write every phase. Small continuous doc updates.
5. **Loop until done**: High items closed. Scheduler ensures persistence.
6. **Alignment**: Project 4_LINSEN_PRINZIP + CLAUDE.md + our VibeCoder templates + WORKFLOW.

**No blind trust. Evidence only.**

## 6. Durable Permanent Loop
- Existing: scheduler id 019ee93f03cf "every 30 minutes" — "Continue autonomous Hermes loop on GENESIS..."
- Will create/renew stronger one with full instruction (see actions).
- Prompt will include: head role, 4 Linsen, read WORK_QUEUE/verification/* first, pick next high, delegate if strategic + handoff, Return Gate mandatory, update all logs, close items, repeat.
- Can run multiple overlapping if needed. FireImmediately true for kick.

## 7. Prioritized Next 10 Micro-Tasks (Start Here)
1. Produce this plan + update verification-log + CodeKnowledge (head).
2. 4-Linsen grok-internal review of physics_validation.py + 1-2 validators (fem/thermal).
3. D15 analysis: read all call sites + propose wiring patch (or explicit defer doc).
4. Review one HORIZON later (e.g. reality.py + gate_delta_plus).
5. LUMEN: implement dream_to_hammer_gate stub + wire.
6. CAD follow-up: audit electronics.py (list bugs, minimal safe fix or defer).
7. Pipeline seam: confirm geometry/grounding in assess_* paths.
8. Delegate small review slice to claude (e.g. a validator) with handoff.
9. Run ruff + targeted tests; fix any new.
10. Scheduler renewal + log "loop permanent active".

Success: All high + D14-16 closed or explicitly owner-deferred with evidence. Full traceability. Project "complete" for next phase (owner push/live).

**Head commitment:** I (Grok) will drive until high items resolved. Continuous autonomous progress via loop. User can "x" to pause.

**WICHTIG — Grok Workflow Disziplin (User-Reminder 2026-06-21):**
Der **volle Structured Loop** aus `/home/genesis/grok-laptop/WORKFLOW.md` wird **immer** auch in allen Hermes-Head Operationen angewendet:
1. Intake + Clarify (mit todo_write)
2. Research (thorough-researcher / Evidenz)
3. Plan (loop-planner)
4. Implement (careful-implementer)
5. Vibe-Verify + Execution (Code Knowledge, Wiring Checklist, Tests, Execution)
6. Review (strict-reviewer)
7. Close + Log

**User Directive 2026-06-21 (Elaboration Focus):** Viele Module/Gates sind nur erstellt (Skeletons/First Stones), nicht komplett ausgearbeitet. Diese müssen nachgearbeitet werden. Memory (CodeKnowledge, verification-log, WORK_QUEUE, etc.) **maximal präzise** halten: exakt dokumentieren was gemacht, verändert, was fehlt. Siehe detailed "Elaboration Status Audit" in verification-log.md + CodeKnowledge.md (2026-06-21 entry).

Dies gilt auch bei Delegationen an claude/codex/antigravity — der Head führt danach immer den vollen Verification-Zyklus inkl. DoD, Wiring Proofs und Code Knowledge durch. Keine Ausnahmen.

Next action: Start next slice using full Grok Workflow (e.g. next physics validator or electronics or HORIZON code).

## Head Return Gate Sync Update (2026-06-21, post re-verify for cert pop + HORIZON + physics close)
**Sync current (from full self research + synthesis in verif-log):**
- HORIZON φ–Ω: skeleton + LUMEN small E2E cert attach (ε/ζ via seam/memory to RunState) + omega elab + dream_to_hammer done/exposed. All "✓" in HORIZON.md at first-stone level. Full rich pop/E2E from claims/N-Judge + reality δ+ E2E: missing per audit.
- Cert pop: pipeline.py:132-152 skeleton + Assessment; lumencrucible.py:317-365 attach + return; state:1325-1326 slots; omega:395-409 validate; bundle/web consumers; integrator mention-only honest sep. Grep: 131/18 src, 75/7 tests. evaluate_reality/gate_delta_plus: low calls (0 prod).
- Physics close (Step7): 42 RECIPES ~40 validators L3 seam full (contact fix, pipeline wiring, 4L on fem/thermal etc); exec proofs. But not closed (hermes-plan #1 remaining depth; WQ Step7-9 open; no E2E reality ingest).
- 4L on state: L1 truth (cites exact), L2 no drift, L3 seams good internal/partial vs docs, L4 realizable (skeleton).
- Honest missing: full E2E δ+γ+εζΩ one-run from real claims; reviewed_failure_modes flow; rich seams; full physics validators.
- Exec/grep proof: pycache all key; specific lines as in verif-log Return Gate.
- Updates to this plan: Prioritized #1-3 now emphasize "complete Step7 depth + E2E cert/reality pop + HORIZON elaboration debt (see verif-log Return Gate)". High items: cert pop partial advanced, physics advanced not closed.

**Precise bullet for logs:** High prio: "Memory sync + Return Gate cert pop/HORIZON/physics close re-verify done. LUMEN attach + skeleton good; evaluate_reality low; Step7 partial close. Update frontier/queue. See verif-log new section."

All per strict evidence. Loop continues. Head owns close gate.

[End of appended section; prior content preserved.]