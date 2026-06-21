# Hermes Head — Routing Plan for GENESIS Project

**Date:** 2026-06-21  
**Session:** Initial activation (`/hermes-head und jetzt loslegen`)  
**Project Path:** /home/genesis/genesis  
**Head:** Grok (this system)

## Project Context (Intake Summary)

GENESIS = Generative Engine for Networked Ideation, Synthesis & Specification  
Core promise: Idea → verified, sourced, gate-checked specification / discovery / invention **without hallucination**.

**Current State (from WORK_QUEUE + SESSION_HANDOFF + docs):**
- Massive Python codebase (`src/gen/`, 1000+ tests mentioned in docs).
- Strong multi-agent system (agents: architect, conductor, skeptic, scout, scholar, synthesizer, forge...).
- Explicit support for Grok + Claude (llm/grok_cli.py, claude_cli.py, scripts/grok_review.sh, dedicated GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md and CLAUDE.md).
- Very similar philosophy to our Vibe-Coder/Hermes rules: Ledger + hard Gates, cross-model verification (skeptic), 4-Linsen (L1 Truth, L2 Drift, L3 Seam, L4 Realizability), honest abstention, determinism, "no push until clean".
- Active work: Deep Review Campaign (Claude + Grok, eval-gated, commit-per-module). Core largely complete. HORIZON phases (φ, χ, δ+, γ+, ε, ζ, Ω) and integration work in progress.
- Branch: feat/app-integration-phase0-2 (local only).

**Alignment with our system:** Extremely high. We will overlay our strict Hermes process (head verifies everything, full wiring proofs, Code Knowledge, DoD) on top of their existing gates.

## Available Harnesses (runtime detection 2026-06-21)

- **grok-internal**: available (this agent + structured-cycle + personas + vibe-verify)
- **claude-code**: available (`/home/genesis/.local/bin/claude`)
- **antigravity**: available (`/home/genesis/Downloads/Antigravity-x64/antigravity`)
- **codex**: available (`/home/genesis/.local/bin/codex`)
- **chatgpt**: manual web (if needed)

## Routing Strategy (why this routing)

**Core Principle (from Hermes skill):** Grok (head) never outsources understanding or final verification. Prefer grok-internal for architecture, verification, Code Knowledge, and DoD gate.

**Proposed Routing for GENESIS work:**

1. **Planning, Architecture Understanding, Verification, Code Knowledge, Final Quality** → **grok-internal** (always)
2. **Heavy coding / module implementation / refactors** → **claude-code** (with extremely tight handoff + precise scope)
3. **Visual / GUI / CAD / simulation inspection, interactive exploration** → **antigravity**
4. **Alternative reasoning / research angles** → **codex** or chatgpt (manual) when useful for diversity
5. **Discovery / research heavy slices inside GENESIS own engine** → mix of internal + targeted delegation

**Data Contracts & Scope Rules (non-negotiable):**
- Every handoff must define exact files/modules, input/output contracts, acceptance tests/Gates.
- All changes must pass project's own gates + our 4-Linsen + ruff clean + evidence in verification/.
- Head always does final read + grep (imports/calls/state/config/ledger) + execution + vibe-verify style proof.
- Documentation updated continuously (small updates).
- No "Claude did it" — head produces the understanding.

## First Slice Recommendation (for "loslegen")

Given the active DEEP REVIEW CAMPAIGN and HORIZON phases:

**Option A (recommended to start):**  
Internal (grok) Intake + full CodeKnowledge.md for the project + pick one high-value open frontier module from WORK_QUEUE (e.g. something in frontier/, seams/, or next in agents/pipelines) for a complete Hermes cycle (research → plan → verify existing + small improvement if needed → full evidence).

**Option B:**  
Delegate a clean review/fix slice to claude-code on one specific file (with handoff), head verifies.

**Option C:**  
Use antigravity for visual inspection of current web app or CAD output while head analyzes architecture.

## Next Steps (Head will execute)

1. Complete this intake + write Code Knowledge document (grok-internal).
2. Produce detailed first handoff or internal work plan.
3. Execute, Return Gate, update verification-log + DoD evidence.
4. Ask user for priority if needed.

All future work on this project will be tracked here or in project verification/.

**Head commitment:** I will personally read every artifact, prove wiring, run what is executable, and only close when "it runs + you can explain everything".
