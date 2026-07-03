# MathBrain-Inventar fuer GENESIS (Sweep 2026-06-12)

## Was MathBrain ist (3 Saetze, aus den Funden)

MathBrain ist ein Mathematik-/Physik-Wissensvault mit rund 26k-28.9k embeddeten Notizen (`data/embeddings.npz`, 26k Notes × 1024d, snowflake-arctic-embed2), darunter 22.179 Paper-Notizen in 45 Unterordnern (`vault/Papers/`), 2.820 Personen-Notizen (`vault/Personen/`) und ein bi-temporaler Knowledge-Graph mit 8.155 Entities, 5.544 Relations, 34.501 typisierten Wikilink-Kanten und 593 Louvain-Communities (`data/kg.sqlite`). Darum liegt ein vollständiger Retrieval-Stack — Vektor-Index, BM25, Hybrid-RRF/MMR, RAG, Self-RAG, mehrere Graph-RAG-Varianten und ein MCP-Server mit 10 Tools (`code/src/mathbrain/mcp_server.py`), gespeist aus 35+ Quellen-Adaptern. Laut Formel-Gate-Befund ist das System auf **Retrieval/Indexing optimiert, nicht auf Validierung** (`code/src/mathbrain/processing/formula_gate.py`), steht seit 2026-05-29 unter Feature-Freeze (`vault/_meta/WORK_ORDER-00-master-now-2026-05-29.md`) und besitzt kein Fakten-Ledger (`code/src/mathbrain/kg/store.py`, `canonical.py`).

## Validator-Kandidaten

Tabelle: Kandidat | Quelle im Vault (Pfad) | welcher GENESIS-Check daraus wird | Aufwand

| Kandidat | Quelle im Vault (Pfad) | GENESIS-Check | Aufwand |
|---|---|---|---|
| Birthday-Bound Kollisions-Check | `vault/Formeln/crypto-birthday-bound.md` | Deterministisch aus Ausgabegröße & q: Pr≈q²/2^(n+1), reale Sicherheit 2^(n/2) | niedrig (closed-form) |
| CTR-Nonce-Eindeutigkeit | `vault/Formeln/crypto-ctr-mode.md` | (Key,Nonce)-Duplikat-Detektor, Keystream-Reuse-Flag | niedrig |
| ECDSA-Nonce-Uniqueness | `vault/Formeln/crypto-ecdsa-nonce-reuse.md` | Wiederholter Nonce → Privatschlüssel-Leak, kritischer Fehler | niedrig |
| X25519 Scalar-Clamping | `vault/Formeln/crypto-x25519-clamp.md` | Bytes auf k[0]&=0xF8, k[31]|=0x40 prüfen | niedrig |
| RSA-CRT-Fault-Detektor | `vault/Formeln/crypto-fault-rsa-crt.md` | Signatur vor Output verifizieren (S^e≡m mod N) | niedrig |
| GHASH/GCM-Nonce-Reuse | `vault/Formeln/crypto-ghash.md` | AES-GCM Nonce-Reuse + Subkey-H-Integrität | niedrig |
| Poly1305-r-Clamping | `vault/Formeln/crypto-poly1305.md` | r-Bit-Maske + One-Time-Einsatz prüfbar | niedrig |
| AEAD-Komposition-Audit | `vault/Formeln/crypto-aead-composition.md` | EtM vs MtE/E&M statisch erkennen | mittel |
| ML-KEM-Decaps-Check | `vault/Formeln/crypto-mlkem-encaps.md` | Rejection-Path (implizit/explizit), K-Derivation | mittel |
| ML-DSA-Bounds-Check | `vault/Formeln/crypto-mldsa-sign.md` | ‖z‖∞ < γ₁−β Ablehnung Out-of-Bounds | niedrig |
| Schnorr/MuSig2-Verifikator | `vault/Formeln/crypto-schnorr.md` | sG=R+eQ Batch + Nonce-Commitments | mittel |
| Fiat-Shamir-Malleability | `vault/Formeln/crypto-fiat-shamir.md` | erkennt fehlendes x-Hashing (c=H(x‖a)) | mittel |
| LLL-Sicherheitsmargin | `vault/Formeln/crypto-lll-reduction.md` | Gitter-Dimension/Hermite-Faktor gg. BKZ | hoch |
| Zeit-fraktionale PDE-Fehler-Bounds | `vault/Papers/arXiv/2605.26054.md` | closed-form h²+τ⁴ Konvergenz-/Energie-Stabilität → δ-Physik-Check | mittel |
| Asteroid-Stabilitäts-Screening | `vault/Papers/Zenodo/20183250.md` | Tisserand-Invariante T_J(t) + 7.96% Diskrepanz-Metrik | mittel |
| OEIS-Sequenz-Match | `vault/Papers/OEIS/A000005.md` | d(n)=Π(e(p)+1) gegen kuratierte OEIS-Daten | niedrig |
| DLMF-Spezialfunktion-Identität | `vault/Papers/DLMF/ch1.md` | Bessel-Nullstellen/Gamma-Rekurrenz gg. US-Public-Domain | mittel |
| Conformal-Coverage-Kern | `vault/Konzepte/60-conformal-foundations.md` | distribution-freie P(Y∈C(X))≥1−α als Basis-Validator | mittel |
| Mondrian Group-Coverage | `vault/Konzepte/61-conformal-mondrian.md` | per-Gruppe-Coverage (EU-AI-Act Art. 10) | mittel |
| CQR Regression-Intervall | `vault/Konzepte/63-conformal-cqr.md` | heteroskedastische Intervall-Vorhersage statt Skalar | mittel |
| Constraint-Konsistenz (bereits in GENESIS) | `vault/Konzepte/48-operations-research.md` | LP-Relaxation/robust optimization für Validator-Set | hoch |

