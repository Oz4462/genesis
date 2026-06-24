# BUILD_LOG

## 2026-06-23 — Tool-Integration: neu-installierte externe Tools real verdrahtet (PG/pgvector, CadQuery, KiCad, OpenFOAM, OpenMDAO)

**Verdict: REAL.** Fünf zuvor degradiert/Fassade laufende import-guarded Hooks an echte, jetzt
installierte Tools angeschlossen — alles fail-loud, keine stillen Defaults, Negativtests inklusive.

1. **PostgreSQL-Ledger + pgvector** (`src/gen/ledger/postgres.py`, `sql/002_embeddings.sql`): `genesis`-Rolle
   (peer-auth Socket) + DB owner gesetzt, `CREATE EXTENSION vector` (0.6.0). `PostgresConfig.from_env()`
   (GENESIS_DB_*-Defaults), `ensure_schema()` (idempotent — `DROP TRIGGER IF EXISTS` in 001; **Dimensions-
   Mismatch-Guard** fail-loud), `store_embedding()`/`recall_similar()` mit **injizierbarem** Embedder (kein
   harter Ollama-Zwang, Dimension explizit). Cosine-Recall liefert den richtigen Claim MIT rekonstruierter
   Provenance. Test `tests/test_ledger_postgres_integration.py`: **6 passed** (Round-Trip, embed_model-
   Isolation, Dim-Mismatch loud, DB-Trigger-Reject sourceless, FK-Reject unknown claim, Dim-Guard).
2. **CadQuery → exakte OCCT-BREP via Subprozess-Bridge** (`src/gen/cad/cadquery_bridge.py` +
   `cadquery_worker.py`): cadquery NIE im Haupt-venv (degradiert numpy) — Worker läuft in `/home/genesis/
   .venv-cad`, JSON rein/raus. `brep.exact_volume/is_valid/interferes` + `export/brep_stl` delegieren jetzt
   an die Bridge (in-process-Fallback bleibt). Neu: STEP-Export (ISO-10303). Test
   `tests/test_cadquery_bridge_integration.py`: **9 passed** (boolean-Volumen == analytisch, exakte
   Interferenz schlägt AABB, STL, STEP, brep-API-Routing, 3 Negativtests). Nebenwirkung: 34 Bundle/STL-Tests
   (`test_bundle/future_ideas/visionary_ideas/competitive_humanoid`) produzieren jetzt ECHTE STLs statt
   „missing" — Gating bridge-aware aktualisiert, **34 passed**.
3. **KiCad → echtes `kicad-cli` (v7.0.11)** (`src/gen/cad/kicad_cli.py`, `electronics.validate_pcb_with_kicad_cli`):
   KiCads EIGENE Engine lädt unsere `.kicad_pcb` und exportiert SVG/Gerbers/STEP — echte Validierung statt
   nur Regex. `_run_cli` fängt KiCads exit-0-ohne-Output-Falle (kein erfundener Pass). Ehrliche Grenze
   gemessen: KiCad 7 LEHNT das minimale Schema-Skelett ab; ERC/DRC erst ab KiCad 8 (deklariert). Test
   `tests/test_kicad_cli_integration.py`: **6 passed** (PCB→SVG/Gerbers/STEP real geladen, Netlist aus echtem
   Demo-Schema, 3 Negativtests).
4. **OpenFOAM → neue CFD-Validierungsachse** (`src/gen/cfd.py`): `poiseuille_channel_check` fährt echten
   `blockMesh`+`simpleFoam`-Lauf (laminarer Kanal), vergleicht das vom Solver UNABHÄNGIG berechnete
   Geschwindigkeitsfeld gegen die analytische Poiseuille-Form (u_max-Fehler 2.1e-7; Profil-L2 0.086 % =
   echter Diskretisierungsfehler). Separater `gate_cfd` + `CFD_VALIDATORS` (bewusst NICHT im schnellen
   δ-Physik-Gate). Test `tests/test_cfd_integration.py`: **8 passed** (inkl. Negativ-Physik + Gate +
   missing-binary loud). Sourct `/usr/share/openfoam/etc/bashrc`.
