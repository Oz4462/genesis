# GENESIS Module Contract (per GENESIS_PLATFORM_BUILD_TODO §A1)

**Purpose:** Every core Genesis module MUST follow this contract to prevent "just an LLM call" drift. Core = typed data + local knowledge/tools + deterministic builders/runners/gates + evidence + human ratification.

## Required Shape (every module)

- **Input**: Typed dataclass (e.g. `Dream`, `Specification`, `InventionBrief`).
- **Knowledge**: Local (wissensbasis, formulas, seeded recipes, dfm rules, physics validators) or injected (no hidden LLM facts).
- **Builder**: Deterministic or LLM-proposer + gate (e.g. `prototype_cad_builder`, `generate_concepts`).
- **Runner**: Execution (simulation, CAD export, experiment, `evaluate_reality`).
- **Gate**: Pure deterministic predicate (e.g. `gate_delta`, `gate_gamma_plus`, `verify_gcode`). Never LLM inside gate.
- **Failure Modes**: Explicit enum/list of why it can fail (with evidence).
- **Evidence**: `SourceRef`, `Ledger` claims, `Receipts`, provenance always required for facts.
- **Human Decision**: Ratification point (never auto-approve critical).

## Examples

### technology_builder / experiment_designer
- Input: `CapabilityGap` + `DevelopmentFrontMap`
- Builder: Proposer (LLM) + `safety_ladder`
- Runner: Teststand or sim
- Gate: `gate_experiment` (measurable prediction + falsifiability)
- Evidence: Plan + Receipt

### development_front_mapper
- Input: `Dream` + sources
- Knowledge: wissensbasis + arxiv/tools
- Builder: scout/scholar/skeptic
- Gate: `gate_chi` (coverage + novelty)
- Evidence: `FrontierMap` with `Quelle` + receipts

## Invariants (enforced by code review + tests)

1. No factual claim without `SourceRef` + Ledger entry.
2. Gate is pure (no side effects, deterministic, testable without LLM).
3. "I don't know" / abstention is first-class and measured (not punished).
4. All outputs carry `quelle`, `gaps`, `failure_modes`.
5. External tools (KiCad, OpenFOAM, etc.) behind adapters + loud failure on missing.

## Enforcement

- New module PR must include:
  - Contract implementation docstring
  - Gate unit tests (including failure modes)
  - Integration test through pipeline or grenz/lumencrucible
  - 4-Linsen self-review in BUILD_LOG

This contract makes the "Erfindungsmaschine mit Wahrheitszwang" real, not aspirational.

(Initial 2026-06-24 autonomous fill per PLAN; expand with more examples as modules mature.)