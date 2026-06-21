# Phase L — Live-Verdrahtung in die Pipeline (2026-06-14)

> Verdrahtet die integrierten Module in den echten Lauf. Core bleibt numpy-only:
> Core-sichere Wiring geht direkt in die Agenten, Extra-abhängige über einen opt-in Layer.

## Verdrahtet

- **Consensus → skeptic (core-safe, `consensus.py` ist pure-core):**
  `Skeptic(..., extra_judges=[...])` + `Dependencies.extra_judges`. Mit ≥3 Judges
  (verifier + second + extras) entscheidet die konservative N-Judge-`consensus_verdict`
  (PoV-3) statt der 2-Judge-Faltung; Cross-Model je Judge erzwungen. Rückwärtskompatibel:
  ohne extra_judges unverändert. `src/gen/agents/skeptic.py`, `src/gen/runner.py`.
- **Audit + Memory-Deposit → opt-in Layer `gen.integration.audited_run`:**
  führt die Core-Pipeline aus, liest die Claims per run_id aus dem Ledger, **deponiert
  jeden VERIFIED-Claim** in die `VerifiedFactsLibrary` (Cross-Run-Reuse, Lücke #1 end-to-end)
  und **signiert** einen `RunAuditRecord`. Keine Core-Änderung; nur dieser Layer zieht die Extras.

## Verifikation (Zahlen)

- `tests/test_skeptic_consensus.py` 2/2: Panel-Support → VERIFIED; ein Judge widerspricht → REFUTED-Veto.
- `tests/test_integration_audited_run.py` 1/1: echter α-Lauf (scripted) → 1 VERIFIED deponiert
  → Audit verifiziert & round-trippt → Fakt nach Kalibrierung recallbar.
- Bestehende `test_skeptic.py` unverändert grün (backward-compatible).
- **Volle Suite: 859 passed, 19 skipped, 0 Fehler.** ruff: All checks passed.

## Noch offen (deferred, mit Grund)

- **Drift → Gate/Telemetry:** `DriftMonitor` braucht Output-Embeddings in `RunState` →
  RunState-Schema-Erweiterung nötig (owner-gated Core-Change). Bis dahin nur als Monitoring-
  Helper nutzbar.
- **Memory-Recall als Vorfilter in scout/scholar:** Deposit ist verdrahtet; das *Überspringen*
  von Live-Research bei einem Recall-Treffer ist Agenten-Surgery in scout → separat, owner-gated.
- **Live-Ollama-Endlauf** (echte Modelle, Token/Zeit-Δ): braucht das Heben des
  „kein Live-Run"-Gates für einen echten α/γ-Lauf.