5. **OpenMDAO → MDO-Backend** (`src/gen/inventor/optimize.py`): `OpenMdaoOptimizer.minimize()` baut echtes
   `om.Problem` + SLSQP, konvergiert auf bekannte Optima (Paraboloid (3,-1) → 3.0e-7). Ehrlich dokumentiert:
   `select()` nutzt OpenMDAO NICHT (Listen-Filter ≠ kontinuierlicher Optimierer) → gleicher Pareto wie
   `ParetoOptimizer`. Test `tests/test_optimize_openmdao.py`: **14 passed** (inkl. Nicht-Konvergenz →
   `OptimizationError`, absent-backend → `OptimizerUnavailable`).

**Volle Offline-Suite: 2479 passed / 43 skipped / 2 failed.** Die 2 Failures sind in
`tests/test_lumencrucible.py` und **vorbestehend** (bewiesen via `git stash` gegen HEAD — Enum-vs-String-
Vergleich + multi_domain['software']=None); von mir NICHT berührt. Ruff sauber auf allen Dateien.
**Nicht committet** (Orchestrator committet nach Verifikation). `.crew/`/Queue unberührt.

DEFERRED (ehrlich): FreeCAD (nur als GUI-Flatpak `org.freecad.FreeCAD 1.1.1` — headless-awkward; FEM ist
ohnehin pure-numpy), OpenModelica/OMPython, Qdrant-als-Store, ROS2-Export, OpenCV — keine Code-Hooks in
`src/` vorhanden; saubere Next-Steps.

### Selbstkontrolle + 4 Linsen
- [x] Interfaces erfüllt, Typen+Docstrings, Fehlerfälle dokumentiert
- [x] Tests grün inkl. Negativtests pro Tool (fehlende Quelle/Tool-Fehler/Widerspruch fail-loud)
- [x] Ledger: pgvector-Recall liefert Claims MIT Provenance; Trigger-Layer live bewiesen
- [x] Keine Gate-Regression; CFD-Gate bewusst separat vom schnellen δ-Gate
- [x] Doku: jeder Modul-Docstring ehrlich (inkl. gemessene Grenzen, z.B. KiCad-7-Skelett-Reject)
- [x] BUILD_LOG-Eintrag
- L1 (Wahrheit): jede Tool-Behauptung durch echten Lauf bewiesen (PG round-trip, OCCT-Volumen vs analytisch,
  KiCad-Load, OpenFOAM vs closed-form, SLSQP vs bekanntes Optimum) — keine erfundenen Zahlen.
- L2 (Drift): bestehende Tests grün; brep_stl-Verhalten verbessert (STL jetzt produzierbar) → abhängige
  Tests bridge-aware nachgezogen, Doc==Code.
- L3 (Vollständig/Naht): Subprozess-Isolation hält numpy sauber; PG-Treiber bleibt aus dem Core; Negativ-
  pfade decken die Nähte ab.
- L4 (Realisierbarkeit): alle 5 Tool-Integrationstests real ausgeführt (PG/CadQuery/KiCad/CFD/OpenMDAO),
  Server/Binaries waren up → pass, nicht skip.

## 2026-06-23 — T01 Depth-Audit + Härtung `discovery/multiterm.py`

**Verdict: REAL.** Neuer Charakterisierungs-Test `tests/test_multiterm_characterization.py` (29 Fälle,
3 Hypothesis-Property-Tests) beweist, dass Greedy-Selektion + lineare lstsq + Pruning + Held-out-Scoring
wirklich berechnet werden (Output folgt dem Input; gemeldetes R²/RMSE == unabhängig nachgerechnet;
Linearität Ziel×k ⇒ Koeffizient×k).

