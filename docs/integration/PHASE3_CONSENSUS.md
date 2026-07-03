# Phase 3 — Multi-Critic Verification Consensus (abgeschlossen 2026-06-13)

> Gerechtfertigt durch PoV-3 (PASS): N-Judge-Aggregation senkte leak-rate 0.593→0.173
> (−71%) ohne sound-recall-Verlust, deterministisch.

## Warum native Re-Implementierung statt buch-llm-Import

**Lizenz ist KEIN Blocker** — buch-llm ist Ozans eigenes Programm; es darf in Genesis
genutzt werden, wo es Mehrwert bringt (Owner-Klarstellung 2026-06-14). Die native
Re-Implementierung wurde aus einem **Engineering-Grund** gewählt: buch-llms
`multi_agent_debate` lebt in einem Paket, dessen `__init__` einen Authorship-HMAC prüft
und schwere Module (gateway/ollama/…) zieht; ein Import nur für ~30 Zeilen Aggregator-
Mathematik wäre unverhältnismäßig. PoV-3 hat die *generische* Konsens-Eigenschaft mit
buch-llms echtem Aggregator bewiesen; Phase 3 implementiert genau diese Eigenschaft
schlank auf Genesis' eigenem `Judgment`-Modell. (buch-llms reichere Bausteine — z. B. die
28 Konsistenz-Detektoren — können in Tier-3 direkt genutzt werden, wo sie Mehrwert bringen.)

## Was integriert wurde

- **`src/gen/verification/consensus.py`** — `consensus_verdict(generator_model, judgments,
  weights?, accept_threshold)` → `ConsensusVerdict`. Generalisiert `cross_model`'s
  2-Judge-Faltung auf **N unabhängige Cross-Model-Judges**:
  - Cross-Model erzwungen (jeder Judge ≠ Generator-Familie, sonst `ModelConflictError`).
  - **Veto:** jede credible REFUTED → Status REFUTED.
  - **Konservativ:** VERIFIED nur, wenn kein Refute UND gewichteter Support-Aggregat ≥
    Schwelle; sonst UNSUPPORTED („im Zweifel UNSUPPORTED"). Jeder Dissenter senkt den
    gewichteten Mittelwert — exakt der PoV-3-Leak-Reduktions-Effekt.
  - VERIFIED-Confidence per Noisy-OR-Korroboration (`corroborated_confidence` aus cross_model).
  - Pur, deterministisch (A5). Exportiert über `gen.verification`.

## Verifikation (Zahlen)

- `tests/test_consensus.py` 6/6: einstimmig→VERIFIED+Korroboration; Dissent→UNSUPPORTED;
  Refute→Veto; Cross-Model erzwungen; Gewichte/Validierung; Determinismus.
- **Volle Suite: 852 passed, 19 skipped, 0 Fehler.** ruff: All checks passed.

## Nicht erledigt / deferred

- Live-Verdrahtung: N reale Cross-Model-Verifier (verschiedene Ollama-Familien) erzeugen
  die `Judgment`s am live `skeptic`/`conductor` → End-to-End-Leak-Messung (owner-gated Pipeline).
- Bandit-gewichtete Critic-Gewichte (trust-core `math.bandit`) als optionale Verfeinerung.
