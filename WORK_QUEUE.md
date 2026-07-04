# WORK QUEUE — GENESIS

> Voller Kontext: `docs/integration/SESSION_HANDOFF.md`. Branch `feat/app-integration-phase0-2`
> (76 ahead of main, lokal, KEIN Push). Suite: 1204 passed / 9 skipped. Ollama gestoppt.

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
- tools/ — DONE (Claude×Grok, 11 Grok-Findings reconciled): fetch.py FIXED (Scheme-Allowlist http/https vor dem
  Fetch → file://|ftp://|data:// werden zu honest ok=False, transport-unabhängig, im Ledger); http.py FIXED
  (max_bytes-Cap auf read() gegen untrusted-body-DoS, fail statt silent-truncate→A5); search.py FIXED (S2+Wikipedia:
  malformed Envelope [fehlender data/query-Key]→SearchBackendError vs. honest-empty→[]); +13 adversariale Tests.
  arxiv_backend.py CLEAN (ET-Parse raised auf bad XML; trusted Host). REBUTTED→D8/D9/D10 (s.u.). Suite 1166/9, ruff clean.
- agents/ scout+scholar+skeptic — DONE (Claude×Grok, eine Review-Pass, je isoliert+eval-gated gefixt):
  · skeptic FIXED non-finite-Confidence (NaN durch _clamp01 → VERIFIED+NaN umgeht `confidence<τ`); Wurzel in parsing.py
    (parse_constant lehnt NaN/Inf-Literale am untrusted Boundary ab, systemisch alle Agenten) + skeptic._clamp01 NaN→0.0.
    Grok korrobierte den NaN-Fund unabhängig (high).
  · scout FIXED array-shape-Guard (Objekt-Reply iterierte Dict-Keys als Müll-Queries); scholar FIXED NFKC-Quote-Fold
    + Docstring-Korrektur (Guard war case+ws, Doc sagte nur ws).
  · REBUTTED Grok scholar-high (text↔quote Token-Overlap): architektur-inkompatibel (text=GERMAN, quote=original-lang →
    cross-lingual ≈0 → over-reject); Text-Treue ist Skeptics Job. REBUTTED skeptic _aggregate min-conf-refute (würde
    REFUTED unsicherer machen — Asymmetrie ist gewollt). Suite 1176/9, ruff clean.
- agents/ conductor+synthesizer+forge+architect — DONE (Claude×Grok, eval-gated, commit per module, no push):
  · conductor `1f62c5c` FIXED `_decompose` array-shape + count guard — an LLM JSON-OBJECT reply iterated its dict
    KEYS as bogus sub-questions (extract_json enforces object/array root); +`_MAX_SUB_QUESTIONS=10` DoS cap. Same
    boundary bug already fixed in scout/scholar; Grok-corroborated high+low. +2 boundary tests.
  · synthesizer `4ee3e0b` FIXED crash-proof `name = str(...)` coercion (non-string name → `123.strip()` →
    AttributeError OUTSIDE the LLMOutputError handler → crashed the β run instead of abstaining; Grok high) +
    `sorted(verified.items())` byte-stable prompt (Principle 5) + dup-approach drop log (forge parity). +2 tests.
  · forge `0e12df0` FIXED crash-proof statement/mechanism `str(...)` coercion (same boundary crash at TWO fields;
    Grok high). forge already had the sorted prompt + dup-log. +1 test.
  · architect `7609994` FIXED `_as_list()` on all 8 `proposal.get(field)` iteration sites (non-iterable field →
    TypeError out of `_assemble`, which runs outside the LLMOutputError handler → crash; Grok high) +
    `_parse_geometry` depth cap 64 (pure-Python recursion hits the stack wall before the C json parser; Grok high) +
    `sorted(verified.items())` prompt. REBUTTED G4 (transport errors MUST fail-loud, not abstain — abstaining would
    mask infra failure as honest abstention) + G5 (derived `Quantity()` is pre-validated unreachable-to-raise:
    evaluate_formula fail-loud on non-finite, `_dimensionally_sound` pre-checks units, measurand regex-checked,
    DERIVED+derivation consistent by construction → a try/except there guards an untestable path → no-defensive-layer
    rule). +3 tests. Suite 1185/9, ruff clean at every commit.
- agents/ PAKET conductor+synthesizer+forge+architect KOMPLETT → agents/ Verzeichnis vollständig reviewt
  (scout/scholar/skeptic done earlier; conductor/synthesizer/forge/architect this session).
- pipeline.py + Quality-Engine (Schritt 6) — KOMPLETT 11/11 (Claude×Grok, eval-gated, commit/Modul, kein Push):
  · pipeline.py `13e1cde` FIXED: `physics_ok` braucht jetzt `physics_checked` (vakuöser 0-Check-Pass war ok) +
    neuer `grounding_failed`-Status (corroboration wurde im `overall` ignoriert → `physics_verified` trotz
    zirkulärer Korroboration). Beide Grok-high.
  · evaluation.py `a5c916b` FIXED: Physics-Verdikt zählt Gaps als non-pass (gleicher Mask wie pipeline) +
    vakuöse `leak_rate`/`false_alarm_rate` → None statt 0.0 + ehrliche Coverage-Doku (5/18 C-Codes = Subset) + Scope.
  · refinement.py `d7d1878` FIXED: Oszillations-/Zyklus-Erkennung (seen-Set statt nur letzter Signatur) +
    kollisionsfreie `(code,claim_id,detail)`-Signatur + domänen-neutrale PHYSICS_CHECK_FAILED-Direktive.
  · clarification.py `17479d4` FIXED: `unblocks` listet nur Checks, die der Answer ALLEIN runnable macht
    (war: jeder beitragende Check → überstellt) + measurand-stabile qid; priority bleibt EVPI-Proxy.
  · grounding_integrity.py — CLEAN (konservativ-korrekt: kein falsches „circular", kein verpasstes dangling/refuted
    in der Map; Grok bestätigt). Limitierungen → D15.
  · constraint_consistency.py — CLEAN (Sign-Set-Algebra provably-complete für pairwise-same-expr; Grok bestätigt).
  · geometry_verification.py — REVIEWED, deferred (D15): exakte Cross-Checks solide (Hemisphären-Guard grün), ABER
    NICHT in pipeline verdrahtet (nur self-tested; README §6 impliziert Komposition) + non-exact-Looseness + Rotation-
    AABB-False-Negative (isclose statt Containment) + ungeguardete Kernel-Calls. Alle unerreicht (nicht im Prod-Pfad).
  · ratification.py `101653f` FIXED: namespaced+unique refs (Cross-Kind/Duplikat-Bypass), named-approver
    erforderlich (anonyme/leere Approval ≠ done — alignt omega SIGNOFF_WITHOUT_APPROVER), frozenset-Coercion.
  · calibration.py `6c9748f` FIXED: ECE-Bin-Index-Clamp (c<0 → Negativindex → Top-Bin) + target_precision-Validierung.
    **Conformal-Math von beiden Reviewern als korrekt bestätigt** (kein Off-by-one).
  · telemetry.py `8bf749f` FIXED: reservierte Attribut-Keys in span gedroppt (TypeError-in-finally maskierte Body-Exc) +
    to_otel kind authoritative.
  · goldset.py `d19f449` FIXED: fail-loud Loader (alle 3 Kinds, leere Tokens, Typ-Validierung) + Scorer (empty-Guard,
    text-bearing-abstention = Halluzination).
  · >>> Schritt 6 KOMPLETT: 11/11 reviewt — 8 fixed, 2 CLEAN (grounding_integrity, constraint_consistency),
    1 deferred (geometry_verification). Roter Faden: die Quality-Engine, die gegen „Pass maskiert Lücke" baut,
    hatte denselben Fehler mehrfach in sich (vakuöse Pässe, ignorierte Achsen, Detektions-Lücken). <<<
- D16 (Schritt-6-Tail deferred): goldset G3 (fact-Token-Match case-sensitive Substring → „4" matcht „14"; deferred
  Live-Pfad, Fixture-Review nötig) + G9/G10 (File/JSON→ValueError, extra outcome keys). telemetry G5-G8, calibration
  vakuöse Skalare, ratification G7/G8 — alle low/defensiv, in den Commit-Messages dokumentiert.
- D14 (Schritt-6 deferred, Claude×Grok, alle med/low): pipeline G3 (printability verwirft gefundene Blocker bei
  GeometryError — enger als gedacht, braucht Blocker-Geometrie-Fixture → Printability-Slice) + G4 (physics_failed
  vor physics_incomplete reordern — NICHT erreichbar: gaps↔questions 1:1 gekoppelt, needs_clarification feuert zuerst).
  refinement G5 (converged vertraut result.passed ohne `not failures` — defensiv gg. malformed GateResult).
- D15 (Schritt-6 deferred, Claude×Grok): grounding_integrity (Alias-ID-Kanonisierung für Zirkularität, body-vs-map-
  Bijection, vakuöse independent_rate/coverage bei Nenner 0). **geometry_verification NICHT in pipeline verdrahtet
  trotz README §6** → entweder verdrahten ODER README-Claim entschärfen; VOR dem Verdrahten: non-exact Volume-Untergrenze
  + Extent-Containment-statt-isclose für konservative AABBs (Rotation) + Volume()/BoundingBox()-Guards. clarification
  G2/G4 (NaN-Answer schon fail-loud; unneeded-measurand-Fold) — low.
  evaluation: per-gate leak-breakdown + jeder unsound-Case soll für seinen GELABELTEN C-Code scheitern.
- D11: Audit-Log-Lücken (Grok, low, A5): scout._queries + skeptic._judge schlucken LLM/Parse-Fehler ohne log
  (best-effort, kein Fabrication-Risiko, aber schwer reproduzierbar) — state.log threaden. Auch: skeptic.claim.verification
  nur aus Primary-Verifier → bei extra_judges/Panel fehlen Second/Extra-Quellen in der Audit-Spur (Union dedup-by-URL).
- D12 (→ ergänzt D7): inter-judge Familien-Dedup (verifier≠second≠extra) im Skeptic/consensus fehlt (nur vs. Generator
  geprüft) — Grok korrobiert das frühere consensus-Finding. Auch: independence nur exakte-URL (Mirror/CDN-Dupes), Canonical/
  content_hash-Dedup gegen Scholar-Quellen.
- D13 (cross-cutting synthesizer+forge, Claude×Grok-einig, aus dem agents-Review deferred — bewusst NICHT piecemeal
  gefixt, um Schwester-Divergenz zu vermeiden): (a) `approach_id`/`possibility_id` hashen nur (name/statement, sorted
  grounding) und ignorieren das Sekundärfeld (tradeoffs/mechanism) → zwei Zeilen, die sich nur darin unterscheiden,
  kollidieren und die zweite wird (geloggt) gedroppt — Sekundärfeld in den Survivor mergen oder in den id-Key
  aufnehmen. (b) kein Cap auf geparste approaches/possibilities (Output ist token-bounded → niedriges Risiko, aber
  konsistent mit conductors `_MAX_SUB_QUESTIONS`). (c) grounding-ids vor id/emit nicht dedupliziert (`c1|c1` vs `c1`
  schwächt Dedup). (d) non-dict-Array-Elemente in `_cluster`/`_open` still gefiltert (Count-Log fehlt für Audit).
  Architect-spezifisch deferred: `_SYSTEM`-Schema listet sourcing/domain/site/material_density/tool/torque_quantity_id
  nicht, die Parser aber akzeptieren (owner: Live-Prompt-Änderung → Live-Remeasure) + per-Feld-Array-Caps (DoS, token-bounded).
  **→ ERLEDIGT 2026-07-04 (a-d), symmetrisch in synthesizer+forge:** (a) **Merge-Variante** — Sekundärfeld des Duplikats
  in den Survivor gemergt (synthesizer: tradeoffs-Union in first-seen-Order; forge: mechanism per `"; "` dedupliziert
  angehängt), geloggt; id-Key bewusst UNVERÄNDERT, damit bestehende ids/Checkpoints reproduzierbar bleiben (Prinzip 5;
  kein Test/Checkpoint assertet auf Hash-ids, aber Key-Erweiterung hätte alle künftigen Replays alter Läufe divergieren
  lassen). (b) `_MAX_APPROACHES`/`_MAX_POSSIBILITIES` = 10 (== `conductor._MAX_SUB_QUESTIONS`), Überschuss geloggt
  gekappt. (c) grounding (+ synthesizer-tradeoffs) vor id/emit `_dedup` (order-preserving, first occurrence,
  deterministisch). (d) non-dict-Filter aus `_cluster`/`_open` nach `run()` gezogen mit Count-Log
  (`skipped N non-dict array element(s)`). 8 neue Tests + 1 auf Merge angepasst (test_synthesizer.py/test_forge.py),
  Suite 1736/0/61, ruff clean.
  **Architect-Teil (`_SYSTEM`-Schema + per-Feld-Array-Caps) bleibt OFFEN (owner-gated).**
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
- D8: tools/ SSRF-Tiefe (Grok #1-IP/#2, deferred — Scheme-Allowlist bereits gefixt): IP-Pinning gegen loopback/RFC1918/
  link-local (169.254.169.254) + per-Redirect-Hop-Revalidierung via custom urllib-Opener. Bewusst NICHT halb gebaut
  (DNS-Auflösung/IPv6/DNS-Rebinding brauchen Design + evtl. config-Allow/Deny; halbe SSRF-Defense = falsche Sicherheit).
- D9: tools/fetch.py final_url-Provenienz (Grok #7): bei Redirect kommt der content von resp.final_url, aber FetchResult.url
  + Ledger führen die Original-Kandidaten-URL → Audit/Repro-Drift. Fix berührt FetchResult-Shape + Ledger + SourceRef.
- D10: tools/arxiv_backend.py XXE/billion-laughs (Grok #9, low): ET.fromstring nicht gehärtet. Risiko niedrig (trusted Host
  export.arxiv.org + https); defusedxml widerspricht minimal-deps-Philosophie. Revisit, falls untrusted-XML-Quelle dazukommt.
  Auch low: limit-clamp (≤25) an Backend-Eingang; Content-Type text/* erzwingen statt lossy errors="replace"-Hash auf Binär.

## Next
- **TEIL 2 läuft: CAD-Fertigungs-Stubs real bauen** (Drift-Rec #5, `docs/DOC_CODE_DRIFT.md` §6/§8):
  - [x] **Stein 1 CNC-DFM (2026-06-17)**: quellenlosen CNC-Stub → echte belegte Regeln (Wand/Envelope/Material/
    Toleranz), erfundene Zahlen (`min_feature_mm`/`typical_tol`) raus, Vacuous-Pass raus (Gaps statt stillem
    `printable=True`). `dfm.py`-Konstanten + `cnc_geometric_gaps()` + `ProcessDFM.gaps`/`AdvancedDFMReport.total_gaps`.
    Grok-Cross-Model 2 Runden + Konvergenz (0 STILL/0 NEW). 4 neue Tests, volle Suite 1208 grün. BUILD_LOG dokumentiert.
  - [x] **Stein 2 Laser/Sheet-DFM (2026-06-17)**: quellenlosen Laser-Stub → echte Sheet-Regeln (Dicke=min(bbox)
    real geprüft; Dual-Threshold Industrie-Obergrenze 25mm-Issue vs. Shop-Cap 12.7mm-Gap; Form/Feature/Bridging/
    Kerf als Gaps). `dfm.py`-Laser-Konstanten + `laser_sheet_gaps()`. Grok 2 Runden + Bestätigung (0 STILL/0 NEW),
    SendCutSend-Dicke selbst verifiziert. 3 neue Tests (inkl. no-silent-band), volle Suite 1211 grün. BUILD_LOG dok.
  - [x] **Stein 3 PCB-DFM (2026-06-18)**: ehrlichster Stein — ein PCB ist ein 2D-Kupfer-Layout, der `BuildArtifact`
    ein Solid OHNE Kupfer-Geometrie → ALLE Fertiger-Regeln Gaps, `printable=False` (nie zertifizierbar). Erfundene
    `trace_min_mm:0.2`/`via_min:0.3` + rückwärtige Namens-Logik raus. `dfm.py`: gequellte JLCPCB/IPC-2221-Konstanten +
    echtes `ipc2221_trace_width_mm()` (gg. Standardwert getestet) + `pcb_dfm_gaps()`; Referenz-Caps NESTED + `evaluated:False`.
    Grok 3 Runden (6+3+1 Lücken, je gg. JLCPCB selbst verifiziert), 2 neue Tests, volle Suite 1213 grün. BUILD_LOG dok.
  - [x] **Stein 4 Kostenmodell (2026-06-18)**: Kosten-Stubs (`"~5-12 EUR"`/`"8-25 EUR"`) → echtes bereich-basiertes
    Modell `cad/cost_model.py` (NEU): `CostEstimate` + `estimate_fdm_cost()` (Material aus Volumen×Dichte×Infill;
    Maschinenzeit/Job-Average-Durchsatz×Rate excl. Material; Setup-Band) + per-Material gequellte Bänder. Bereich
    statt Punkt; Annahmen+Gaps explizit (Shell-dominiert/Commercial/Material-Default geflaggt). Report trägt
    strukturiertes `cost_estimate`; FDM-`cost_hint`+`cost_model_stub` echt. Grok 3 Runden (9+3 Lücken), 5+1 Tests,
    volle Suite 1219 grün. Nur FDM berechnet; CNC/Laser/PCB ehrlicher Cost-Gap. BUILD_LOG dok.
    Naht-Follow-up: `fertigungs.py:KostenModell` (String-Prosa) soll `CostEstimate` konsumieren.
    **→ ERLEDIGT 2026-07-04:** `_structured_cost_from_dfm` konsumiert `AdvancedDFMReport.cost_estimate`
    (Material-/Maschinenzeit-/Setup-Bänder einzeln, `summary()` als gesamt_est, Gap-Anzahl deklariert);
    Prosa-`cost_hint` bleibt ehrlicher Fallback für ältere Reports. +1 Test (TDD, erst rot). Suite 1728/0/61.
  - [x] **Stein 5 G-Code (2026-06-18)**: `datei_stub`-Prosa → echte VERIFIZIERTE G-Code-Generierung `cad/gcode.py`
    (NEU): `generate_profile_gcode()` (2,5D-Außenkontur RS-274/ISO 6983, Tool-Radius-Offset explizit, Stepdown,
    fail-loud) + `verify_gcode()` als Gate (Units/Spindel+S/Feed-F/Gouge-lateral+Rapid-Z/Retract-vor-M5/Bounds).
    Report trägt verifiziertes `gcode_program` (echte bbox); fertigungs-`datei_stub` ehrlich (FDM-Print=Slicer-Gap).
    Verifier NON-VACUOUS (bewiesen). Grok 3 Runden (10+2 Lücken, eigene Regression selbst gefangen), 6+1 Tests,
    volle Suite 1226 grün. Nur 2,5D-Kontur; Pockets/3D/Slicing = Gaps. BUILD_LOG dok.
  - [x] **Stein 6 KiCad-Adapter (2026-06-18, letzter)**: `generate_kicad_schematic_stub` (droppte `[:8]` still,
    alle `(at 0 0 0)` überlappend, alle als „R") → echter VERIFIZIERTER Export `cad/kicad.py` (NEU): `to_kicad_netlist()`
    (komplette valide `.net`, bare `(code N)`, escaped) + `to_kicad_schematic()` (ehrliches Skeleton: alle Komponenten
    grid + global_labels) + `verify_*()` als **Gate** (electronics-Wrapper raisen on !ok). Verifier NON-VACUOUS
    (Dropped/Dangling/Floating/malformed/Overlap/Truncation gefangen, escape-aware). Grok 2 Runden (viele Lücken,
    eigenen Regex-Tupel-Bug gefangen), 8 Tests, volle Suite 1234 grün. Netliste=Import-Pfad; grafischer Schaltplan=Gap.
    **TEIL 2 KOMPLETT** (alle 6 Steine echt+verifiziert+gequellt). BUILD_LOG dok.
  - Nebenfund (Stein 6, DEFERRED): `electronics.py:export_placement_to_kicad_pcb` hat eigene Bugs (rot_deg-Tupel statt
    Skalar, legacy `(module)`-Syntax statt `(footprint)`, kein `_esc`, `zip`-by-order-Truncation) — separate PCB-Export-
    Funktion, ungegatet → eigener Follow-up (kann `cad/kicad.py`-Härtung + Verifier-Muster nutzen).
    **→ WAR SCHON ERLEDIGT (verifiziert 2026-07-04):** `cad/kicad.py:to_kicad_pcb` behebt alle 4 Bugs
    (rot_deg-Tupel→Skalar Z.260, modernes `(footprint)`, `_esc`, ref_des-Auflösung statt zip) und
    `export_placement_to_kicad_pcb` ist via `verify_kicad_pcb` als Gate verdrahtet (raise on !ok).
  - Nebenfund (Stein 3): `electronics.py:run_internal_drc` nutzt unbelegte Magic-Numbers (`trace_a_per_mm2=12.0`
    Harness-Draht-Stromdichte ≠ PCB-Trace, `min_clearance_mm=0.8`, `max_power_density=2.5`, hardcodierte Board-Fläche
    150cm²) — tiefe Elektronik-DRC, bewusst nicht in Stein 3 angefasst → Review-Schritt 7-9 (electronics/circuit).
  - Nebenfund: FDM-`hole_hint=3.0` ist ein Fake-Input (separater kleiner Fix).
    **→ WAR SCHON ERLEDIGT (verifiziert 2026-07-04):** `manufacturing_check.py:224-231` deklariert die
    min-hole-Regel ehrlich als „not evaluable" (Spec trägt keine Loch-Geometrie) statt der fabrizierten
    3.0-mm-Bohrung, die immer bestand. Kein Code-Change nötig, nur dieser Queue-Eintrag war stale.
- Review-Kampagne **Schritt 7-9 offen** (Reihenfolge oben): physics_validation + 27 Validatoren + fem*/modal/dfm/
  orientation/mesh_integrity/brep/circuit → export/+costing+completeness+software → pipelines/+integration/+grenzverschiebung/.
- Deferred Findings aus Schritt 6: D14 (pipeline/refinement), D15 (grounding/geometry — geometry_verification NICHT
  verdrahtet), D16 (goldset/telemetry/calibration/ratification Tails) — je in den Commit-Messages dokumentiert.

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