**Defekt gefunden + behoben:** `discover_multiterm(max_terms<1)` gab still ein erfundenes 1-Term-Gesetz
zurück (Greedy-Schleife läuft nie → `not selected`-Fallback griff fälschlich). Guard
`if max_terms < 1: raise ValueError` ergänzt (fail-loud, „keine stillen Defaults") + Regressionstest.
Greedy-Nicht-Global-Optimalität ist eine dokumentierte ehrliche Grenze, kein Bug — out-of-sample gefangen.

Bestehende `tests/test_discovery_multiterm.py` weiter grün (14/14). Details: `docs/audit/DEPTH_AUDIT_multiterm.md`.
4 Linsen angewendet (L1 Wahrheit / L2 Drift / L3 Naht / L4 Realisierbarkeit).

## 2026-06-23 — T03 Depth-Audit + Fix `discovery/surrogate.py` (prefilter + physics surrogate)

**Verdict: REAL.**

- Neuer Charakterisierungs-Test `tests/discovery/test_surrogate_characterization.py` (10 Tests, 3 Hypothesis property-based): train on known f, held-out accuracy within bound + meaningfully better than constant baseline, uncertainty monotone/high on extrapolation, documented errors on <2 pts / bad frac / non-finite.
- Pre-existing discovery prefilter (subsample R²) unchanged for happy path; added explicit guards + negative tests for n<2 and out-of-range sample_fraction (was silent/raised from inside numpy.choice).
- Echter RBF-Surrogate implementiert (`build_surrogate`/`predict_surrogate`): quantifizierbar genau, deterministisch, honest unc.
- Modul-Docstring ehrlich erweitert (beide Rollen + shared "never confirms" Vertrag). Eigene .copy() Snapshots + korrigierter Docstring.
- Legacy `tests/test_discovery_surrogate.py` 5/5 grün. Keine neuen Deps.

Details + 4 Linsen: `docs/audit/surrogate.md`.

### Selbstkontrolle + 4 Linsen
- [x] Interface erfüllt, Typen geprüft
- [x] Tests grün (inkl. Negativtests für beide Pfade)
- [x] Ledger: n/a (keine fakten-basierten Claims mit Quellen)
- [x] Keine Gate-Änderung (Surrogate ist Pre-Filter/Approx)
- [x] Doku aktualisiert (Modul + audit/surrogate.md)
- [x] BUILD_LOG Eintrag
- L1 (Wahrheit): alle Claims durch Test auf closed-form f bewiesen + Quellen in Test.
- L2 (Drift): Pre-Filter Verhalten (passend) byte-stabil; neue Guards schließen echte Lücke; Doc=Code.
- L3 (Vollständig/Naht): nur Scope-Dateien; Legacy unberührt; Seams zu engine stabil.
- L4 (Realisierbarkeit): Guards exakt getestet (assert message), full pytest grün, Hypo-Props, minimaler Fix.

## T03 — Depth-audit + harden `reality_fork.py` (counterfactual physics sandbox)

**Verdikt: REAL** (ein ehrlichkeits-relevanter Defekt behoben).

- Neuer Charakterisierungs-Test `tests/test_reality_fork_characterization.py` (14 Tests, 3
  property-based via Hypothesis): beweist, dass Dimensions-Fork = Gauß'sches Gesetz
  `F ∝ r^(-(D-1))` und Konstanten-Fork = Potenzgesetz `(new/base)^exp` **berechnet** werden
  (Output ändert sich mit dem Input, keine kanned strings), und dass die Ehrlichkeits-
  Invarianten halten (Basis D=3 → `counterfactual=False`, alle anderen `True`, kein Fork
  trägt `bestaetigt`).
- **Defekt gefunden+behoben** in `src/gen/discovery/reality_fork.py`: `fork_constant` ließ
  NaN/inf-Magnituden durch den `<= 0.0`-Guard schlüpfen (NaN-Vergleiche sind immer `False`)
  und stempelte einen nicht-finiten Skalenfaktor `internally_consistent=True` — ein stiller
  nicht-finiter „Fakt", der dem Finite-Power-Law-Vertrag widerspricht (Kernprinzip 4). Fix:
  Finitheits-Guard für base/new/exponent + Overflow-Guard auf den Faktor → ehrliche
  Abstention (`internally_consistent=False`, kein `target_scale_factor`).
- **Runde 2 (Review-Finding `rubberduck`):** CPython wirft beim Potenz-Overflow
  `OverflowError` (kein `inf`), z.B. `base=1, new=1e10, exp=40` → `1e400`; der reine
  `isfinite`-Guard ließ die Exception ungefangen entkommen → Absturz statt Flag. Fix: Potenz
  in `try/except OverflowError` gekapselt, beide Überlauf-Pfade → flagged-inconsistent. Neuer
  Regressionstest `test_power_overflow_is_flagged_not_crashed`.
- **Runde 3 (Review-Finding `rubberduck`):** zweiter Crash-Pfad — Verhältnis `new/base`
  unterläuft nach `0.0` (z.B. `1e-300/1e300`) + negativer Exponent → `ZeroDivisionError`
  (nicht `OverflowError`), entkam dem alleinigen `except OverflowError`. Fix:
  `except (OverflowError, ZeroDivisionError)`. Neuer Regressionstest
  `test_ratio_underflow_with_negative_exponent_is_flagged_not_crashed`.
- Öffentliche Signaturen unverändert; bestehende `tests/test_discovery_reality_fork.py` grün.
- 4 Linsen: L1 (Math gegen Gauß/Potenzgesetz verifiziert), L2 (Counterfactual-/`bestaetigt`-
  Invarianten getestet), L3 (Signaturen stabil, keine Downstream-Brüche), L4 (stiller
  nicht-finiter Defekt + Overflow-Crash beseitigt).
- **21 Tests grün** (16 neu + 5 bestehend). Details: `docs/audit/DEPTH_AUDIT_reality_fork.md`.

## T04 — Depth-audit + harden `separability.py` (additive/multiplicative separability)

**Verdict: REAL** — `analyze_separability` genuinely evaluates the mixed second difference
`y(++) − y(+−) − y(−+) + y(−−)` (and its `log y` form for multiplicative mode); the grouping is
computed from the per-pair residual, not canned.

- **Added** `tests/test_separability_characterization.py`: facade-killer proving (a) the grouping/
  `max_interaction` changes meaningfully when the function's coupling changes (additive→singletons,
  product→one group, partial `a·b+c` isolates `{a,b}` from `{c}`, magnitude scales with coupling
  strength), (b) the log path genuinely flips `a*b`'s verdict between modes (anchored to a hand-computed
  log corner sum), and (c) every documented guard raises. Includes Hypothesis property tests sweeping the
  coefficient/exponent space.
