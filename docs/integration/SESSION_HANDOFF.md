# SESSION HANDOFF — GENESIS Integration + HORIZON (Stand 2026-06-14)

> Vollständiger Wiedereinstieg. Wo wir waren, was erledigt ist, was offen ist.
> Quelle der Wahrheit für den Code: der git-Branch unten + die Phasen-Docs in `docs/integration/`.

## Git-Stand (kritisch)
- Branch **`feat/app-integration-phase0-2`**, **16 Commits über `main`**, **ALLES LOKAL — KEIN PUSH** (Owner-Regel: Push erst auf expliziten Auftrag → `feedback_no_push_until_done`).
- Working tree enthält den aktuellen δ⁺ Deckungs-Beweis + γ⁺ Inverses Design + ε Nähte + ζ Bindegewebe + Ω Querfaden (noch nicht committet).
- Volle Test-Suite zuletzt: **950 passed, 19 skipped, 0 Fehler**; `ruff` sauber. Baseline-Start der Session war ~881.

## Commit-Kette (neueste zuerst)
```
2872d4d feat(chi)   Phase χ frontier map (gate-first, ultracode-reviewed)
a701ad8 feat(phi)   Phase φ model layer — Forge + run_divergence (ultracode-reviewed)
39cacee feat(phi)   Phase φ grounded divergence — first HORIZON stone (gate-first)
95adf65 fix(llm)    explicit num_ctx (defensive) + disprove num_ctx as live-extraction cause
4e2eef4 docs(live)  run #2 + live-web-variance finding
389c0a6 feat(integ) skeptic recall tuning + cross-run drift + memory recall prefilter
cda72d4 feat(live)  end-to-end Ollama run of the integrated stack
8959675 feat(verif) SMT constraint feasibility (Tier-3) + Tier-3 close-out
cb3d38a feat(tools) arXiv discovery backend (Tier-3)
593b6d5 feat(integ) live-wire consensus into skeptic + audited_run (Phase L)
6f9a2b7 feat(audit)  signed tamper-evident run audit (Phase 4)
b3a33c6 feat(verif)  native N-judge consensus (Phase 3)
9bdacb3 feat(integ)  trust-core + ANAMNESIS memory + proof-of-value (Phases 0-2)
```

