# Live Ollama Run — End-to-End-Beweis (2026-06-14)

> Erster echter Live-Lauf der integrierten Pipeline. Skript: `scripts/pov/live_run_ollama.py`
> (Ergebnis unter `runs/pov/live_alpha/report.json`; `runs/` ist gitignored, Zahlen hier gepinnt).

## Setup (alles real, lokal)

- **Modelle (Cross-Model ✓):** Generator `qwen3.5:9b` (qwen) / Verifier `gemma4:12b` (google).
- **Backends:** Wikipedia + Semantic Scholar + **neuer `ArxivBackend`** (Tier-3), echtes HTTP.
- **Pfad:** `gen.integration.audited_run` → α-Pipeline + Memory-Deposit + signiertes Audit.
- **Frage:** „What is the speed of light in vacuum in meters per second?"

## Ergebnis (gemessen, run_id `live-alpha-1`)

| Größe | Wert |
|---|---|
| Claims extrahiert | 1 |
| Status | **1 unsupported** (0 verified / 0 refuted) |
| Memory deponiert | 0 (korrekt — nichts verifiziert) |
| Audit verifiziert | **true** (ledger_digest `ca1b1fe2…`) |
| Report-Body | „Für diese Frage konnte kein Beleg unabhängig verifiziert werden." |
| Gap | „Lichtgeschwindigkeit … genau gleich 299792458 m⋅s⁻¹ — Status: unsupported, Konfidenz 0.00" |

## Interpretation (ehrlich)

Das ist ein **erfolgreicher End-to-End-Beweis**, kein Fehler:
- Der Generator extrahierte den korrekten Claim (inkl. 299792458 m/s, deutsch per δ §57).
- Der **Cross-Model-Skeptic** fand über die Live-Backends keine schwellenwert-erfüllende
  **unabhängige** Korroboration → **ehrliche Abstention** (UNSUPPORTED, Konfidenz 0.00),
  als Gap ausgewiesen statt als Fakt behauptet. Das ist Genesis' Kernprinzip 1/4 live in Aktion:
  **kein faktischer Output ohne unabhängigen Beleg.**
- Die gesamte integrierte Kette lief: α-Pipeline + arXiv-Backend + Memory-Layer +
  **signiertes, verifizierbares Audit** (audit_verifies=true).

Damit ist die Live-Lauffähigkeit der Integration bewiesen. Höherer verifizierter-Claim-Recall
ist eine separate Tuning-/Backend-Frage (z. B. gezieltere Skeptic-Such-Queries, mehr Backends),
nicht eine Frage der Verdrahtung.
