# WORK QUEUE — GENESIS

> Voller Kontext: `docs/integration/SESSION_HANDOFF.md`. Branch `feat/app-integration-phase0-2`
> (16 ahead of main, lokal, KEIN Push). Suite: 1121 passed / 9 skipped. Ollama gestoppt.

## Active — DEEP REVIEW CAMPAIGN (Claude+Grok · sorgfältig · eval-gated · kein Push)
Tiefendurchlauf jedes Moduls Zeile für Zeile, **immer mit Grok** (research → 1 Rebuttal → der Eval
entscheidet, PROTOCOL #6), **4-Linsen pro Modul** (L1 Wahrheit · L2 Drift · L3 Naht · L4 Realisierbarkeit),
**Commit pro Modul** (kein Push). Sorgfältig, nicht max-Tempo. Rückgrat zuerst → dann alles (162 Module).

Reihenfolge (Rückgrat → alles):
1. core/ (state ← AKTIV, interfaces, errors, config)
2. verification/ (gates, cross_model, derivation, units, geometry)
3. ledger/ (store, postgres)  ·  4. llm/ + tools/
5. agents/ (scout, scholar, skeptic, conductor, synthesizer, architect)
6. pipeline.py + Quality-Engine (evaluation, refinement, clarification, ratification, calibration,
   telemetry, grounding/constraint/geometry-integrity, goldset)
7. physics_validation + 27 Validatoren + fem*/modal/dfm/orientation/mesh_integrity/brep/circuit
8. export/ + costing + completeness + software  ·  9. pipelines/ + integration/ + grenzverschiebung/
   + research + memory + web/
Status-Ledger (pro Modul nachführen): [reviewed | fixed <commit> | clean].
- core/state.py — DONE: reviewed (Claude+Grok, 19 Grok-Findings), fixed (Measurement.unit-Guard + 2× doc-truth),
  eval grün 1121/9. Gros der Findings = intentionales Gate-Deferral (defended; permissive Konstruktoren für
  adversariale Gate-Tests). Erster echter End-to-End-CRAFT-Zyklus bewiesen.
- core/interfaces.py — NEXT

Deferred Findings-Backlog (owner-/Architektur-Ebene, aus core/state.py-Review, Claude×Grok-Einigkeit):
- D1: ModuleSpec/ColonyModule/NanoRecipe (Space-Colony/Nano-„2036-Leap"-Typen) aus dem Kern nach
  gen/domains|grenzverschiebung auslagern — breite Imports betroffen, eigener PLAN nötig.
- D2: _now()-Wall-Clock-Timestamps brechen bit-identische Checkpoint-Replays (Prinzip 5) — run-start-Timestamp
  injizieren (breiter Refactor über alle created_at-Felder).
- D3: Quantity value/uncertainty isfinite-Guard — vor Fix prüfen, ob ein DERIVED-Pfad legitim inf erzeugt.

## Next
- (Kampagne läuft; nach core/ → verification/ usw. gemäß Reihenfolge oben)

## Owner-gated / blockiert
- Branch mergen/pushen (braucht Owner-Auftrag).
- Live-Ollama-Läufe (Genesis owner-gated) + Extraktions-Robustheit (größeres Modell/Fine-Tune) —
  der belegte Live-Recall-Hebel, siehe `docs/integration/EXTRACTION_BOTTLENECK.md`.

## Done (diese Session)
- App-Integration: trust-core (dep) · ANAMNESIS-Memory (vendored) · N-Judge-Consensus (nativ) ·
  signiertes Audit (nativ) · arXiv-Backend · SMT-Feasibility · Live-Wiring · Live-Ollama-Run.
- HORIZON: Phase φ (Gate + Modellschicht) · Phase χ (Gate + Builder) · δ⁺ Realitäts-Beweis
  (`reality.evaluate_reality` + `gate_delta_plus` + Falsifikations-Experiment/Measurement) ·
  δ⁺ Deckungs-Beweis (`coverage.build_coverage_certificate` + `gate_delta_plus_coverage`,
  inkl. `reviewed_failure_modes` für N-Judge-Kandidaten) · γ⁺ Inverses Design
  (`inverse_design.build_pareto_front` + `gate_gamma_plus`) · ε Nähte
  (`seams.build_seam_certificate` + `gate_epsilon`) · ζ Bindegewebe
  (`memory_fabric.build_memory_fabric_certificate` + `gate_zeta`) · Ω Querfaden
  (`omega.build_omega_certificate` + `gate_omega`).
- Test-Honesty-Fix (2026-06-17): 4 build123d-gated CAD-Tests folgen jetzt dem README-§7-Honest-Skip-
  Vertrag (`importorskip`); build123d in `pyproject [cad]` deklariert. Suite grün statt 4 rot.
- LUMENCRUCIBLE Dedup/Isolation-Fix (2026-06-17): `_self_improve` ist idempotent (Append nur, wenn der
  Vorschlag noch nicht in der Queue steht) + konfigurierbarer `work_queue_path`; Tests isolieren den
  Append in `tmp_path`. Beendet die Flut identischer Queue-Zeilen + neuer Regressionstest.

## LUMENCRUCIBLE Self-Improvement Suggestions (2026-06-15)
- LUMENCRUCIBLE Ω v1: expose `process_dream` as first-class HORIZON entrypoint in conductor + new small `dream_to_hammer_gate` in verification/gates.py.
  Beispiele: Jetpack-Energie-Gap → EmberNest_Thrust_Rig_v0.1 (tethered, gate_delta_plus, reality-ready); Generic → FirstCrack_*-Rig.
  Evidence: lumencrucible.py + test_lumencrucible.py + reale WORK_QUEUE-Appends (Quelle: lumencrucible._self_improve + HORIZON.md §2A).
  Mehrere Runs (lumen-test-jet-001, lumen-test-gen-002, lumen-final-verify) haben den Mechanismus verifiziert.

> Konsolidiert 2026-06-17: ~150 historische LUMENCRUCIBLE-Duplikate (Test-Artefakte aus dem relativen
> Pfad, der in die echte WORK_QUEUE.md schrieb) entfernt; der Dedup/Isolation-Fix verhindert die
> Wiederkehr. Diese eine Zeile bleibt als Dedup-Seed stehen. Vollständige Historie bleibt im Git.
