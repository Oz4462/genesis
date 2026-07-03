# Phase 2 — ANAMNESIS Cross-Run-Memory (abgeschlossen 2026-06-13)

> Gerechtfertigt durch PoV-2 (PASS mit echtem Ollama-Embedder: 0 false reuse).
> Schließt GENESIS-Lücke #1: per-Run-Ledger → durable, conformal-bounded Reuse.

## Was integriert wurde

- **`src/gen/memory/verified_facts.py`** — `VerifiedFactsLibrary`: durable Cross-Run-Store
  zuvor VERIFIZIERTER Claims (nur `ClaimStatus.VERIFIED` wird deponiert), keyed by claim id;
  `remember(claims)`, `add_calibration(scores)`, `recall(query, alpha) -> RecallResult`.
  Reuse ist conformal-gated; **vor Kalibrierung wird abstrahiert** (kein Bound → kein Reuse).
  Plus `ollama_embedder()` (Produktions-Embedder, lokal, kein Cloud-Egress).
- **Additiv, kein Ersatz** des per-Run `LedgerStore`: Claims fließen weiter mit voller
  Provenance durch den Ledger; nur verifizierte landen zusätzlich in der Library.

## Vendoring statt Dependency (bewusst)

ANAMNESIS deklariert `anthropic` + `openai` als **harte Core-Deps**, und sein
`__init__` importiert sie transitiv. Das in GENESIS (local-first / anti-cloud-leak) zu
ziehen, wäre falsch. Die Memory-Primitive brauchen nur numpy+stdlib → **vendored** unter
`src/gen/memory/_vendor/anamnesis_mem/` (capture/conformal/storage/retrieve, nur
Intra-Imports auf relativ umgeschrieben, Logik unverändert). Begründung + Update-Prozedur:
`src/gen/memory/_vendor/WHY.md`. Kontrast: trust-core (Phase 1) IST Dependency (leicht,
keine Cloud-SDKs, von VERIDEX genutzt) — anderer Trade-off, andere Wahl.

## Verifikation (Zahlen)

- Unit (offline, deterministisch, `tests/test_verified_facts.py`, 4/4): nur VERIFIED wird
  gespeichert; Abstention vor Kalibrierung; exakter Repeat korrekt recalled; Unverwandtes
  abstrahiert (0 false reuse).
- **Live-Smoke** (`scripts/pov/pov2b_vendored_live.py`, run_id `pov2b`, **PASS**): produktiver
  Pfad (vendored + echter Ollama-Embedder): **false_reuse 0/3 (harte Honesty-Gate)**,
  recall 3/5 (tuning-abhängig — Abstention ist der sichere Fehler-Modus).
- **Volle Suite: 846 passed, 19 skipped, 0 Fehler.** `ruff check` memory: All checks passed.

## Nicht erledigt / deferred

- Recall-Tuning (alpha/k/Kalibrierungsgröße) für höhere Recall-Rate bei kleinem N.
- Verdrahtung in scout/scholar als „Vorfilter vor Live-Research" + Live-Token-/Zeit-Messung
  (braucht den live α-Lauf — owner-gated Pipeline-Integration).
- Receipts der Reuse-Entscheidung über trust-core (Single-Source nach Phase 1).