## Kalibrierungs-/Qualitaets-Upgrades (conformal prediction, drift detection — konkret)

- **Conformal-Kern als neuer Kalibrierungs-Validator neben `src/gen/calibration.py`**: `vault/Konzepte/60-conformal-foundations.md` liefert die exchangeability-freie Coverage-Garantie; die bestehende GENESIS-`threshold_for_precision`/ECE-Logik (`src/gen/calibration.py`) bekommt damit ein Baseline-Verfahren mit finite-sample-Quantil-Bound.
- **Nonconformity-Baukasten**: `vault/Konzepte/70-nonconformity-scoring.md` definiert 6+ benannte Scores (Centroid/Mahalanobis, kNN, LOF, Model-Residual, Softmax-Margin, generative NLL) — modulare Validator-Komposition, je Score deckt einen Failure-Mode ab.
- **Online-Adaption statt Offline-Recalibration**: ACI (`vault/Konzepte/65-conformal-online-aci.md`, Update α_{t+1}=α_t+γ(α−1{Y∉C})) und Conformal-PID (`vault/Konzepte/66-conformal-pid-control.md`, P+I+D-Feedback gegen Saisonalität) brechen Austauschbarkeit bei Drift ohne Neutraining.
- **Drift-Monitoring mit garantiertem FWER**: Sliding-Window-Meta-Test (`vault/Konzepte/67-drift-sliding-window-fwer.md`, innerer Conformal-p-Wert + äußerer Binomial-Meta-Test, Bonferroni/BH) triggert Recalibration; Drift-Lokalisierung per Embedding-Clustering (`vault/Konzepte/68-drift-localization-clustering.md`, K-means/HDBSCAN + Mahalanobis) zeigt die betroffene Region.
- **Kovariate-Shift-Erhalt**: Weighted CP (`vault/Konzepte/64-conformal-weighted-shift.md`, w(x)=p_test/p_cal) hält Garantien unter bekanntem Shift; Jackknife+/Cross-Conformal (`vault/Konzepte/62-conformal-jackknife-plus.md`) als Drop-in bei kleiner Kalibrierungsmenge.
- **Fairness-Drift**: `vault/Konzepte/69-fairness-drift-metrics.md` (DP, Equalized-Odds, group-ECE, Wilson-Intervalle, per-Gruppe-Binomial+BH) kombiniert mit Mondrian-CP für regulatorische per-Gruppe-Coverage.
- **Bestehende GENESIS-Eval-Disziplin als Andockpunkt**: `src/gen/evaluation.py` (leak_rate=0 Non-Negotiable, false_alarm_rate messbar) und `goldset/v1.json` (25 Fälle: fact/trap/nonsense) sammeln (conf, is_true)-Paare; MathBrains Eval-Gate-Muster mit Bootstrap-CI + Regression-Detection (`vault/_meta/WORK_ORDER-eval-gate-2026-05-28.md`) und KG-Quality-Sample (100 Relations, Precision≥0.75, `vault/_meta/WORK_ORDER-kg-quality-sample-2026-05-29.md`) sind übertragbare Go/No-Go-Templates.

## MathBrain als Recherche-Backend fuer GENESIS (exakte Schnittstellen/Kommandos, Integrationsskizze)

