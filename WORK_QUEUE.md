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
- core/state.py — DONE (a1361b9): reviewed (Claude+Grok, 19 Findings), fixed (Measurement.unit-Guard + 2× doc-truth),
  eval grün 1121/9. Gros der Findings = intentionales Gate-Deferral (defended; permissive Konstruktoren für
  adversariale Gate-Tests). Erster echter End-to-End-CRAFT-Zyklus bewiesen.
- core/interfaces.py — DONE: reviewed (Claude+Grok), Quelle CLEAN (kein Bug). Protocol-Tightening-Findings → D4.
  Grok-„mojibake" war Artefakt meiner Dispatch-Pipeline (Get-Content ohne -Encoding UTF8, PS5.1) → Pipeline gefixt.
- core/errors.py — DONE: reviewed (Claude+Grok), fixed (E1 EvidenceIntegrityError + E2 UngroundedValueError
  message-accuracy), eval grün 1121/9. Ergonomie/Architektur-Findings → D5.
- core/__init__.py — DONE: leerer Package-Marker, trivial clean.
- >>> core/ PAKET KOMPLETT reviewt (interfaces clean · state fixed · errors fixed · __init__ clean) <<<
- gen/config.py — DONE: reviewed (Claude+Grok), fixed (#2 search_backends str-Koersion → fail-loud statt Zeichen-Tuple),
  eval grün 1121/9. Grok-Irrtum „Config nicht hashable" widerlegt (frozen ⇒ hashbar). Cross-Model-Frage → cross_model.py.
- verification/ — DONE (Claude-Workflow: 8 parallele Tiefenreviews + eval-gated Fixes):
  · gates.py: HIGH C-4 value_in_text vorzeichen-blind GEFIXT (64bf3c7) + non-vakuöser Regressionstest
  · derivation.py inf/nan-Scalar fail-loud + constraint_smt.py term() finite-Guard + ehrlicher unsat-core-Doc (502e964)
  · units.py Dead-Code-Cleanup + consensus.py REFUTED-confidence-Doc (83d5b5a)
  · cross_model.py / drift_monitor.py / trustcore_adapter.py / geometry.py: CLEAN (kein Fix)
  · Grok-Cross-Review: nachgeholt (war Klassifizierer-Outage). Suite 1134/9, ruff clean.
- ledger/ — DONE: store.py CLEAN (atomare add_claims/batch-before-mutate, Quellenzwang Layer 2, Determinismus,
  non-independence-View); postgres.py CLEAN (spiegelt InMemory + sql/001_ledger.sql, lazy asyncpg, 3-Layer-Trigger)
  — NICHT eval-bar (keine DB in der Sandbox → review-only, keine spekulativen Änderungen). Micro-Nits low → kein Fix.
- llm/ — DONE: base.py CLEAN (Protocol + frozen LLMResponse + deterministischer ScriptedLLM);
  ollama.py CLEAN (transport→LLMTransportError fail-loud, 2xx-Check, Envelope-Guard, temp0/num_ctx); parsing.py FIXED:
  structured-root-Enforcement (dict/list per Docstring-Kontrakt — Scalar wurde sonst von best-effort-Caller-Fallbacks
  als „honest emptiness" maskiert) + whitespace-empty-Klarheit; NEU test_parsing.py (19 adversariale Fälle, Boundary
  war ungetestet). Claude×Grok: Groks Scalar-Finding (high) korrobiert+gefixt; ollama SSRF/Redirect/DoS/empty-content
  REBUTTED für dieses File (base_url ist operator-Config, kein untrusted Input; Loopback-Allowlist bräche Remote-Ollama)
  → als Review-Ziele zu tools/fetch.py weitergetragen. Suite 1153/9, ruff clean.
- tools/ — NEXT (http.py, fetch.py [untrusted-URL SSRF/Redirect/Size-Limit aus Grok-llm-Review hierher], search.py, arxiv_backend.py)
- FEATURE DONE: Abo-OAuth LLM-Adapter — ClaudeCLI + GrokCLI (shellen `claude -p`/`grok -p`, keylos, Max-Abos),
  make_llm-Factory (family-routed) im cli.py-Live-Wiring, config-Default claude-opus-4-8 / grok-composer-2.5-fast.
  LIVE PONG-verifiziert (beide), 11 Offline-Tests, ruff clean, Suite 1132 grün, kein Import-Zyklus.

Deferred Findings-Backlog (owner-/Architektur-Ebene, aus core/state.py-Review, Claude×Grok-Einigkeit):
- D1: ModuleSpec/ColonyModule/NanoRecipe (Space-Colony/Nano-„2036-Leap"-Typen) aus dem Kern nach
  gen/domains|grenzverschiebung auslagern — breite Imports betroffen, eigener PLAN nötig.
- D2: _now()-Wall-Clock-Timestamps brechen bit-identische Checkpoint-Replays (Prinzip 5) — run-start-Timestamp
  injizieren (breiter Refactor über alle created_at-Felder).
- D3: RESOLVED — Quantity value/uncertainty isfinite-Guard. value: `math.isfinite` fail-loud im __post_init__;
  uncertainty: `not math.isfinite` vor dem `<0`-Test (inf/nan passierten beide `<0.0`=False). Schließt das
  non-finite-Wurzelthema, das beide Vendoren an 4 Gate-Eingängen (geometry/consensus/derivation/units) sahen.
  Eval-arbitriert: kein Gate-Test baut ein non-finite Quantity → kein gate-deferral. Suite 1134/9, ruff clean.
- D4: core/interfaces.py Protocol-Tightening (Claude+Grok): Tool typed Result statt object/**kwargs; Agent-Protocol-
  Member (input/output_schema, tools, failure_modes) vs Docstring angleichen; GateResult.failures tuple statt list
  (mit verification/gates.py zusammen); SearchBackend/LedgerStore typed failure surface. Architektur, owner-level.
- D5: core/errors.py Ergonomie (Claude+Grok): bare Errors (NoIndependentSourceError/RefineBudgetExceeded) Kontext-__init__;
  Intermediate-Base ProvenanceError/GenesisPolicyError (soft-vs-hard-Catchability); Konstruktor-Args auf self speichern;
  Rename RefineBudgetExceeded→…Error (Import-Blast). Ergonomie/Architektur, owner-level.
- D6: gen/config.py Hardening (Claude+Grok): Top-Level-Typo-Keys laut ablehnen; Range-Validierung (confidence∈[0,1],
  rounds≥0) — Achtung Gate-Test-Konstruktion; YAML-Schema = from_dict-Pfad teilen; Float-Repr-Repro. Blast-Radius.
- README-SYNC (Owner-Hinweis): README ist stale — viele Erweiterungen fehlen (HORIZON φ–Ω, research/ProofKernel,
  LUMENCRUCIBLE, App-Integration, Cloud-Model-Defaults, 1121 statt 881 Tests). Eigene README-Update-Aufgabe.
- OWNER-Q1 GELÖST: Abo-OAuth statt API-Key. ClaudeCLI + GrokCLI gebaut (CLI-Shell, keylos, Claude-Max + Grok-Max),
  live verifiziert. Lokaler Ollama-Pfad bleibt für reproduzierbare/deterministische Läufe (A5) erhalten.
- D7: verification/ deferred (Claude-Workflow-Findings, owner-/risk-level): gates.py eq-Constraint ignoriert GUM-Unsicherheit
  (Doc behauptet Gating) → eq-Toleranz um kombinierte Unsicherheit weiten ODER Doc einschränken; gates.py ERC duplicate-net
  meldet falschen Code 'DANGLING_PIN_REF' (eigener 'DUPLICATE_NET' nötig) + E-2 bei leerer BOM still übersprungen;
  geometry.py exact=True auf degenerierten Operanden (med) + 90°-float-Doc; consensus.py intra-panel Familien-Dedup
  + UNVERIFIED/NaN-loud; Doc-Nits (units leading-/ + min/max-Literal-Asymmetrie, drift_monitor scan-index, trustcore isinf).

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
