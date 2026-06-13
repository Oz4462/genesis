# Integrations-Katalog — GENESIS × "alle apps"

> Stand: 2026-06-13 · Read-only verifiziert gegen `C:\Users\Ozan\Desktop\alle apps\`
> und gegen GENESIS-Quelle `src/gen/`. Reife-/Testzahlen aus Repo-Inspektion.
> Verdikt-Tiers und Mehrwert-Beweis siehe `PROOF_OF_VALUE.md`.

## Zweck

Ozan besitzt 10 Projekte in `alle apps/`. Mehrere haben **dieselben
Verifikations-Primitive unabhängig nachgebaut**, die GENESIS braucht — und GENESIS
hat einige selbst dupliziert. Dieser Katalog hält fest, was jede App konkret
beiträgt, mit exakten Modul-Pfaden, damit Integration als **Adapter hinter den
bestehenden `Protocol`-Interfaces** (`src/gen/core/interfaces.py`) erfolgen kann —
kein Framework-Lock-in, Determinismus + Fakten-Ledger-Prinzipien bleiben gewahrt.

## GENESIS-Andockpunkte (verifiziert)

`src/gen/core/interfaces.py` definiert als `Protocol`:
- `Tool` — Capability (search/fetch/compute), ehrliche Fehler statt Fabrikation.
- `Agent` — `run(state)->state`, faktische Aussagen MÜSSEN über den Ledger als `Claim`.
- `LedgerStore` — append-mostly, **kein Claim ohne Quelle** (+ DB-Constraint).
- `Gate` — deterministisches, LLM-freies Prädikat, strukturiertes `GateResult`.
- `SearchBackend` — Kandidaten-Quellen (web/arXiv/SemanticScholar).
- `LLMClient` (`src/gen/llm/base.py`) — ScriptedLLM (Test) / OllamaLLM (live).

GENESIS-Lücken (mit Beleg):
1. **Cross-Run-Persistenz fehlt** — `src/gen/ledger/store.py` ist per-Run in-memory.
2. **Research-Breite dünn** — `src/gen/tools/search.py` = SemanticScholar + generischer SERP.
3. **Verifikations-Math unvollständig** — `src/gen/calibration.py` hat Precision@Threshold +
   ECE; kein Drift/CRC/FDR (der eigene Docstring nennt das SOTA-Konsistenz-Signal als fehlend).
4. **Linearer Conductor** — `src/gen/agents/conductor.py`, keine Multi-Agent-Debatte.
5. **Keine Governance/Audit-Schicht** für Live-/regulierten Betrieb.

---

## TIER 1 — Fundament (höchster, sofortiger Mehrwert)

### trust-core  → **Dependency** (wie VERIDEX es bereits nutzt)
- **Pfad:** `alle apps\trust-core\` · Python ≥3.11, mypy-strict · ~726 Tests · 5 Kern-Deps
  (numpy, scipy, pynacl, cryptography, pydantic) · Dual-Lizenz Apache-2.0 OR MIT.
- **Reusable Module:**
  - `src/trust_core/conformal/split.py` — split-conformal Threshold (finite-sample).
  - `src/trust_core/conformal/crc.py` — Conformal Risk Control.
  - `src/trust_core/conformal/ccdd/*.py` — **Drift-Detection** (Anderson-Darling, Wasserstein,
    MMD, CUSUM, E-Value) — **fehlt GENESIS komplett**.
  - `src/trust_core/math/fdr.py` — Benjamini-Hochberg FDR-Gate.
  - `src/trust_core/math/bandit.py` — UCB1 / Thompson.
  - `src/trust_core/receipts/receipts.py` + `keystore.py` — Ed25519-DSSE-Receipts + Rotation.
  - `src/trust_core/honesty/auditor.py` — Claim-Pin-Auditor (README-Claim ⇄ Test/CI).
- **Genesis-Fit:** ersetzt/erweitert `src/gen/calibration.py`; liefert Drift-Gate (`Gate`),
  einheitliche Receipts, Meta-Honesty-Auditor. **Strikte Obermenge** der Genesis-Math.

### ANAMNESIS  → **Adapter** (`LedgerStore`++ / optionaler `SearchBackend`)
- **Pfad:** `alle apps\ANAMNESIS\anamnesis-py\` · Python ≥3.11 · ~367 Tests · SDK + FastAPI-Server.
- **Reusable Module:**
  - `src/anamnesis/distill.py` — Thinking-Tokens → atomare Reasoning-Schritte (LLM + Heuristik).
  - `src/anamnesis/storage.py` — `TraceStore`: SQLite + numpy-Embedding-Matrix, pluggbarer Embedder.
  - `src/anamnesis/retrieve.py` — `ConformalRetriever`: kNN-Cosine + conformal-Filter (Abstention).
  - `src/anamnesis/conformal.py` — Split-conformal-Kalibrierung der Reuse-Entscheidung.
  - `src/anamnesis/receipts.py` — Ed25519-DSSE-Receipts (EU-AI-Act Art. 15/50).
- **Genesis-Fit:** schließt **#1-Lücke** (Cross-Run-Memory): persistenter, conformal-bewerteter
  „verified-facts library"-Layer vor Live-Research; signierte Reuse-Lineage.

---

## TIER 2 — Verstärkung (nach Fundament)

### buch llm  → **Adapter** (`Agent`: Synthese-/Verifikations-Konsens)
- **Pfad:** `alle apps\buch llm\src\buch_llm\` · Python ≥3.11 · ~2697 Tests · v1.29, prod-stabil.
- **Reusable Module:**
  - `orchestrator/multi_agent_debate.py` — 7 Kritiker-Rollen + Thompson-gewichtete Aggregation
    (deterministischer Konsens, inkl. FactChecker-Rolle).
  - `manuscript/detectors/` — 28 Konsistenz-Detektoren (pure Funktionen / LLM-Judges) als
    Vorlage für „Claim muss Quelle zitieren", „Schluss ≠ Widerspruch zur Prämisse".
  - `gateway.py` — Rollen-Routing Ollama/Anthropic mit Cache/Retry/Schema-Repair/Circuit-Breaker.
  - `manuscript/receipts.py` — DSSE-Receipts pro Artefakt.
- **Genesis-Fit:** hebt den linearen `conductor`/`skeptic` auf Multi-Kritiker-Konsens für die
  Synthese-/Spec-Verifikation; Cross-Model-Regel bleibt (Generator ≠ Kritiker-Modell).

### VERIDEX  → **Adapter** (Governance / Audit / Drift-Monitoring)
- **Pfad:** `alle apps\VERIDEX\` · Python ≥3.11 · ~356 Tests · k8s/Helm · **nutzt trust-core**.
- **Reusable Module:**
  - `ccdd/` — Conformal Drift-Detection (chi2-F-Test + Bootstrap, formale FPR-Garantie).
  - `backend/app/api/events.py` — Art-12-Event-Logging (Metadaten, DSGVO-konform).
  - `backend/app/api/annex_iv.py` — Annex-IV-Generator (HTML/PDF, Evidenz-Fußnoten).
  - `backend/app/api/audit.py` — HMAC+Ed25519-signierte Audit-Bündel + Standalone-Verify.
  - `sdk/` — `@instrument`-Decorator (Ein-Zeilen-Instrumentierung).
- **Genesis-Fit:** manipulationssicherer, regulator-tauglicher Audit-Trail pro Lauf; Drift-Alarm
  bei Generator/Verifier-Modellwechsel; gleicher trust-core-Unterbau ⇒ konsistent.

---

## TIER 3 — Selektiv (eigene, später-gegatete Specs)

### ATLAS  → zusätzlicher `SearchBackend` + Verifikations-Bausteine
- **Pfad:** `alle apps\ATLAS\atlas\` · ~628 Tests · HUNTER live, Rest scaffolded.
- **Module:** `hunter/scrape_arxiv.py` (arXiv-Ingest-Template), `judge/cpcv.py`,
  `judge/walk_forward.py`, `judge/conformal.py` (Sharpe-Bounds — Muster für „finite-sample
  Confidence statt hand-wavy"), `mech/sae.py` (mechanistische Feature-Discovery).
- **Genesis-Fit:** breitere Research-Discovery (arXiv) + Verifikations-Muster für empirische Claims.

### PROMETHEUS  → Orchestrator-Muster + optionales Z3-Kausal-Gate
- **Pfad:** `alle apps\PROMETHEUS\prometheus\` · ~366 Tests · 100% math-/meta-Branch-Coverage.
- **Module:** `orchestrator.py` (Layer-Isolation per Disk-State + Locks + Idempotenz),
  `math/` (entropy/info_bottleneck/bayes+conformal/fdr/z3_circuits/bandit),
  `intervene/` (Z3-validierte Kausal-Ablationen), `report/`+`meta/` (Repro-Manifest, `reproduce.sh`).
- **Genesis-Fit:** härtet Determinismus/Reproduzierbarkeit; Z3-Gate für **kausale** Claims
  (stärker als Korrelation).

### AGORA  → nur bei realer Multi-Agent-Budget-Allokation
- **Pfad:** `alle apps\AGORA\py-prototype\` · 96 Tests · MCP-live.
- **Module:** `agora_core/mechanisms/` (Vickrey/VCG/Gale-Shapley/…), `agora_audit/envelope.py`
  (DSSE), `agora_settlement/`, `agora_mcp/`.
- **Genesis-Fit:** faire Compute-/Verifikations-Slot-Allokation, falls viele parallele Agenten.

### CHORUS  → optionaler Adversarial-Verifikator
- **Pfad:** `alle apps\CHORUS\` · 420 Tests · v0.2 (pre-seed).
- **Module:** `core/population/` (conformal-bounded Sampling), `agents/adversary`
  (zweite-LLM-Kritik), `core/calibration/`.
- **Genesis-Fit:** synthetische, statistisch geerdete Adversarial-Faktenprüfer als Zusatz-Skeptic.

---

## TIER 4 — Skalierungs-Option

### aletheia  → kompakter Index bei Massendaten (Rust)
- **Pfad:** `alle apps\aletheia\` · Rust, 0 Runtime-Deps · entropie-bewusste Roaring-Kompression.
- **Module:** `src/elias_fano.rs`, `src/container.rs`, `src/bits.rs` (rank/select/popcount).
- **Genesis-Fit:** dichte (source × topic × credibility)-Indizes bei Millionen Tupeln; **nicht MVP**.

---

## AUSSCHLUSS

### batch
- **Pfad:** `alle apps\batch\index.html` · 1 HTML-Datei, 0 Tests, kein Backend.
- Marketing-Landingpage (Group-Buy-Escrow). **Kein Research/Verifikations-Bezug — orthogonal.**

---

## Doppelarbeit-Matrix (warum Konsolidierung Mehrwert ist)

| Primitive | trust-core | ANAMNESIS | buch llm | VERIDEX | ATLAS | PROMETHEUS | AGORA | CHORUS | GENESIS heute |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Split-Conformal | ✓(kanon.) | ✓ | ✓ | ✓ | ✓ | ✓ | – | ✓ | ✓ (eigen) |
| CRC / Drift (CCDD) | ✓ | – | – | ✓ | – | – | – | – | **✗** |
| FDR / Bandit | ✓ | – | ✓ | – | ✓ | ✓ | ✓ | – | **✗** |
| Ed25519-DSSE-Receipt | ✓(kanon.) | ✓ | ✓ | ✓ | – | ✓ | ✓ | ✓ | **✗** |
| Honesty-Auditor | ✓ | – | ✓ | ✓ | – | – | – | – | **✗** |
| Multi-Agent-Debatte | – | – | ✓(kanon.) | – | – | – | – | ✓ | **✗** |
| Cross-Run-Memory | – | ✓(kanon.) | teilw. | – | DB | DB | – | ✓ | **✗** |

Lesart: GENESIS profitiert am meisten dort, wo es heute **✗** hat und ein gereiftes,
getestetes Modul existiert — exakt die Tier-1/2-Auswahl.