**Vorhandene Schnittstellen (produktionsreif, keine Patches laut Befund):**
- **MCP-Server, stdio**: `py -m mathbrain.mcp_server` (`code/src/mathbrain/mcp_server.py`), 10 Tools: `mathbrain_search` (dense), `mathbrain_ask` (RAG), `mathbrain_reading_path`, `mathbrain_search_formula`, `mathbrain_ppr`, `mathbrain_bridges`, `mathbrain_hubs`, `mathbrain_get_note`, `mathbrain_list_sources`, `mathbrain_stats`. `.mcp.json` bereits konfiguriert.
- **CLI (Click)**: `ingest`, `ingest-all`, `reindex`, `ask`, `search`, `formula-search`, `guard-status` (`code/src/mathbrain/cli.py`); weitere Module: `self_rag`, `path_explain`, `node_rag`, `gfm_rag`, `formula_index`.
- **Direkt-Import**: jedes Python-Skript kann `mathbrain.*` importieren; `VectorIndex.load()`, `BM25Index.build()/.search()`, `FormulaIndex` (`code/src/mathbrain/vector_index.py`, `bm25.py`, `formula_index.py`).
- **Config/Env**: `MATHBRAIN_*` env-vars setzen vault/data/logs/state (`code/src/mathbrain/config.py`); `GENESIS_VALIDATOR_PATH` als denkbare Erweiterung.

**Live-Quellen-Adapter (REST, je `code/src/mathbrain/adapters/*.py`):** DLMF (`dlmf_adapter.py`, Public Domain Spezialfunktionen), Crossref (`crossref_adapter.py`), arXiv (`arxiv_adapter.py`, LaTeX-Quelle+PDF), OEIS (`oeis_adapter.py`), Semantic Scholar (`semantic_scholar_adapter.py`, citationCount→Trust), Zenodo (`zenodo_adapter.py`), NASA ADS (`nasa_ads_adapter_real.py`, Token nötig), OpenAlex (`openalex_adapter.py`, 250M CC0), zbMATH (`zbmath_adapter.py`, MSC), INSPIRE-HEP (`inspire_hep_adapter.py`). Registry mit Stub-Override (`code/src/mathbrain/adapters/registry.py`).

**Integrationsskizze:**
1. GENESIS Phase ε ruft `mathbrain_search_formula`/`mathbrain_ask` → Formel-Treffer mit Kontext und Note-Pfad (`code/src/mathbrain/formula_index.py`, FormulaEntry mit ±60-Wort-Kontext).
2. GENESIS als **Post-RAG-Critic**: Ask-Output durchläuft GENESIS-LogicCritic/γ-Gates, Confidence-Gate setzen (`code/src/mathbrain/rag.py`, `self_rag.py` 3-Stufen-Eskalation 0.55→0.05→Rerank).
3. **Gating am Eingang**: `source_trust.py` (trusted/neutral/low/blocked, Crank-Regex Limbertwig/Omega-Numbers, Gewichte 1.0/0.9/0.6/0.0) + `relevance.py` (4-Sphären, ~1761 Keywords, Whitelist arXiv/INSPIRE/zbMATH) als Trust-/Relevance-Layer für GENESIS-Ledger-Konfidenz.
4. **Formula-Gate als γ-Pre-Filter**: `formula_sanitizer.py` (HTML-Entity-Unescape, \lee→\le, Tag-Strip) → `formula_gate.py` (keep/trivial/malformed) vor den teuren C-1..C-18-Checks.
5. **Zentrale Lücke**: MathBrain hat **kein** Fakten-Ledger mit (fact_id, sources[], confidence, corroboration_count, status); `kg.sqlite.relations` trägt nur `source_note`. Für GENESIS-Korroboration wäre eine separate `genesis_ledger.sqlite` nötig (Befund aus `code/src/mathbrain/kg/store.py`, `canonical.py`).

## Krypto-Achse (die 56 Formeln, Top-Checks)

56 Dateien `vault/Formeln/crypto-*.md` vollständig gelesen. Top-Checks, die sich deterministisch als GENESIS-Validatoren registrieren lassen (analog `src/gen/physics_validation.py` VALIDATORS-Dict):

