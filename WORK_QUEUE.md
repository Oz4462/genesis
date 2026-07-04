# WORK QUEUE — GENESIS

> Voller Kontext: `docs/integration/SESSION_HANDOFF.md`. Stand 2026-07-04: Arbeit auf `main`
> (lokal, 40+ Commits vor origin, KEIN Push ohne Owner); Humanoid TP1/TP2 im Worktree-Branch
> `worktree-claude-orchestrator` (unmerged). Suite: 1736 passed / 0 failed / 61 skipped.
> (Der frühere Branch `feat/app-integration-phase0-2` ist in main aufgegangen.)

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
  Bijection, vakuöse independent_rate/coverage bei Nenner 0). **geometry_verification-Teil → ERLEDIGT 2026-07-04** (P7):
  alle 3 Härtungen gebaut (non-exact Volume-Untergrenze `Volume.lower` mit Beweisskizzen; `Aabb.exact`-Flag +
  Extent-Containment-statt-isclose für konservative AABBs/Rotation; isValid/Volume/BoundingBox-Guards → GeometryError)
  UND in `pipeline.assess_specification` verdrahtet (`geometry_status` verified/failed/unavailable/no_geometry,
  `failed` → `overall="geometry_failed"`; cadquery-fehlt = ehrlicher Skip, sichtbar in CLI-Footer/assess/Web-Dict).
  Tests: test_geometry.py (+13 Schranken/Exaktheit), test_geometry_verification_hardening.py (neu, läuft OHNE
  cadquery via Stub-Solid), test_pipeline.py (+4 Verdrahtung). clarification
  G2/G4 (NaN-Answer schon fail-loud; unneeded-measurand-Fold) — low, bleibt offen.
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
  **→ ERLEDIGT 2026-07-04:** zwei Schichten in `tools/http.py`+`tools/fetch.py`: (1) syntaktischer Guard
  `ssrf_host_block_reason` (kein DNS; Literal-IPs loopback/RFC1918/link-local inkl. 169.254.169.254/0.0.0.0/::1/
  ULA fc00::/7/multicast/reserved + `localhost`, IPv4-mapped IPv6 entpackt) im WebFetchTool VOR jedem Transport →
  ehrliches `ok=False` mit Grund, ledger-sichtbar; (2) im Default-Transport `_resolved_ssrf_block_reason`
  (getaddrinfo: ALLE aufgelösten Adressen müssen public sein, eine private blockt) + `_redirect_handler`
  (custom `HTTPRedirectHandler`: JEDER Hop Scheme-Allowlist + resolved-Check). Operator-Opt-in
  `allow_private_hosts=True` nur am Transport (Research-Pfad setzt es nie); Ollama-LLM/Embedder-Pfad
  (eigene Transporte, operator-config base_url) bewusst UNVERÄNDERT. Restrisiko: TOCTOU-DNS-Rebinding
  (Check-Resolve ≠ Connect-Resolve) bleibt — echter Fix wäre Connect-per-IP-Pinning, notiert.