## Was erledigt ist (jedes hinter Tests/Gate)
**App-Integration (aus `C:\Users\Ozan\Desktop\alle apps\`):**
- **trust-core** = echte Dependency (`verify`-Extra): `gen.verification.trustcore_adapter` (split-conformal single-source + FDR), `gen.verification.drift_monitor` (CCDD). PoV-1 bewiesen.
- **ANAMNESIS** = **vendored** (`gen/memory/_vendor/anamnesis_mem/`, nur numpy/stdlib — hält anthropic/openai aus Genesis): `gen.memory.VerifiedFactsLibrary` (Cross-Run-Memory). PoV-2 PASS (echter Ollama-Embedder, 0 false reuse).
- **buch-llm-Konsens** = **nativ** reimplementiert (Lizenz egal, aber Engineering): `gen.verification.consensus.consensus_verdict` (N-Judge). PoV-3 −71% leak.
- **VERIDEX-Governance** = **nativ** auf trust-core: `gen.audit.run_audit` (signiertes, tamper-sicheres Audit). PoV-4 PASS.
- **Tier-3:** `gen.tools.arxiv_backend.ArxivBackend` (live an echter arXiv-API bewiesen) + `gen.verification.constraint_smt` (z3-Feasibility, schließt transitive-Infeasibility-Lücke).
- **Live-Wiring (Phase L):** consensus→skeptic (`extra_judges`), `gen.integration.audited_run` (Memory-Deposit + Audit), `gen.integration.detect_run_drift`, Recall-Vorfilter (provenance-erhaltend), Skeptic model-driven Verifikations-Queries.
- **Live-Ollama-Run** end-to-end bewiesen (qwen3.5:9b/gemma4:12b): Audit verifiziert, Anti-Halluzination greift live (ehrliche Abstention).

**HORIZON (neuer Bogen, `docs/HORIZON.md`):**
- **Phase φ (Funke):** Gate (`gate_phi`) + Datenmodell (`Spark/Possibility/Divergence`) + **Modellschicht** (`agents/forge.Forge` + `runner.run_divergence`). Gate-first, adversarial-reviewed.
- **Phase χ (Frontkarte):** `gate_chi` + Datenmodell (`KnownRegion/FrontierEdge/FrontierMap`) + deterministischer Builder (`gen.frontier.build_frontier_map`). Gate-first, adversarial-reviewed.
- **δ⁺ Deckungs-Beweis:** Datenmodell (`FailureMode`/`CoverageCertificate`) + deterministischer Builder (`gen.coverage.build_coverage_certificate`) + Gate (`gate_delta_plus_coverage`). Deckt `physics_selection`-Failure-Modes, SMT-Constraint-Feasibility und consensus-akzeptierte N-Judge-Kandidaten als `reviewed_failure_modes`; untestbare Modi bleiben explizite Restlücken.
- **γ⁺ Inverses Design:** Datenmodell (`InverseDesignGoal`/`DesignCandidate`/`ParetoFront`) + deterministischer Builder (`gen.inverse_design.build_pareto_front`) + Gate (`gate_gamma_plus`). Kandidaten müssen GATE γ bestehen, δ-Physics als Fitness-Orakel `physics_verified` liefern, Zielwerte werden aus Spec-Quantities recomputed, Front muss nondominiert und vollständig über den evaluierten Pool sein.
- **ε Nähte:** Datenmodell (`DomainSeam`/`SeamCertificate`) + deterministischer Builder (`gen.seams.build_seam_certificate`) + Gate (`gate_epsilon`). Koppelt mechanisch↔thermisch↔elektrisch↔Firmware per unit-geprüften Seam-Relationen und Kosten via `bom_cost`-Rollup; fehlende erforderliche Domain-Paare und falsche Nahtwerte blockieren.
- **ζ Bindegewebe:** Datenmodell (`MemoryDeposit`/`MemoryRecallLink`/`MemoryFabricCertificate`) + deterministischer Builder (`gen.memory_fabric.build_memory_fabric_certificate`) + Gate (`gate_zeta`). Deposits nur VERIFIED Claims mit Quellen; Recall nur mit τ, score≤τ, calibration-ready und Memory-Health OK; Drift-Alert blockiert.
- **Ω Querfaden:** Completion-Packet (`GateReceipt`/`LearningNote`/`OmegaCertificate`) + deterministischer Builder (`gen.omega.build_omega_certificate`) + Gate (`gate_omega`). Jeder Phasenabschluss braucht Gate-Receipt, failed Receipts blockieren, Gaps/Decisions/Frontier-Edges werden als Lernnotizen sichtbar, Spec-Blocking-Items bleiben unter explizitem `SignOff`.

**Pro-Phase-Doku:** `docs/integration/PHASE{1_TRUSTCORE,2_ANAMNESIS,3_CONSENSUS,4_AUDIT,_L_LIVE_WIRING,_L2_RECALL_DRIFT,_T3_ARXIV,_T3_SMT}.md`, `LIVE_RUN.md`, `EXTRACTION_BOTTLENECK.md`, `CATALOG.md`, `PROOF_OF_VALUE.md`. PoV-Berichte unter `runs/pov/` (gitignored).

## Offen / als Nächstes
- HORIZON-Sequenz ist gate-first erledigt; nächster Owner-Auftrag: Review/Commit/Push oder nächste Phase.

✓ **δ⁺ Realitäts-Beweis ERLEDIGT** (`reality.evaluate_reality` + `gate_delta_plus`, dimension-safe, adversarial-reviewed).
✓ **δ⁺ Deckungs-Beweis ERLEDIGT** (`coverage.build_coverage_certificate` + `gate_delta_plus_coverage`, selector-/SMT-/N-Judge-input-basiert, lokal getestet).
✓ **γ⁺ Inverses Design ERLEDIGT** (`inverse_design.build_pareto_front` + `gate_gamma_plus`, lokal getestet).
✓ **ε Nähte ERLEDIGT** (`seams.build_seam_certificate` + `gate_epsilon`, lokal getestet).
✓ **ζ Bindegewebe ERLEDIGT** (`memory_fabric.build_memory_fabric_certificate` + `gate_zeta`, lokal getestet).
✓ **Ω Querfaden ERLEDIGT** (`omega.build_omega_certificate` + `gate_omega`, lokal getestet).

## Bekannter Flaschenhals (belegt, nicht Verdrahtung)
Live verifizierter-Claim-Recall ist variabel — Ursache ist die **Extraktions-Robustheit** des 9B-Generators auf langen/verrauschten Quellen (num_ctx als Ursache WIDERLEGT, `EXTRACTION_BOTTLENECK.md`). Nächster Hebel dort: größeres Extraktionsmodell → Prompt-Härtung → Fine-Tune (3B QLoRA, GTX 1080 Ti Pascal). NICHT mehr Verdrahtung.

## Arbeitsweise (Owner-Regeln, aktiv)
- **Nach jeder großen Aufgabe: voller Bericht, dann auf „go" warten** (`feedback_report_then_go`).
- Ultracode-Modus an (xhigh + Workflow-Orchestrierung): pro großem Bau eine Map-Workflow + adversariale Review-Workflow vor Commit.
- Lokal committen ok; **Push erst auf Auftrag**.
- Ollama ist aktuell **gestoppt** (GPU frei); Genesis ist owner-gated für Live-Läufe.

## Schneller Verifikations-Befehl
```
$env:PYTHONPATH="C:\Users\Ozan\Desktop\Genesis\genesis\genesis\src"; cd "C:\Users\Ozan\Desktop\Genesis\genesis\genesis"; py -3 -m pytest -q
```