- **Nonce-Reuse-Familie (4 Checks)**: ECDSA (`crypto-ecdsa-nonce-reuse.md`, d-Leak), CTR (`crypto-ctr-mode.md`), GHASH/GCM (`crypto-ghash.md`, Joux-Wurzel), plus deterministischer Gegenpol Ed25519/RFC6979 (`crypto-ed25519.md`, `crypto-ecdsa.md`).
- **Birthday-Bound** (`crypto-birthday-bound.md`): generischer 2^(n/2)-Sicherheits-Check für jede Hash-/Block-Ausgabegröße.
- **Fault-/Side-Channel**: RSA-CRT-Bellcore (`crypto-fault-rsa-crt.md`), CPA-Hamming-Leck ρ(k) (`crypto-cpa-correlation.md`, Masking d+1).
- **PQ-Bounds**: ML-KEM-Rejection (`crypto-mlkem-encaps.md`), ML-DSA ‖z‖∞-Schwelle (`crypto-mldsa-sign.md`), LWE-Parameter gegen Regev-Reduktion (`crypto-lwe.md`), LLL/Hermite-Faktor (`crypto-lll-reduction.md`).
- **Protokoll-Audits**: X3DH-DH-Komposition (`crypto-x3dh.md`), Double-Ratchet MK-Shred (`crypto-double-ratchet.md`), TLS-1.3-Key-Schedule (`crypto-tls13-key-schedule.md`), HKDF-Parameter (`crypto-hkdf.md`), HMAC-Length-Extension (`crypto-hmac.md`), SPAKE2 (`crypto-spake2.md`).
- **ZK/Signatur**: Fiat-Shamir x-Hashing (`crypto-fiat-shamir.md`), Groth16 3-Pairing (`crypto-groth16-verify.md`), KZG 2-Pairing (`crypto-kzg.md`), BLS-Aggregat (`crypto-bls-signature.md`), Schnorr/MuSig2 (`crypto-schnorr.md`), Poly1305-Clamp (`crypto-poly1305.md`), AEAD-EtM (`crypto-aead-composition.md`).

Diese Bank ist der dichteste Block sofort einsatzbereiter closed-form-Checks im gesamten Sweep.

## Ehrlich nicht nutzbar / Fragmente