- D9: tools/fetch.py final_url-Provenienz (Grok #7): bei Redirect kommt der content von resp.final_url, aber FetchResult.url
  + Ledger führen die Original-Kandidaten-URL → Audit/Repro-Drift. Fix berührt FetchResult-Shape + Ledger + SourceRef.
  **→ ERLEDIGT 2026-07-04:** `FetchResult.url` = echte finale URL (`resp.final_url`); Ledger-`record_fetch` und
  `to_source_ref` zitieren damit die reale Provenienz; neues Feld `requested_url` bewahrt bei Redirect die
  ursprünglich angefragte URL für den Audit-Trail (None ohne Redirect → kein Shape-Rauschen). Finale URL wird
  zusätzlich revalidiert (Scheme + SSRF-Guard, Defense-in-depth für injizierte Transporte ohne Hop-Guard).
- D10: tools/arxiv_backend.py XXE/billion-laughs (Grok #9, low): ET.fromstring nicht gehärtet. Risiko niedrig (trusted Host
  export.arxiv.org + https); defusedxml widerspricht minimal-deps-Philosophie. Revisit, falls untrusted-XML-Quelle dazukommt.
  Auch low: limit-clamp (≤25) an Backend-Eingang; Content-Type text/* erzwingen statt lossy errors="replace"-Hash auf Binär.
  **→ ERLEDIGT 2026-07-04 (XXE-Teil):** DTD-Vorab-Check ohne neue Dependency (defusedxml-Muster): jedes
  `<!DOCTYPE`/`<!ENTITY` im Body → lauter `SearchBackendError` BEVOR expat parst (kein Expansion-Hang, kein
  External-Entity-Fetch; legitimes arXiv-Atom trägt nie eine DTD); Größen-Cap existiert via Transport
  `max_bytes=5MB`; undeklarierte Entity-Referenz bleibt lauter ParseError. Tests: billion-laughs + XXE +
  lowercase-doctype. Die zwei „auch low"-Punkte (limit-clamp ≤25, Content-Type text/*) bleiben OFFEN.

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
- Deferred Findings aus Schritt 6: D14 (pipeline/refinement), D15 (grounding/geometry — geometry_verification-Teil
  ERLEDIGT 2026-07-04, Rest offen), D16 (goldset/telemetry/calibration/ratification Tails) — je in den Commit-Messages dokumentiert.

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

## Schritt 7 (Review-Kampagne) — Fortschritt 2026-07-04
- physics_validation.py + fatigue.py — DONE (Claude-Tiefenreview, 8 Findings F1-F8; Grok-CLI-Outage
  [2x Timeout], Cross-Review NACHZUHOLEN wie beim Klassifizierer-Outage-Präzedenzfall):
  · F1/F6 HIGH GEFIXT: NaN/Inf → stiller Grün-Pass in isru/life/vacuum (NaN passiert jeden <=-Guard);
    zentrale Finite-Schranke in run_physics_checks (non-finite Input → PHYSICS_CHECK_ERROR) +
    Defense-in-depth-isfinite-Guards in den 3 Inline-Validatoren.
  · F2 HIGH GEFIXT (Guard-Variante): 7/43 Validatoren ohne Recipe (bolted_joint, contact, creep,
    fracture, overtemperature, plate_bending, thermal_mismatch) → MANUAL_ONLY_VALIDATORS-Whitelist
    (physics_selection) + Registry-Test der stille Unterabdeckung ab jetzt hart fängt; ehrliche
    Recipes für die 7 = eigener Follow-up (Measurand-Konventionen fehlen; TP2-Spec bestätigt
    "fehlende ehrliche Eingangsdaten" für fracture/creep/thermal_mismatch). ACHTUNG Merge: TP1
    (Worktree) hat overtemperature-Recipe → Eintrag dort aus Whitelist nehmen.
  · F3 MED GEFIXT: negative stress_amplitude → ValueError in goodman/soderberg/gerber_safety_factor
    (war: safety_factor=inf, ok=True, "infinite life" aus Vorzeichenfehler).
  · F5 MED GEFIXT: non-dict-Validator-Result crashte den Batch außerhalb try (Doc-Truth-Bruch) →
    status=error für DEN Check, Batch läuft weiter.
  · F7/F8 LOW GEFIXT: fabrizierte safety_factor 1.0/0.0 bei Pass-ohne-Target → None (ehrlich "kein
    Margin"); Fail-Detail "no margin reported" statt "safety_factor=None".
  · DEFENDED bestätigt: vakuöser Leer-Checklisten-Pass, designed-sink-Bypass, Gate-Aggregation CLEAN.
  · +8 Tests (TDD). Suite 1799/0/61, ruff clean.
- physics_selection.py + verification/units.py — DONE (Claude-Review; Grok nachzuholen), alle 4 GEFIXT:
  · S-F2 MED: optional_inputs — deklarierte-aber-unauflösbare Größe wurde still 0.0 (genullte Dosis
    → dose_ok=True); jetzt Gap wie Pflicht-Input, nur echt-abwesend defaultet 0.0. Doc-Truth repariert.
  · S-F6: Sv/Gy als EIGENE Basisdimensionen in _KNOWN_UNITS (bewusst nicht J/kg, kein Sv↔Gy-Laundering);
    mSv/µSv/kGy lösen jetzt über den Prefix-Zweig auf (mSv→Sv Faktor 1e-3 getestet).
  · S-F1 MED (konservative Variante): Trigger fehlt, aber ALLE übrigen Input-Measurands (≥2) deklariert
    → ehrlicher Mis-Tag-Gap statt lautlosem Verschwinden; Teil-Präsenz bleibt bewusst still
    (kein Gap-Spam aus geteilten material.*-Measurands).
  · S-F3: evaluate_spec_physics liefert honest_pass = gate.passed AND not gaps (der sichere Wert
    ist jetzt der bequemste; pipeline/evaluation kombinierten schon so).
  · CLEAN bestätigt: _resolve-Gaps, Determinismus, Registry 38/38, Signaturen, first-wins (C-17).
  · +7 Tests (TDD). Suite 1806/0/61, ruff clean.
- fem.py+fem3d.py+fem3d_quadratic.py+bracket_fem.py(+plate_hole) — DONE (Batch 2 FEM-Schicht):
  · F1 MED GEFIXT: FEM-Engines validierten Endlichkeit nicht — NaN/Inf in E/ν/inertia/force
    propagierte still zu NaN-Ergebnissen (tip_deflection, peak_vm; NaN passiert jeden Vergleichs-
    Guard als False). Konvention konsistent zu buckling/modal: ungültige EINGABEN → ValueError
    (fail-loud, inkl. ν∉(−1,0.5)-Schranke gegen singuläre D-Matrix); non-finite LÖSUNG nach dem
    Solve → GeometryError (degenerierte Struktur). Geteilte Guards _check_material_and_bcs/
    _check_solution_finite in fem3d, wiederverwendet von fem3d_quadratic; bracket_fem-Guard feuert
    VOR _require_gmsh (fehlendes gmsh maskiert keinen Input-Fehler); von_mises wirft bei
    non-finite Stress.
  · F2 LOW GEFIXT (Doc-Truth): „4-Punkt-Gauss exakt" gilt nur für geradkantige (affine) Tets —
    Modulkopf + t10_stiffness-Docstring auf t10_mass-Ehrlichkeitsniveau angeglichen.
  · F3 LOW GEFIXT: plate_hole._read_kt — leere Fernfeld-Maske → np.mean([])=NaN → stiller NaN-Kt;
    jetzt GeometryError bei leerer Maske und bei σ_far=0/non-finite.
  · F4 LOW NICHT ANGEFASST (wie vorgegeben): test_bracket_fem.py-Float-Gleichheits-Determinismus
    skippt in dieser Umgebung (gmsh fehlt) — ohne Lauf keine ehrliche Änderung möglich.
  · DEFENDED bestätigt (Review): Element-Mathematik verifiziert (Patch-Test, Kirsch/Howland-Kt,
    Maschinengenauigkeits-Abgleich gegen closed form), degenerierte Elemente fail-loud, BCs korrekt
    (Elimination, penalty-frei), kein Exception-Schlucken.
  · +20 Tests (TDD, tests/test_step7_fem_hardening.py, stub-basiert ohne gmsh). Suite (ohne die
    parallel in Arbeit befindlichen circuit/mesh_integrity/brep-Dateien) 1812/0/59, ruff clean.
- mesh_integrity+brep+circuit — DONE (Batch 2, Claude-Tiefenreview 2026-07-04):
  · M1 MED GEFIXT: STL-Parser akzeptierte nan/inf/1e999-Vertices — +inf konnte volume_positive=True
    liefern bei Müll-chi/genus; jetzt math.isfinite über alle Komponenten in _triangles → ValueError.
  · M2 Doc-Truth GEFIXT: Modul-Doc behauptete „chi odd OR exceeds 2 per shell wird geflaggt" — Code
    flaggt nur ungerades chi; Doc ehrlich korrigiert (chi>2 = Summe über Shells, unterdrückt nur
    genus, wird berichtet, nicht geflaggt). Shell-Zerlegung bewusst NICHT gebaut.
  · M3 LOW: 1e-15-Degeneriertheits-Schwelle mit mm-Welt-Begründung kommentiert (|u×v|=2·Fläche, echte
    Degeneriertheit = exakt 0.0; ehrliche Grenze dokumentiert: nicht einheitsagnostisch).
  · B1/B2/B4/B7 GEFIXT: brep.py hält jetzt seinen GeometryError-Kontrakt — fehlender params-Key
    (_param statt roher KeyError), nicht-positive/non-finite Primitivmaße (_positive je box/cylinder/
    sphere-Maß; Defense-in-depth — Quantity-Root-Guard fängt non-finite schon upstream), Transform
    ohne Kind (war IndexError), NaN-Rotationsachse (passierte den <1e-12-Guard, NaN-Vergleich=False).
  · B3 MED GEFIXT (sichere Richtung): interferes meldete Kernel-Fehler als „keine Kollision"
    (except→return False); jetzt: nur echte Null-Shape-Schnittmenge = False, boolesche/Volumen-Fehler
    → GeometryError. „Kollisionscheck crashte" liest sich nie mehr als „keine Kollision".
  · B6 LOW: Kugel-Volumen-Regressionstest gegen 4/3·π·r³ (makeSphere-Winkelargumente jetzt gepinnt;
    skippt ohne cadquery, läuft in Full-Dep-Umgebungen).
  · C1 MED GEFIXT (fail-loud-Variante): Duplikat-Quellennamen (auch 2× Default "V") überschrieben
    source_i still → ValueError; f"V{k}"-Fallback nur für leeren Namen (jetzt getestet-live).
    Begründung: alle realen Aufrufer (Tests, electronics.py BAT48) nutzen explizite eindeutige
    Namen — Index-Keying hätte deren API gebrochen, fail-loud bricht keinen korrekten Aufrufer.
  · C2 MED GEFIXT: ohms=0 war ZeroDivisionError, negative/NaN ohms/farads/henries wurden still
    gestempelt, dt<=0/NaN crashte → _positive_value an allen Stempeln (solve_dc, solve_ac,
    solve_transient inkl. dt>0- und t_end>=0-Guard); Docstrings deklarieren die ValueErrors.
  · C4 LOW: solve_dc_nonlinear max(..., default=0.0) — Diode Ground→Ground (0 unbekannte Knoten)
    konvergiert trivial statt max()-ValueError; Kommentar-Drift korrigiert (Knoten-Konvergenz
    impliziert Junction-Konvergenz, Vd ist Differenz zweier Knotenspannungen).
  · C5 LOW: solve_ac omega=0 mit L war ZeroDivision → klarer ValueError (+ omega finite/>=0 generell).
  · C3 Doc-Truth: solve_dc([]) als vakuös deklariert (als Solver korrekt-leer, als Gate kein Beweis;
    Caller muss Nicht-Leere selbst prüfen) + Test pinnt das Verhalten.
  · DEFENDED nicht angefasst: THERMAL_VOLTAGE, MNA-Stempelung, _pnjlim; mesh_integrity-Kernmathematik
    (Euler–Poincaré, Divergenzsatz, gerichtete Kanten) unverändert.
  · +23 Test-Items (TDD, 19 davon erst rot: 1 mesh, 8 circuit, 13 brep-Stub-Items in
    tests/test_step7_brep_hardening.py nach test_step7_hardening.py-Muster + 1 kernel-gebundener
    in test_brep.py). Suite 1853/0/61, ruff clean.
- Schritt 8: costing+completeness+software — DONE (Claude-Review-Findings gefixt, TDD, 3 Commits):
  · C-1 HOCH GEFIXT: Filament-geschätzte (gedruckte) Teile zählten unmarkiert in complete=True —
    Cost jetzt mit estimated_count/fabricated_estimated + fully_grounded (Beweis-Ebene: NUR belegte
    Kaufpreise); complete = "jede Position erfasst: belegt ODER explizit Schätzung". Konsumenten
    nachgezogen: format_cost labelt "geschätzt aus Filament (Schätzung, kein belegter Preis)",
    bundle schreibt cost_fully_grounded/cost_estimated_parts/cost_notes (bom.json+MANIFEST) und
    MISSING.md bekommt die Sektion "Geschätzte Preise"; pipeline/seams dokumentieren: COST_ROLLUP-
    Seam beweist arithmetische Kopplung, nicht Preis-Erdung.
  · C-2 MITTEL GEFIXT: bom_cost summierte jeden Preis-Origin trotz GROUNDED-Versprechen (C-16) —
    nur ValueOrigin.GROUNDED zählt; andere Origins → unpriced + ehrliche Notiz (Cost.notes).
    DECISION-Filamentpreis bleibt zulässig (Position ist ohnehin Schätzung).
  · C-3 NIEDRIG GEFIXT: negative BomItem.count rechnete Positionen weg → geflaggt, nie verrechnet.
  · K-1 HOCH GEFIXT: leerer-Spec-Blindfleck (rein negativer Kritiker ⇒ [] ⇒ "vollständig") —
    3 Positiv-Untergrenzen als weiche deutsche Warnungen (keine Schritte / keine Stückliste /
    erzeugt kein Artefakt); Demo-Welten geprüft: capstone weiter 0 Warnungen.
  · K-2 MITTEL GEFIXT: per Measurand konsumierte Filamentpreis-Größe war falscher Orphan —
    Measurand-Konsum in der Referenzmenge (Import aus costing, kein Zyklus).
  · K-3 NIEDRIG: doppelter Drift-Wächter (Regex-Pin der quantity-id-Felder in core/state.py +
    Funktionaltest über alle Referenzkanäle). K-4 NIEDRIG: except Exception → FormulaError.
  · S-1 HOCH GEFIXT (Anti-Halluzination): erfundene "Elektriker/Techniker/DFM/Lern"-Provenienz aus
    quelle/Docstring entfernt → "PLAN §4 Kanon-Vorlage, kein Prior konsumiert (Lücke: echte
    Prior-Auswertung)"; ingenieur-Parameter bleibt (API), als reserviert deklariert, KEINE
    Schein-Auswertung. S-2 MITTEL: "flug"-Substring → Wortgrenzen-Regex (Ausflug/Flughafen matchen
    nicht mehr; Drohne bewusst nicht aufgenommen). S-3 MITTEL: Jetpack-Kanon deklariert
    "Kanon-Annahmen (aus keinem Prior abgeleitet)". Beifang: trailing comma machte update_pfad
    zum 1-Tupel statt UpdatePfad — gefixt + Typ-Pin.
  · DEFENDED nicht angefasst: Währungstrennung/kein FX, NaN-Schutz via Quantity, Determinismus
    (costing); Warnungs-statt-Gate-Semantik (completeness); Generic-Fallback-Gaps (software);
    src/gen/export/ (paralleler Review) unberührt.
  · +19 Tests (TDD: 5 costing + 1 bundle + 7 completeness + 4 software rot vor dem Fix, Rest
    Pins/Wächter). Suite 1871/0/61, ruff clean. Commits 5fade13 / 2be78f9 / 5ad4e70.
- Schritt 8: export/ — DONE (Claude-Review-Findings gefixt, TDD, 2 Commits):
  · F1 MITTEL GEFIXT (Injection): mehrzeilige spec.idea/comp.name brachen aus //-/#-Kommentaren
    und Markdown-Headings aus (nicht-öffnendes .scad, nicht kompilierendes .py) — zentraler Helfer
    export/_text.py (single_line/md_cell, reine Display-Sanitisierung, Zitat-Pfade C-4 laufen NIE
    hindurch) an allen Stellen in openscad/build123d/assembly/markdown; b123d-Output per compile()
    bewiesen.
  · F2 MITTEL GEFIXT (Markdown-Korruption): | und Newlines in name/rationale/formula/action/reason
    sprengten Tabellen — md_cell (| → \|, Newline → Leerzeichen) an allen Zellwerten; Spaltenzahl-
    Invariante (6 Separatoren) getestet.
  · F3 MITTEL GEFIXT (Single-Source + Genauigkeit): markdown.py umging fmt_number mit inline :g;
    :g rundete auf 6 signifikante Stellen → sichtbare Backend-Divergenz. Alles über
    numfmt.fmt_number geroutet, Präzision .12g (double fast verlustfrei, locale-frei); numfmt-
    Docstring dokumentiert Display-Rundung + bewusste Ausnahmen (stl.py %.9g = eigener Mesh-
    Kontrakt, unberührt; Zitate C-4 byte-genau, nie durch den Formatter). 6-Stellen-Pins in
    test_markdown.py nach Intentions-Prüfung nachgezogen.
  · F4 GEFIXT (Overlap-Overclaim): openscad._footprint ignorierte interne translate/rotate — der
    PARTS-TRAY konnte real überlappen. Footprint jetzt aus der sounden analytischen AABB
    (verification.geometry.aabb_of) + Zentrums-Kompensation → Hüllen paarweise disjunkt per
    Konstruktion (Gegenbeispiel inner-translate=Pitch als Test).
  · F5 GEFIXT: assembly._bbox_dims kannte nur box — cylinder/sphere-Teile fielen still aus dem
    Assembly-PNG. Jetzt cylinder (2r,2r,h) / sphere (2r,2r,2r); nicht ableitbare Teile werden im
    Bild-Titel benannt statt verschluckt.
  · F6 GEFIXT (Skip-Konflation): specification_to_stl verschluckte JEDEN ExportError als Boolean-
    Skip. API-Entscheidung (einziger Aufrufer cli.render_spec; STL hat keine Kommentar-Syntax):
    CsgBooleanRefusal(ExportError) als markierte erwartete Verweigerung + neues
    specification_to_stl_report → (stl, skipped: id→Grund); echte Fehler propagieren laut;
    specification_to_stl bleibt str-Wrapper (API-kompatibel). CLI verweigert Teil-STL ehrlich.
  · F7 GEFIXT: _triangles_to_stl filtert Nullflächen-Facetten (<1e-15, identisch brep_stl) und
    wirft bei leerem Rest; CLI-Primitiv-Fallback läuft durch dasselbe stl_integrity_check-Gate
    wie der Kernel-Pfad (verweigern statt liefern bei !ok).
  · F8 bewusst NICHT gefixt (skopiert): Ein-Solid-Fusion in specification_to_brep_stl — Docstring
    erklärt den Kontrakt bereits explizit inkl. per-Part-Alternative; kein Zusatz nötig.
  · DEFENDED nicht angefasst: state.py-NaN-Guard, mesh_integrity-Gates der OCCT-Pfade,
    Identifier-Sanitisierung (_module_name/_safe_name), _origin-Provenienz, δ-Neuberechnung im
    Markdown, bundle-Fehlerprotokollierung, brep_stl-%.6e/Degenerate-Filter.
  · +24 Tests in tests/test_step8_export_hardening.py (TDD: 12 + 9 rot vor dem Fix, Rest Pins).
    Suite 1895/0/61, ruff clean. Commits 0d44a1b / 6917343.
- Schritt 9: integration+memory+web — DONE (Claude-Review-Findings gefixt, TDD, 2 Commits):
  · #1 MED GEFIXT (Ehrlichkeit, Recall-Vorfilter): audited_run(recall=True) konnte in der
    komponierten Form NIE feuern (Library abstiniert bis min_calibration=30, add_calibration
    wurde in integration/ nirgends gerufen) und ein leeres reused_facts sah aus wie „nichts
    gefunden". Jetzt: AuditedRunResult.recall_status ("disabled"|"uncalibrated"|"no_match"|
    "hit") macht die Abstention sichtbar; Docstring + PHASE_L2_RECALL_DRIFT.md nennen die
    Vorbedingung explizit (Aufrufer kalibriert separat, audited_run kalibriert nie). NEU
    tests/test_audited_run_recall.py fährt recall=True auf manuell gewarmter Library
    END-ZU-END zu einem echten Hit (Provenance + claim_id-Rückverweis bewiesen) + Negativtests
    uncalibrated/no_match. Dafür audit-Import in audited_run lazy gemacht: Memory-only-
    Komposition bleibt numpy-only/testbar OHNE verify-Extra; fail-loud der Audit-Naht bleibt
    exakt dort erhalten, wo keystore+key gegeben sind (eigener Negativtest ImportError).
  · #2 LOW GEFIXT (Härtung, web): POST /api/research/assess ließ HTTP-Body-Strings direkt in
    sympify (eval-basiert). Jetzt VOR dem Parsen: Längenschranke _MAX_EXPR_LEN=500 → 400,
    Dunder-Token-Sperre ('__' = klassische sympify-Attribut-Ketten-Flucht) → 400, und
    parse_expr(evaluate=False) statt sympify (keine Arithmetik/Power-Tower-Auswertung im
    Web-Layer; nur freie Symbolnamen werden gebraucht — assess_identity/-inequality parsen
    selbst gegen die Manifest-Symbole). Loopback-Bindung (web/__main__.py, 127.0.0.1) als
    primäre Milderung im Kommentar dokumentiert. Paritätstest: valide Ausdrücke verhalten
    sich identisch (sin²+cos²=1 → gleiche variables + Verdikt); bestehende 400-Tests grün.
  · #3 LOW GEFIXT (Dedupe): VerifiedFactsLibrary.remember() deduplziert jetzt gegen vorhandene
    capture_id (Prüfung in verified_facts.py via store.list_steps_for_trace — vendored storage
    UNVERÄNDERT) + Intra-Call-seen-Set; zweimal remember(gleicher Claim) → genau ein Step,
    kein Recall-Rauschen durch identische Nachbarn. Der e2e-Recall-Test beweist zusätzlich
    n_remembered==0 beim reproduzierten Lauf (gleiche run_id → gleiche capture_id).
  · DEFENDED nicht angefasst: audit-Naht fail-loud (per Negativtest sogar gepinnt), drift,
    identity_research_hook, Lazy-Exports (PEP-562-Getattr unverändert), web-Escaping/Gating,
    kein NaN-Guard-Leck; vendored anamnesis_mem nur an der Naht geprüft, nicht editiert.
  · +9 Tests (4 recall-e2e/-status, 2 dedupe, 3 web-Härtung; TDD: dedupe+web rot vor dem Fix).
    Eigene Scope-Suite grün, ruff clean. EHRLICH: Voll-Suite hatte zum Zeitpunkt des Laufs
    10–16 Failures AUSSCHLIESSLICH in parallel bearbeiteten Dateien (pipelines/*,
    grenzverschiebung/*, deren Tests + test_webapp-Kollateral); per git-stash-Gegenprobe
    bewiesen, dass test_webapp OHNE diese Änderungen identisch failt. Suite ohne die
    parallel-bearbeiteten Dateien: 0 failed.
- Schritt 9: grenzverschiebung/ — DONE (Claude-Review-Findings F1–F10 gefixt, TDD, 2 Commits
  04b8dea + 037e201):
  · F1 HIGH GEFIXT (lumencrucible:827): `... or True` fingierte einen nie gelaufenen
    8-Schritt-Lernzyklus, die statische lern_summary wurde in der ForschungsArbeit als
    durchgeführt gedruckt. Entscheidung: lernmaschine-Engine NICHT angeworfen — lern_summary
    trägt jetzt status=PLANNED_NOT_EXECUTED, Arbeit + EMERGENCE_SUMMARY weisen „geplant,
    nicht ausgeführt" explizit aus.
  · F2 HIGH GEFIXT: quelle behauptete unbedingt electronics+Wissensbasis+inverse design+
    multi-physics, Claim hart VERIFIED/0.92 — obwohl der Multi-Domain-Block IMMER stirbt
    (Import `from .architekt import …` zeigt ins falsche Paket; Module liegen in pipelines/).
    Jetzt: quelle aus real befüllten multi_domain-Keys komponiert; dokumentierte Abstufung
    VERIFIED/0.92 (keine Stufe übersprungen) → UNVERIFIED/0.7 (Teil-Erfolg) → UNVERIFIED/0.5
    (Multi-Domain leer). Der tote Import wurde bewusst NICHT „repariert" (das hieße die
    pipelines scharf zu schalten) — er ist jetzt sichtbar in skipped statt geschluckt.
  · F3 HIGH GEFIXT: save_fragment-Fehlschlag setzte new_recipe_id trotzdem → Arbeit behauptete
    geseedetes Rezept. Jetzt: None + mehwert_indicators["seed_failed"]=Grund + pending-Ausweis.
  · F7 MED GEFIXT: 6× bare `except Exception: pass` → eng gefasst wo klar (ImportError/
    TypeError), sonst strukturiert erfasst als multi_domain["skipped"]=[{stage,reason}]
    (Grundlage der F2-Degradierung).
  · F6 MED GEFIXT: fabrizierte „2026 Lab Results"-Items → FrontierItem.evidence_level
    (Default "synthetic"); boundary_reviser wertet NUR verified-Items auf, synthetische
    erzeugen Kandidaten-Notiz (old_typ==new_typ, „synthetische Front-Evidenz, unverifiziert"),
    NEEDS_BREAKTHROUGH bleibt; learning_integrator labelt den Energie-WissensEintrag als
    SYNTHETISCH und formuliert Regel/Vorschlag als Kandidat („WÜRDE verschieben").
  · F4 MED GEFIXT (paketweit, minimal-ehrlich wie software.py): 10 quelle-Strings behaupteten
    Konsum, den es nicht gibt (milestone_builder „+ gap_report" nie gelesen; breakthrough_watch
    „+ bench_test_plan" ohne solchen Input; …) → „nur (source_)traum konsumiert; <Feld> noch
    nicht ausgewertet — Lücke"; Prior-Parameter bleiben als reservierte API (Docstrings),
    KEINE Schein-Auswertung.
  · F5 MED GEFIXT: Substring-Trigger („mensch"+„fliegen" feuerte in „unmenschlich"/
    „Fliegengitter"; is_complex „power/board"; looks_fusion „zwei"/„fuse") → EIN Wortgrenzen-
    Helfer development_front.is_jetpack_traum für alle 12 Steine + präzise Regexes in
    lumencrucible (Muster wie pipelines/_triggers); Jetpack-Kanon-Pfade als Positivtests gepinnt.
  · F8 LOW GEFIXT: forge_research out_dir-Parameter (Default runs/ wie bisher), Tests hermetisch
    auf tmp_path, redundanter os-Import weg. F9 LOW: development_front-Fallback nannte gebaute
    Steine „zukünftiger Stein" → korrigiert. F10 LOW: bench_test_runner in __init__ exportiert.
  · VERDRAHTUNGSLAGE (ehrlich): lumencrucible ist der einzige verdrahtete Moonshot-Kern
    (Package-Export, simulation.runner-Typ-Naht, ruft map_development_front + apply_learning_cycle);
    development_front speist zusätzlich extensions/breakthrough_bridge; safety_ladder-TYPEN
    werden von inventor/safety wiederverwendet. Die übrigen 10 Builder sind reine Test-Inseln
    (nur aus tests/ aufgerufen): analyze_capability_gaps, build_milestone_ladder,
    design_experiment_plan, build_test_stand, build_technology_roadmap,
    build_technology_prototype, run_bench_test, watch_frontier, revise_boundary,
    build_safety_ladder.
  · DEFENDED nicht angefasst: Self-Ascent-Idempotenz, development_front/safety_ladder-
    Verdrahtung, boundary_reviser-Input-Konsum (nur die F6-Aufwertung geändert).
  · +11 Tests (TDD: 10 rot vor dem Fix), Paket-Suite 46/46 grün, ruff clean. Volle Suite
    1960 passed / 54 skipped / 1 failed — der eine Failure (test_webapp „seams_failed") ist
    in sauberen Worktrees auf 356d19b (vor ALLEN Grenzverschiebungs-Commits) und b57a322
    identisch reproduziert: vorbestehend, Scope der parallelen web/-Review, hier nicht angefasst.
- Schritt 9: pipelines/ — DONE (Claude-Review-Findings #1–#15 gefixt, TDD, 3 Commits):
  · #3/#4/#5/#6 HOCH GEFIXT (Trigger): `"flug" in idee_lower` matchte „Ausflug/Flughafen" und
    feuerte den vollen Jetpack-Kanon (regulatorik inkl. EASA/Haftung!) — EIN gemeinsamer Helfer
    pipelines/_triggers.is_flight_idea (exakt das S-2-Wortgrenzen-Regex aus software.py) in
    allen 6 Stellen (software/regulatorik/designer/elektriker/wirtschaft + fertigungs:125);
    #11-Trigger: architekt „fliegen"-Substring → has_fliegen_word (\bfliegen\b). Commit 356d19b.
  · #1/#2 HOCH GEFIXT (Provenienz): physiker (ingenieur) und techniker (ingenieur+physiker)
    lesen ihre Prior-Parameter NIE, behaupteten aber „breakthrough lab data 2026"/„ingenieur
    lastfaelle"/„manufacturing_check + ingenieur" — MINIMAL-EHRLICH nach S-1: _CANON_QUELLE
    „PLAN §4.x Kanon-Vorlage, kein Prior konsumiert (Lücke: echte Prior-Auswertung)", Werte als
    Kanon-Annahmen, Parameter als reserviert dokumentiert. #9 MED: designer/regulatorik/
    wirtschaft gleich (inkl. „8-25 EUR from Fertigungs" → Kanon-Annahme). #10 MED: regulatorik-
    Kanon deklariert „Lücke: EASA-Zuordnung/Zertifizierung ist Kanon-Annahme, kein Norm-
    Connector". #11-quelle: architekt-Überklaim (safety_ladder/learning_integrator/…) ehrlich.
    #12 LOW: toter main_assemblies-„jetpack"-Zweig in ingenieur/physiker/techniker entfernt;
    elektriker-Docstring „(+ optional Physiker loads)" ohne Param → geplante Naht. Commit 6ebbe26.
  · #7 HOCH GEFIXT (integrator): SystemConcept/IngenieurSpec ohne Pflichtfelder
    (zusammenfassung/source_concept) → TypeError bei JEDEM Aufruf, vom breiten except zu
    „fertigungs skipped" verschluckt — Fertigungs-Naht permanent tot, Manifest behauptete sie.
    Jetzt echte (concept, ingenieur)-Paare je Fragment (built_specs). #8 HOCH: `i` von
    enumerate-Loops auf int geclobbert → elektriker bekam Integer statt IngenieurSpec, getattr
    fiel still auf "" — sprechende Bindungen last_concept/last_ingenieur + Spy-Test. #13: prints
    → manifest["integration_notes"]/lern_note (kein stilles Löschen). #14: out/-„latest(_full)"-
    Stale-Bleed → _run_dir_name mintet eindeutiges „kind-unlabeled-UTCstamp" (Aufrufer geprüft,
    kein Leser hängt an „latest"). #15: pipelines/__init__ except → ImportError. Commit b57a322.
  · TEST-WAHRHEITS-BEFUND: test_physiker.py:25 („ingenieur/breakthrough in quelle"),
    test_architekt.py:21 („safety_ladder in quelle") und test_integrator.py:75 (nur
    `"fertigungs" in manifest`, akzeptierte den toten skipped-Eintrag) SCHÜTZTEN die Bugs —
    auf Ehrlichkeits-/Echtheits-Assertions umgestellt (Verbotslisten fabrizierter Herkunfts-
    Token, Manifest-Einträge müssen echte prozesse/kosten tragen).
  · DEFENDED nicht angefasst: elektriker-Exception-Handling (Z.216-228), ingenieur-Kern,
    _ingenieur_spec_to_dict, Empty-ideas-Guard; grenzverschiebung/integration/memory/web per
    Vorgabe unberührt.
  · +20 Tests (TDD: 11 rot vor dem Fix in test_pipeline_triggers/test_integrator/Honesty-Tests).
    Volle Suite 1960 passed / 54 skipped / 1 failed — der eine Failure (test_webapp
    „seams_failed" am LED-Halter) ist VORBESTEHEND: per PYTHONPATH-Worktree deterministisch auf
    3b5e293 und sogar 744bd2d^ (vor der ganzen Session, clean cwd) reproduziert; Ursache ist die
    required-Seam-Adjazenz ELECTRICAL↔FIRMWARE auf der capstone-Demo-Spec ohne Seam-Zertifikat
    (seams/demo/web-Scope der parallelen Review, hier nicht angefasst). ruff clean.
  · Offen (deklarierte Lücke, kein Bug): echte Prior-Auswertung in physiker/techniker/designer/
    regulatorik/wirtschaft/software (Parameter sind reservierte API; Kanon-Vorlagen sagen das jetzt).
- Schritt 9 NACHFIX (vorbestehender test_webapp-Failure, von beiden Fixern unabhängig bestätigt) —
  DONE: capstone trägt jetzt die ehrliche ELECTRICAL–FIRMWARE-Naht (q_fw_current_limit ≤ q_psu_a,
  DECISION + DomainSeam s_fw_strom, Zertifikat AM Spec); `Specification.seam_certificate`-Feld +
  `assess_specification`-Fallback (spiegelt TP1-Worktree-Design → Merge trivial); gate_epsilon
  fordert COST_ROLLUP nur noch wenn beweisbar (bom_cost.complete — vorher erzwang jede ehrlich-
  unvollständig bepreiste BOM mit anderem Pflichtpaar einen unzertifizierbaren Dauer-Fail);
  latenter Auto-Cost-Seam-Drop bei mitgeliefertem Zertifikat gefixt; completeness kennt
  Seam-Ausdrücke als Referenzkanal. +1 Regressionstest. Suite 1962/0/54, ruff clean.
  >>> DEEP-REVIEW-KAMPAGNE SCHRITT 7-9 KOMPLETT (alle 9 Schritte) — Grok-Cross-Reviews
  für 7/8/9 NACHZUHOLEN (CLI-Outage 2026-07-04) <<<