- **Fixed** `src/gen/discovery/separability.py`: two confirmed silent-wrong-value defects (no-silent-
  defaults). `n_bases < 1` skipped the sampling loop → fabricated "fully separable" (a coupled `a*b` read
  as separable); `tol < 0` → fabricated "all coupled" (a pure sum read as coupled). Both now raise
  `ValueError`; docstring updated. The only repo caller uses defaults, so legacy paths are unchanged.
- **Tests:** `tests/test_separability_characterization.py` + legacy `test_separability.py` +
  `test_engine_separability_annotation.py` → 28 passed. `test_discovery_engine.py` → 6 passed.
- Full audit + 4 Linsen in `docs/audit/DEPTH_AUDIT_separability.md`.

## 2026-06-23 — T02 Depth-Audit + Härtung `discovery/srbench_hygiene.py`

**Verdict: REAL** (headline "leakage prevention + OOS + deterministic splits" jetzt selbst-verifizierbar).

- Neuer Charakterisierungs-Test `tests/discovery/test_srbench_hygiene_characterization.py` (13 Tests, 2 Hypothesis-Property-Suites): deliberate leakage (overlapping rows) wird von `check_train_test_overlap` + `assert_no_split_leakage` erkannt+rejected; clean akzeptiert; recompute des held-out R² aus train-only Fit exakt == reported oos_test_r2 (beweist "truly held-out", kein Leak); noise rejected, n<4 → exakter ValueError; Split-Overlap-Invariante + Determinismus via @given.
- **Defekt behoben:** `hygiene_gate(seed=...)` übergab seed nicht an `out_of_sample_validate` (OOS lief immer default-0) — jetzt forwarded; plus `split_overlap` im Report + explizite Checker-Fns (Leakage-Metric real, 0 für internes OOS).
- Hygiene-Gate + Legacy-Tests grün (13+5). Keine Änderung außerhalb Scope.
- 4 Linsen angewendet (L1: recompute + intersect bewiesen; L2: Seed-Drift + Headline-Facade-Risiko geschlossen; L3: Naht zu validation via public API, Scope exakt; L4: minimal fail-loud + Property-Tests).
- Details: `docs/audit/srbench_hygiene.md`.

## 2026-06-23 — T05 Depth-Audit + Härtung `discovery/simulated_data.py`