- **Reine Theorie ohne anwendbare Formeln**: Operator-Algebren/K-Theorie (`vault/Papers/arXiv/2605.26049.md`), Riemann-Hypothese-Operator-Beweis (`vault/Papers/Zenodo/20399267.md`), Quantum-Computing-Foundations als Future-Option (`vault/Konzepte/40-quantum-computing.md`).
- **Spezialdomänen ohne GENESIS-Kernbezug**: semcluster-005 Smart-Grid (`vault/Konzepte/semcluster-005.md`), -010 Medical-Imaging (`semcluster-010.md`), -020 Seismologie (`semcluster-020.md`), -030 Predator-Prey (`semcluster-030.md`).
- **Sozial-/angewandte Statistik**: Egypt-Marriage-Trends (`vault/Papers/DOAJ/480390a5a986407895d5ba27261ebadc.md`).
- **Fragmentarisch/Tutorial**: Wikibooks (`vault/Papers/Wikibooks/456373.md`).
- **Nur Metadaten / leer**: CrossRef-Registry, OpenAlex (10 Records), PDG (leer), Quantum-Journal (n_formulas meist 0) (`vault/Papers/CrossRef`, `…/OpenAlex`, `…/PDG`, `…/Quantum`).
- **Technisch blockiert**: ProofWiki via Cloudflare-403 (`code/src/mathbrain/adapters/proofwiki_adapter.py`).
- **Crank-Quellen (quarantäne, nicht löschen)**: Hall, Matthew (23 Zenodo „Chronos Field", `vault/Personen/hall-matthew.md`), Baladi/Silva (13/21 Zenodo-only, `…/silva-denivaldo.md`), Crank-Regex in `code/src/mathbrain/source_trust.py`.
- **Formel-Ingestion-Noise**: 30-40% trivial, 25-30% Fragment, 10-15% malformed (`vault/_meta/health/formula-sweep-audit-2026-06-01.md`, 200 hand-labeled Verdicts, ~640 quarantined in `data/formula_index.cleaned.json`).

## Ungelesene Restmasse (ehrlich beziffert)

- **vault/Papers (22.179 Notizen)**: <2% gelesen, <5% nach Relevanz-Signal gescreent. Konkret ungelesen u.a. `arXiv/2605.26057.md`, `arXiv/2605.26060.md` (beide has_formulas=true), ~58 weitere arXiv, CORE/1092, InternetArchive/3142, DOAJ/6950 (Abstracts), Zenodo/2552, OAPEN/858, OSF/517, DOAB/699, bioRxiv/8, EuropePMC/85 — Summe ~500+ substantive Paper.
- **vault/Konzepte**: Dateien 01-25, 29-39, 41-47, 49 breit aber nicht direkt validator-relevant; semcluster-002 bis -049 (~97% der ~50 Cluster); CyberSecurity/Kryptografie-Unterordner crypto-01..21 (separat von den 56 gelesenen `vault/Formeln/crypto-*.md`).
- **code/**: `cli.py` (1341 Z.), `ingestor.py` (515 Z.), 33+ Adapter, `scripts/`, `tests/` (310 passing, Coverage unbekannt), `.claude/agents/`, Reranker-Implementierungen `reranker_gte/colbert/math.py`.
- **data/**: tatsächliche Inhalte von `kg.sqlite`, `embeddings.npz`, `logs/` nur über Metadaten/Watermarks bekannt.
- **GENESIS-intern (nur Interfaces gelesen)**: `src/gen/verification/gates.py` (1805 Z., C-1..C-18), `src/gen/agents/`, `src/gen/ledger/`, `src/gen/uncertainty.py` (GUM), `src/gen/verification/derivation.py` (ab Z. 120+), `src/gen/demo.py`.
- **Personen-Netzwerk**: vollständige Affiliations (nur in Paper-Body), Autor-Genealogien, Bibliometrie, semantisches Distanz-Scoring über 2820×12228 Kanten — nicht durchgeführt.

## Top-10-Empfehlungen priorisiert

1. **Krypto-Validator-Bank (25 Checks)** aus `vault/Formeln/crypto-*.md` als deterministisches Registry analog `src/gen/physics_validation.py` — höchste Dichte sofort einsetzbarer closed-form-Checks, Nonce-Reuse-Familie zuerst.
2. **Conformal-Coverage-Kern** (`vault/Konzepte/60-conformal-foundations.md`) als neuer Kalibrierungs-Validator neben `src/gen/calibration.py`; Nonconformity-Baukasten (`vault/Konzepte/70-nonconformity-scoring.md`) als modulare Erweiterung.
3. **MathBrain-MCP-Server als GENESIS Phase-ε-Recherche-Backend** (`code/src/mathbrain/mcp_server.py`, 10 Tools, `.mcp.json` bereits konfiguriert) — keine neuen APIs nötig.
4. **Formula-Gate als γ-Pre-Filter** (`code/src/mathbrain/processing/formula_sanitizer.py` + `formula_gate.py`) vor C-1..C-18; 200-Sample-Labelset bereits vorhanden (`vault/_meta/health/formula-sweep-audit-2026-06-01.md`).
5. **Drift-Monitoring-Layer** (`vault/Konzepte/67-drift-sliding-window-fwer.md` + `68-drift-localization-clustering.md`) für Produktions-Streaming mit garantiertem FWER + Region-Lokalisierung.
6. **Source-Trust + Relevance als Ledger-Konfidenz-Gate** (`code/src/mathbrain/source_trust.py`, `relevance.py`) — Crank-Detektion als unabhängiger Validator; **plus** Bau einer fehlenden `genesis_ledger.sqlite` (Lücke aus `kg/store.py`).
7. **PDE/PINN closed-form Fehler-Bounds-Validator** (`vault/Papers/arXiv/2605.26054.md`, h²+τ⁴) als δ-Physik-Check für fraktionale/hybride Systeme.
8. **Koautorschafts-Korroborations-Validator** (`vault/Personen/*` + `data/kg.sqlite` authored_by 12.228 Kanten) — Single/Dual/Triple-Source-Konfidenz 0.6/0.8/0.95, plus Temporal-Konsistenz (Autor-Todesdatum vs. Paper-Jahr).
9. **DLMF/OEIS-Lookup-Validatoren** (`code/src/mathbrain/adapters/dlmf_adapter.py`, `oeis_adapter.py`) — autoritative Public-Domain-Verifikation von Spezialfunktionen und Integer-Sequenzen.
10. **Eval-/Kalibrierungs-Harness-Angleichung** (`code/src/mathbrain/eval/runner.py` ↔ `src/gen/evaluation.py` + `goldset/v1.json`) mit Bootstrap-CI + Regression-Gate (`vault/_meta/WORK_ORDER-eval-gate-2026-05-28.md`) und KG-Quality-Sample-Template (`…/WORK_ORDER-kg-quality-sample-2026-05-29.md`).

---
*Sweep-Metadaten: 13 Leser-Agenten (2 Wellen + Critic), 295 Dateien wirklich gelesen, 233 strukturierte Findings. Logs: Welle 1: 8/8 Leser fertig, 165 Findings, 234 Dateien gelesen; Nachlese-Aufträge: 5; Welle 2: 5 Leser, 68 weitere Findings*