Verdikt **REAL**: `problem_from_simulation`/`discover_from_simulation` sampeln echt eine geschlossene
Form, generieren die Zieldaten selbst und gewinnen das Gesetz dimensional zurück (kein Stub).
Neue Charakterisierungssuite `tests/test_simulated_data_characterization.py` (21 Tests, inkl.
2 Hypothesis-Property-Tests: Potenzgesetz-Recovery für eine Familie + `baked`-Round-Trip-Identität;
Negativ-Kontrolle additive Form; alle dokumentierten Guards).

**Gefundener + behobener Defekt (L2):** Namens-Kollision (zwei Eingaben gleichen Namens, oder
Eingabe == Konstante) kollabierte still auf eine Spalte und korrumpierte den dimensionalen Solve.
Minimaler Eindeutigkeits-Guard in `problem_from_simulation` → lautes `ValueError` („keine stillen
Defaults"). Öffentliche Signaturen + Sampling unverändert; vorbestehende Tests grün (27 passed).
Details: `docs/audit/DEPTH_AUDIT_simulated_data.md`.

## T01 — Depth-Audit + Fix: discovery/sindy.py (SINDy) — 2026-06-23
VERDICT **REAL**. Headline-Claim (sparse identification of nonlinear dynamics) gegen reale Numerik
charakterisiert in `tests/discovery/test_sindy_characterization.py` (8 Tests grün, inkl. Hypothesis-
Invariante): STLSQ findet aus einem bekannten kubischen System exakt Support + Koeffizienten, nullt
Störterme exakt (vs. dichter `np.linalg.lstsq`-Fit), refüsiert (Null-Modell) ein nicht-sparses Ziel und
meldet ehrlich niedrigeres R² bei unzureichender Bibliothek statt Fabrikation; Negativfälle (fehlende
Daten / threshold<0) → lautes `ValueError`. Kein Quellcode-Verhalten geändert (Modul war real); nur
Audit-Note im Docstring. Details: `docs/audit/sindy.md`.

---

## 2026-06-23 — Depth-Audit + Fix: `discovery/symbiosis.py` (Grok Cross-Model-Symbiose) [T04]

**Verdikt: REAL (nach gezielter Ergänzung).** Die bestehenden `symbiosis_discover`/`council_discover`
nutzten als Verifikator den deterministischen Gate (echt, aber nicht die *wörtliche*
Modell-gegen-Modell-Drift-Prüfung aus CLAUDE.md §3). Neu: `cross_model_drift_check(...) -> DriftReport`
lässt ein **zweites, anders-familiges** Modell (dependency-injizierter `LLMClient`, offline via
`ScriptedLLM`) dieselbe Frage unabhängig beantworten. `verified=True` nur bei echter
Cross-Model-Korroboration; Widerspruch ⇒ `drift` (kein stiller Pass); Verifikator-Fehler/Timeout ⇒
ehrliche `abstention`; gleiche Familie ⇒ `ModelConflictError` (Selbstcheck verweigert). 6 neue Tests
inkl. zwei Negativtests + ein Hypothesis-Property (falsches Zweiturteil kann nie fälschlich
verifizieren), alle offline grün. 4 Linsen + Details: `docs/audit/symbiosis.md`.

---

## 2026-06-23 — Depth-Audit T05: discovery/symbolic_search.py (VERDICT: REAL)
Tiefen-Audit des Open-Form-GP-Symbolic-Regression-Suchers. Charakterisierungstest
(`tests/discovery/test_symbolic_search_characterization.py`, 9 Tests grün) beweist ECHTE Suche,
kein Lookup: Rediscovery der transzendenten `y = 3·sin(x)+2` (exakte Struktur + Koeffizienten,
R² ≈ 1 out-of-sample — eine Form, die die enge Power-Law-`engine.py` nicht darstellen kann),
strikt steigende + monoton nicht-fallende Fitness über Generationen (reale Optimierung, kein
Einmal-Rate), reines Rauschen → ehrliches `unentschieden` (Out-of-Sample-Gate kollabiert),
fehlende/inkonsistente Daten → dokumentierter `ValueError`. Hypothesis-Property: Seed-Determinismus
+ Recovery beliebiger Affin-Gesetze. KEINE Verhaltensänderung nötig (Modul war bereits korrekt);
nur Modul-Docstring-Audit-Notiz ergänzt. 4 Linsen angewendet. Details:
`docs/audit/symbolic_search.md`.

## 2026-06-24 — Depth-Audit `printability.py` (FDM Design-Regeln) [T01]
Charakterisierungs-Suite `tests/test_printability_characterization.py` (25 Tests,
Hypothesis-property-based) für die 7 Closed-Form-FDM-Validatoren (bridge_span,
fit_clearance, pin_diameter, thread_size, unsupported_wall, emboss_detail,
layer_adhesion). Fassaden-Killer pro Validator: (a) Output skaliert nachweisbar mit
dem treibenden Input (doppelter Span → halber safety_factor; fit/kind wählt echten
Floor; allowed_stress = z_retention×base_strength) — kein gecanntes Konstant; (b)
jeder dokumentierte ValueError feuert exakt; (c) Null-Span/Null-Stress → ehrliches
`inf`. Property-Invarianten: safety_factor==q/limit, ok⇔q≥limit, use_insert_or_tap==¬ok.
**Verdikt REAL — keine Quelländerung** ("change nothing if correct"). Legacy (15) +
neu (25) grün. 4 Linsen angewendet. Details: `docs/audit/DEPTH_AUDIT_printability.md`.

---

## T02: Depth-audit proof_kernels.py (z3 QF_NRA) — 2026-06-24
**Task:** NEW `tests/test_proof_kernels_characterization.py` (with `pytest.importorskip('z3')` at top) proving Z3IdentityKernel is a real decision procedure (genuine UNSAT → 'proved'; sat+ce → 'refuted'; abstentions → 'unsupported') + LeanStub always abstains. Property tests. Edit src ONLY on genuine defect. Add DEPTH_AUDIT + BUILD_LOG entry.
**Research (pre-edit):** read proof_kernels.py + legacy test_proof_kernels.py + proof_loop + identity_research callers, existing DEPTH_AUDIT_* + team decisions (facade-killer a+b, property, real API, "change nothing unless defect", isolation, z3 skip at top), probe exec for ce/unsat/0**neg/unbound/empty.
**Outcome:** 21-pass char test (example + 2 Hypothesis determinism/equivalence + explicit UNSAT string + ce witness plug-in + all abstention NEGATIVEs + domain matrix + unknown contract). Guard added only for surfaced defect.
**Defect scan:** Pre-analysis: correct (UNSAT path real, ce genuine or {} valid for ground false, all abstentions honest). Rubberduck (post-round1) surfaced: 0**negative-int emits 1/0 (undefined) instead of abstain — real L4 (silent bad term). Fixed with minimal guard in _to_z3 + explanatory comment (0**0 convention kept+documented). Also addressed: empty-ce doc, explicit UNSAT assert, more domain combos, timeout-unknown path.
**Files touched (strict scope):** src/gen/proof_kernels.py (1-line guard + comment only), tests/test_proof_kernels_characterization.py (new + extensions), docs/audit/DEPTH_AUDIT_proof_kernels.md (new), BUILD_LOG.md (this append). Legacy test_proof_kernels.py untouched.
**Test exec (green):** PYTHONPATH=src pytest tests/test_proof_kernels_characterization.py -q → 21 passed. Combined slice (char + legacy proof + proof_loop char) 24+ passed.
**4 Linsen + Selbstkontrolle:** L1 (verbatim UNSAT detail + ce subs recheck); L2 (status+detail+contract match docstring); L3 (all paths + matrix + properties; legacy protected); L4 (scoped to 0**neg + ce-empty + domain/unknown; no creep; guarded imports). DoD met: facade-detector, property tests, neg tests, explicit REAL verdict, only-justified src delta, audit+log present.
**Verdict:** T02 COMPLETE. proof_kernels is REAL (z3 is genuine decision proc; Lean stub honest). Guard only for the one undefined-input L4 case.
**Evidence:** new test (21), DEPTH_AUDIT, this entry, pytest output above. Isolation + "pass using own files + pre-existing" satisfied.

---

## 2026-06-24 — Depth-Audit `ratification.py` (T03, HITL Sign-off-Gate) — REAL, keine Quell-Änderung
Charakterisierung des No-Default-Approval-Vertrags (Research #5 / Agent-SDK „never fake approval"):
`ratification_packet` ist nachweislich aus Inputs abgeleitet (mehr Decisions/Gaps → mehr blockierende
Items mit deren Inhalt; Gate-Verdikt PASS→Evidenz / FAIL→blockierend; Abweichungs-Anzahl aus
`result.failures` gelesen, nicht hartcodiert). `is_ratified` gepinnt als Property (200 Bsp.):
`== (benannter Approver) ∧ (jede blockierende Ref explizit signiert)` — anonymer Voll-Sign-off,
ein fehlendes Item, nicht-signiertes FAILED-Gate und leeres Packet ohne Mensch sind alle NICHT
„done"; `SignOff` friert mutables Approval-Set zu `frozenset` (kein nachträgliches Nachschmuggeln).
14 neue Tests (inkl. 2 Hypothesis-Properties) grün, Legacy-Test (9) unverändert grün. Modul war
bereits korrekt → keine Quell-Edits („change nothing if correct"). 4 Linsen angewendet. Details:
`docs/audit/DEPTH_AUDIT_ratification.md`.

---

## 2026-06-24 — Depth-Audit T04: reality.py (GATE δ⁺ reality proof) (VERDICT: REAL)
Tiefen-Audit des deterministischen Reality-Proofs. Charakterisierungstest
(`tests/test_reality_characterization.py`, 25 Tests grün, offline) beweist als Facade-Killer:
(a) das Verdikt ist AUS DEN ZAHLEN GERECHNET, kein Konstanten-Stub — Residuum trackt den
gesweepten Messwert (≥4 verschiedene Werte == `|measured−predicted|`), die Toleranz-Grenze
flippt den Status inklusiv, und die Einheiten-Skala konvertiert echt (1.5 m == 150 cm ==
1500 mm korroborieren, 1600 mm → 1.6 m widerlegt); (b) jede Abstention/Fail-loud feuert exakt —
INCONCLUSIVE bei Dimensions-Mismatch/unparsbar/keine-SI-Skala/keine-Provenance/nicht-finit, und
`gate_delta_plus` mit allen vier Codes (GROUNDING_UNKNOWN_CLAIM/EXPERIMENT_MISMATCH/
UNSOURCED_MEASUREMENT/DEAD_MEASUREMENT_SOURCE), Akkumulation ohne Short-Circuit und dem
Schlüssel-Vertrag „REFUTED lässt das Gate bestehen". Hypothesis-Properties: Residuum==Distanz +
Status 1:1, m↔cm/mm-Round-Trip, Determinismus (A5). KEINE Quellcode-Änderung nötig (Modul war
bereits korrekt). 4 Linsen angewendet. Details: `docs/audit/DEPTH_AUDIT_reality.md`.

---

## 2026-06-24 — Depth-Audit T05: refinement.py (VERDICT: REAL)
Tiefen-Audit des Verify→Refine-Controllers (bounded loop um beliebiges Gate).
Charakterisierungstest (`tests/test_refinement_characterization.py`, 12 Tests grün, davon
2 Negativtests + 2 Hypothesis-Properties) beweist einen EHRLICHEN bounded Controller, kein
Fassaden-Stub: `directives_from_gate` mappt jede Failure (bekannter Code → Template, unbekannter
→ generische Direktive, die das Detail trägt, nie erfunden); `refine_until_pass` konvergiert nur
bei echtem Gate-Pass, meldet `stuck=True` bei wiederkehrender Failure-**Signatur** (inkl. A↔B-
Oszillation, die der mengenbasierte Detektor fängt), `converged=False` mit Residuals bei
erschöpftem Budget, `ValueError` bei nicht-positivem Budget. Facade-Killer: Outcome wird von der
Regenerator-Stärke getrieben (stark → converged, schwach → nicht), Rundenzahl = geschlossene Form
`ceil((threshold−start)/step)`. Isoliert über ein rein deterministisches, physik-/LLM-freies
Scripted-Gate (Defekt-Level im realen `Question.run_id`). KEINE Verhaltensänderung nötig (Modul war
bereits korrekt und ehrlich). 4 Linsen angewendet. Details: `docs/audit/DEPTH_AUDIT_refinement.md`.
