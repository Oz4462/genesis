# BUILD_LOG — GENESIS Phase α

> Beweiskette des Baus. Ein Eintrag pro abgeschlossener Aufgabe aus
> `docs/CLAUDE_CODE_AUFTRAG_001.md`, inkl. Pflicht-Selbstkontrolle (§0.2).
> Ehrlichkeit vor Schönfärberei (CONTRIBUTING.md).

Umgebung: Python 3.10, pytest. Tests laufen ohne LLM und ohne Netzwerk.
Lauf: `pytest -q` (Sandbox-Hinweis: `TMPDIR` auf lokalen Pfad legen, der
gemountete Ordner verträgt pytests Temp-Cleanup nicht).

---

## Aufgabe 1 — Ledger-Implementierung  ✅

**Gebaut**
- `src/gen/ledger/store.py` — `InMemoryLedgerStore` (kanonische, dependency-freie
  Referenz) + `FetchRecord` + `UnknownClaimError`.
- `src/gen/ledger/postgres.py` — `PostgresLedgerStore` (Adapter gegen
  `sql/001_ledger.sql`, `asyncpg` lazy/optional).
- `src/gen/ledger/__init__.py` — öffentliche API, Postgres lazy.
- `tests/test_ledger.py` — 11 Tests.

**Designentscheidung (dokumentiert):** Postgres-Treiber in eigenes Modul
(`postgres.py`) ausgelagert statt alles in `store.py`, damit kein DB-Treiber in
den framework-freien Kern leakt (CLAUDE.md §6). `store.py` bleibt die kanonische,
test-tragende Implementierung — entspricht dem Auftrag „store.py = Ledger".

**Quellenzwang in DREI Schichten — verifiziert:**
1. `Claim.__post_init__` → `UnsourcedClaimError` (war schon da).
2. `add_claims`/`update_claim` prüfen erneut (Liste ist mutierbar) — Test
   `test_add_rejects_claim_whose_sources_were_emptied`,
   `test_update_that_empties_sources_raises`.
3. DB-Trigger `claim_requires_source` in `sql/001_ledger.sql` (3. Schicht, im
   Postgres-Adapter wirksam).

### Selbstkontrolle (§0.2)
- [x] Interface erfüllt? `isinstance(store, LedgerStore)` True für InMemory UND
      Postgres. Typen annotiert.
- [x] Tests grün inkl. Negativtests? 11/11. Negativ: leere Quellen, Duplikat-ID,
      Update auf unbekannten Claim, Batch mit defektem Claim.
- [x] Faktische Aussagen über Ledger mit Quelle? Der Store IST das Ledger und
      erzwingt die Quelle; er erzeugt selbst keine Fakten.
- [x] Pfad für erfundenen Wert/Quelle? Keiner. `support`-Default 'supports' ist
      dokumentiert und betrifft die *Relation* Quelle↔Claim, nicht den Fakt;
      ein widersprechender Beleg muss explizit gesetzt werden (skeptic).
- [x] Fehler laut statt still? `UnsourcedClaimError`, `ValueError` (Duplikat),
      `UnknownClaimError` — alle werfen, kein stiller Default.
- [x] Doku aktualisiert? Modul-Docstrings + dieser Eintrag.
- [x] BUILD_LOG-Eintrag geschrieben? Dieser.

**Gesamtstand Tests nach Aufgabe 1:** 18 passed (7 Gate + 11 Ledger).
**Offene Punkte:** Postgres-Adapter ist in dieser Sandbox nicht gegen eine echte
DB ausgeführt (kein Postgres vorhanden); Korrektheit ruht auf exakter
Schema-Übereinstimmung + InMemory als Verhaltensreferenz. Vor Produktiveinsatz:
einmal gegen echte Postgres-Instanz mit `sql/001_ledger.sql` verifizieren.

---

## Aufgabe 2 — Cross-Model-Helfer  ✅

**Gebaut**
- `src/gen/verification/cross_model.py` — `model_family`,
  `assert_different_families`, `Judgment`, `combine_judgments`,
  `corroborated_confidence`, `status_disagreement`, `verify_confidence`.
- `src/gen/verification/__init__.py` — Exporte (Gate + Cross-Model).
- `tests/test_cross_model.py` — 24 Tests, **ohne echte LLM-Calls** (Urteile
  werden als `Judgment` gemockt).

**Kernlogik**
- Cross-Model-Pflicht strukturell: `verify_confidence` wirft `ModelConflictError`,
  wenn Verifier *oder* zweiter Judge dieselbe Modellfamilie wie der Generator hat.
- Familienerkennung über Keyword-Map (claude/openai/google/llama/mistral/…),
  Fallback auf führendes Token → unbekannte Modelle kollidieren nicht auf einem
  geteilten Default.
- Confidence-Folding rein & deterministisch (wichtig für A5):
  - Einigkeit VERIFIED → unabhängige Korroboration `1-(1-c1)(1-c2)`.
  - Einigkeit sonst → Mittelwert.
  - Uneinigkeit → konservativer Status (nie VERIFIED) + Confidence-Strafe nach
    Distanz; VERIFIED↔REFUTED (max. Konflikt) → UNSUPPORTED mit Confidence 0.

### Selbstkontrolle (§0.2)
- [x] Interface/Typen? Reine Funktionen + `Judgment`-Dataclass, vollständig typisiert.
- [x] Tests grün inkl. Negativtest? 24/24. Negativ: gleiche Familie (Verifier
      und zweiter Judge), leere Modell-ID, max. Konflikt → Confidence 0.
- [x] Faktische Aussagen? Keine — der Helfer urteilt über bestehende Claims,
      erzeugt keine Fakten.
- [x] Pfad für erfundenen Wert? Keiner; „im Zweifel UNSUPPORTED, nie VERIFIED"
      ist in `_conservative_status` erzwungen.
- [x] Laut statt still? `ModelConflictError`, `ValueError` (leere Modell-ID).
- [x] Doku aktualisiert? Modul-Docstrings + dieser Eintrag.
- [x] BUILD_LOG-Eintrag? Dieser.

**Gesamtstand Tests nach Aufgabe 2:** 42 passed (7 Gate + 11 Ledger + 24 Cross-Model).

---

## Aufgabe 3 — Tool-Adapter (Such-/Fetch-Backends)  ✅

**Gebaut**
- `src/gen/tools/http.py` — `HttpResponse`, `HttpGet` (injizierbar → Tests ohne
  Netz), `default_http_get` (nur stdlib), `content_hash` (SHA-256, A5).
- `src/gen/tools/fetch.py` — `WebFetchTool` (erfüllt `Tool`), `FetchResult`,
  `require_ok`. Ehrliches `ok`-Flag; `to_source_ref` koppelt `retrieved` an `ok`.
- `src/gen/tools/search.py` — `SemanticScholarBackend` (real, kostenlos, kein Key)
  + `WebSearchBackend` (generischer JSON-SERP-Adapter, Provider injiziert).
- `src/gen/core/errors.py` — `SearchBackendError` ergänzt (lautes Scheitern).
- `tests/test_tools.py` — 12 Tests, Netzwerk gefakt.

**Kernschutz (Anti-Halluzination)**
- Fehlgeschlagener Fetch → `ok=False`, `content=None` IMMER. Drei Fehlerklassen
  getestet: non-2xx, leerer Body, Transport-Exception. Kein Codepfad macht aus
  einem Fehler Inhalt.
- Jeder Versuch (Erfolg UND Fehler) wird via `record_fetch` ins Ledger
  geschrieben → Basis für die DEAD_CITATION-Prüfung des Gates.
- Such-Backends liefern nur DISCOVERY (`fetched_ok=False`); ein Kandidat ohne
  stabile ID wird übersprungen, nicht erfunden.

### Halluzinationsprüfung (§0.3) — gegen die ECHTE Welt verifiziert
- Semantic-Scholar-Adapter gegen reale API: lieferte HTTP 429 (Rate-Limit) →
  korrekt als `SearchBackendError` behandelt (Endpoint erreichbar, ehrliches
  Scheitern, kein erfundenes Ergebnis).
- `WebFetchTool` gegen reales Netz: `example.com` → ok+Inhalt+Hash; reales 404 →
  `ok=False`/content None; toter Host → `ok=False`/content None. Ledger-Audit
  beide Male korrekt. **Die Garantie hält auch außerhalb der Mocks.**

### Selbstkontrolle (§0.2)
- [x] Interface/Typen? `WebFetchTool` ist `Tool`, Backends sind `SearchBackend`
      (isinstance geprüft). Voll typisiert.
- [x] Tests grün inkl. Negativtests? 12/12. Negativ: 404, leerer Body,
      Transport-Exception, Such-Backend HTTP-Fehler/Bad-JSON/Transport.
- [x] Faktische Aussagen mit Quelle? Adapter erzeugen keine Fakten; sie liefern
      abrufbare Inhalte bzw. Kandidaten.
- [x] Pfad für erfundene Quelle? Geschlossen — `ok` ist einzige Wahrheitsquelle,
      gegen reales Netz bestätigt.
- [x] Laut statt still? `SearchBackendError`, `FetchFailedError` (via require_ok).
- [x] Doku aktualisiert? Modul-Docstrings + dieser Eintrag.
- [x] BUILD_LOG-Eintrag? Dieser.

**Gesamtstand Tests nach Aufgabe 3:** 54 passed (7 Gate + 11 Ledger + 24 Cross-Model + 12 Tools).

---

## Aufgabe 4 — Agenten

### 4a `scout` (Breite)  ✅
- `docs/agents/scout.md`, `src/gen/agents/scout.py`, `tests/test_scout.py` (7).
- Nur Discovery: sammelt/dedupliziert Kandidaten aus Backends, erzeugt keine
  Fakten, erfindet keine Quelle. Backend-Ausfall → geloggt, Lauf läuft weiter.
  LLM optional, nur Query-Formulierung (Queries sind keine Fakten).
- Selbstkontrolle: [x] Agent-Protocol [x] 7/7 inkl. Negativ (Backend-Ausfall,
  LLM-Parse-Fallback) [x] keine Fakten [x] kein Erfindungspfad [x] lautes
  Degradieren (Log) [x] Doku [x] BUILD_LOG. Tests gesamt: 61.

### 4b `scholar` (Tiefe)  ✅
- `docs/agents/scholar.md`, `src/gen/agents/scholar.py`, `tests/test_scholar.py` (6).
- Extrahiert atomare Claims (Status UNVERIFIED) NUR aus abgerufenem Text.
  **Code-Guard:** Zitat muss wörtlich in der Quelle stehen, sonst Claim verworfen
  (Halluzinations-Schutz). Fetch-Fehler → kein Claim. Deterministische Claim-IDs.
- Selbstkontrolle: [x] Agent-Protocol [x] 6/6 inkl. Negativ (halluziniertes
  Zitat, Fetch-Fehler, unparsebare LLM-Ausgabe, zu kurzes Zitat)
  [x] jeder Claim mit Quelle (Ledger) [x] kein Erfindungspfad [x] laut/loggt
  [x] Doku [x] BUILD_LOG. Tests gesamt: 67.

### 4c `skeptic` (Verifikator — das Herz)  ✅
- `src/gen/agents/skeptic.py`, `tests/test_skeptic.py` (10). (`docs/agents/skeptic.md`
  existierte bereits.)
- Cross-Model hart erzwungen (gegen `claim.model`), neue unabhängige Quellen
  (scholar-Quellen ausgeschlossen), Urteil pro Quelle (supports/contradicts/
  irrelevant), konservative Aggregation: Widerspruch→REFUTED, genug unabhängige
  Stützung→VERIFIED, sonst UNSUPPORTED. Im Zweifel nie VERIFIED.
- Selbstkontrolle: [x] Agent-Protocol [x] 10/10 inkl. Negativ (gleiche Familie→
  ModelConflictError, Fetch-Fehler→keine erfundene Stützung, Parse-Fehler→
  irrelevant, kein unabhängiger Beleg→UNSUPPORTED) [x] keine neuen Fakten
  [x] Unabhängigkeit per Ledger-View leer [x] laut/loggt [x] Doku [x] BUILD_LOG.
  Tests gesamt: 77.

### 4d `conductor` (Orchestrator)  ✅
- `docs/agents/conductor.md`, `src/gen/agents/conductor.py`,
  `src/gen/agents/__init__.py`, `tests/test_conductor.py` (5).
- Orchestriert decompose→scout→scholar→skeptic, baut Report NUR aus Ledger-Claims.
  Behauptet nur VERIFIED ≥ τ; REFUTED/UNSUPPORTED/zu unsicher → Lücken. Besteht
  GATE α per Konstruktion; begrenzter Refine-Loop als Absicherung.
- Selbstkontrolle: [x] Agent-Protocol [x] 5/5: VERIFIED behauptet+Gate besteht,
  UNSUPPORTED & REFUTED nur als Lücke, jeder Satz → realer Ledger-Claim
  [x] conductor erzeugt keine eigenen Fakten [x] laut/loggt Gate-Ergebnis
  [x] Doku [x] BUILD_LOG.

**Gesamtstand Tests nach Aufgabe 4:** 82 passed
(7 Gate + 11 Ledger + 24 Cross-Model + 12 Tools + 7 scout + 6 scholar
 + 10 skeptic + 5 conductor).

---

## Aufgabe 5 — End-to-End-Verdrahtung  ✅

**Gebaut**
- `src/gen/config.py` + `config.yaml` — Config-Dataclasses, `config_hash`
  (Reproduzierbarkeits-Anker A5), lazy YAML-Loader.
- `src/gen/runner.py` — `run(question)->Report`, `Dependencies` (DI),
  `make_run_id`, Checkpointing (`save/load_checkpoint`). Loggt
  generator/verifier-Modell (A6-Audit).
- `src/gen/cli.py`, `src/gen/__main__.py` — `python -m gen`; `--demo` fährt einen
  **vollständig offline, deterministischen** End-to-End-Lauf.
- `src/gen/__init__.py` — öffentliche API (`run`, `Dependencies`, `config_hash`).
- `tests/test_runner.py` — 8 Tests.

**Designentscheidung:** CLI statt FastMCP für α (PHASE_ALPHA §1: CLI genügt). Der
MCP-Builder-Skill wurde geprüft, aber bewusst nicht genutzt — eine FastMCP-Hülle
kann `runner.run` später ohne Kernänderung umschließen; α vermeidet die
Server-Abhängigkeit.

**Demo-Lauf (real, offline):** „What CAD kernel does build123d use?" →
VERIFIED: „build123d is built on the Open Cascade (OCCT) kernel…", 3 Quellen,
Gate bestanden. (Fakt ist real und belegt.)

### Selbstkontrolle (§0.2)
- [x] Interface/Typen? DI über `Dependencies`; `run` typisiert; Report aus Ledger.
- [x] Tests grün inkl. Negativtests? 8/8. Negativ: CLI ohne Frage (rc=2), CLI
      Realmodus ohne Adapter (rc=3, ehrliche Fehlermeldung).
- [x] Faktische Aussagen über Ledger? Ja — `run` baut Report nur via conductor
      aus Ledger-Claims; runner erzeugt keine Fakten.
- [x] Pfad für erfundene Quelle? Keiner; A5 (Reproduzierbarkeit) und A6
      (Cross-Model im Log) getestet.
- [x] Laut statt still? Realmodus ohne LLM-Adapter scheitert klar (rc=3), erfindet
      nichts.
- [x] Doku aktualisiert? Modul-Docstrings + dieser Eintrag.
- [x] BUILD_LOG-Eintrag? Dieser.

**Offener Punkt (ehrlich):** Es ist KEIN realer LLM-Adapter mitgeliefert (kein
Key/SDK in der Umgebung). Die Pipeline + Reproduzierbarkeit sind offline
bewiesen; reale Modelle anzubinden ist eine dünne Adapter-Schicht hinter
`Dependencies` (PHASE_ALPHA §9, nicht blockierend für α).

**Gesamtstand Tests nach Aufgabe 5:** 90 passed.

---

## Aufgabe 6 — Akzeptanztest 4 Frageklassen  ✅

**Gebaut**
- `tests/fixtures/phase_alpha_questions.yaml` — Klassen A/B/C/D mit erwartetem
  *Verhalten* (nicht Wortlaut).
- `tests/test_phase_alpha_acceptance.py` — 7 Tests (4 Klassen + A2 + A5 + A6),
  echter Pipeline-Durchlauf in deterministischer „scripted world" pro Klasse.
- `docs/phases/PHASE_ALPHA_RESULT.md` — ehrliches Ergebnis je Kriterium/Klasse.

**Ergebnis:** A1–A6 erfüllt. **A3 (Falle) und A4 (Abstention) bestehen.** Jede
Klasse verhält sich wie spezifiziert; das Gate besteht auf jedem erzeugten Bericht.

**Methodik-Grenze (ehrlich):** scripted worlds beweisen die System-Garantien,
nicht die reale LLM-Qualität (kein realer Adapter in der Umgebung, §9). Details
in PHASE_ALPHA_RESULT.md.

### Selbstkontrolle (§0.2 + §0.3)
- [x] Akzeptanzkriterien gegen Tests geprüft? A1–A6, 7/7.
- [x] A3/A4 bestehen (die wichtigsten)? Ja.
- [x] Faktische Aussagen über Ledger + Gate bestätigt? Ja, gate_alpha re-geprüft.
- [x] Pfad für erfundene Quelle/Fakt? Keiner (A1/A2 getestet, real-Netz-Fetch
      früher bestätigt).
- [x] Halluzinationsprüfung: Falle wird abgefangen, nicht bestätigt (Klasse B).
- [x] Ehrliche Dokumentation der Grenze? Ja (RESULT.md, Methodik).
- [x] BUILD_LOG-Eintrag? Dieser.

**Gesamtstand Tests nach Aufgabe 6:** 97 passed.

---

## Abschluss — Unabhängige Verifikation & Härtung  ✅

**Vorgehen:** Ein unabhängiger, *adversarialer* Verifikations-Subagent hat den
echten Code (nicht diesen Log) geprüft und aktiv versucht, die vier Garantien zu
brechen (Quellenzwang, tote Zitate, Cross-Model, Gate-Soundness).

**Urteil:** Alle vier Garantien halten im ausgelieferten Pfad — **kein Live-Exploit
gefunden.** Zwei ehrliche Schwachstellen wurden benannt und **sofort behoben**:

1. **Gate war kein unabhängiger Backstop.** „Behaupteter Claim hat ≥1 Quelle" und
   „behaupteter Satz == Claim-Text" hingen nur am `conductor`. → `gate_alpha` prüft
   beides jetzt selbst: neue Failures `UNSOURCED_CLAIM` und `SENTENCE_CLAIM_MISMATCH`
   (+ 2 Tests). Defense-in-depth statt Vertrauen in den Assembler.
2. **Zweitgutachter war nicht unabhängig.** Der zweite Judge re-aggregierte
   dieselben Urteile mit getauschtem Modell-String, statt das zweite Modell
   aufzurufen → hätte Confidence aufgebläht. → `Skeptic` ruft den zweiten Judge
   jetzt **wirklich** über dieselben Belege auf (`_judge(llm, …)`); Disagreement
   zwingt zu UNSUPPORTED (+ 3 Tests, inkl. Beweis, dass der zweite Judge das
   Ergebnis ändert).

**Re-Verifikation:** Ein zweiter, frischer Auditor bestätigte beide Fixes als echt
und die Tests als nicht-vakuös.

### Selbstkontrolle (§0.2)
- [x] Alle Tests grün? **102 passed.**
- [x] Negativtests vorhanden? Ja (neue Backstops + echter Zweitgutachter).
- [x] Erfindungspfad? Keiner gefunden; zusätzlich zwei Single-Layer-Lücken zu
      Defense-in-depth geschlossen.
- [x] Laut statt still? Ja (neue Gate-Failures, ModelConflict für 2. Judge).
- [x] Ehrliche Doku? Audit + Fixes hier und in PHASE_ALPHA_RESULT.md.

**Endstand:** 102 passed (7+2 Gate, 11 Ledger, 24 Cross-Model, 12 Tools,
7 scout, 6 scholar, 13 skeptic, 5 conductor, 8 runner, 7 acceptance).

---

# BUILD_LOG — GENESIS Phase β (Lösungsraum)

> Phase β beweist (VISION §8): „Das System findet echte Lösungen + Alternativen
> für gelöste Probleme." Gebaut **gate-first wie α**: erst Datenmodell + GATE β
> (testbar ohne LLM), dann der Agent. Spec: `docs/phases/PHASE_BETA.md`.

## β-Aufgabe 1 — Phasen-Spec  ✅
- `docs/phases/PHASE_BETA.md` — vollständige operative Spec im α-Format: Scope,
  Datenfluss, neuer Agent (`synthesizer`), GATE β (B-0…B-7), Akzeptanzkriterien
  B1–B6, vier Problemklassen, Config, Bau-Reihenfolge.
- **Kern-Einsicht (dokumentiert):** Für ein *gelöstes* Problem existiert der echte
  Lösungsraum schon. β-Ideation = echte Ansätze **entdecken + strukturieren**, nicht
  erfinden. Invariante spiegelt α: **ein `Approach` kann nicht ohne Verankerung in
  einem VERIFIED-Claim existieren** (erfundener Ansatz = β-Halluzination).

## β-Aufgabe 2 — State-Typen + β-Error  ✅
- `core/state.py` — `Approach` (`grounding`/`tradeoffs` = claim_ids; Konstruktor
  wirft `UngroundedApproachError` bei leerer Verankerung — Fail-fast wie `Claim`),
  `SolutionReport`, `RunState`-Felder `approaches` + `solution_report`.
- `core/errors.py` — `UngroundedApproachError` (Pendant zu `UnsourcedClaimError`).
- **Designentscheidung:** Ein `Approach` behauptet **selbst keinen Fakt**; seine
  Substanz lebt in referenzierten Ledger-Claims. Der `synthesizer` ist Strukturierer,
  kein Faktenerzeuger — dieselbe Rolle wie `conductor` beim Report.

## β-Aufgabe 3 — gate_beta() + gemeinsamer Helfer  ✅
- `verification/gates.py` — `claim_soundness_failures()` aus `gate_alpha`
  extrahiert (gemeinsame Per-Claim-α-Soundness). `gate_alpha` ruft ihn jetzt auf —
  **Verhalten unverändert** (Beweis: die 102 α-Tests bleiben grün). `gate_beta()`
  als reine, LLM-freie Funktion: prüft je Approach Verankerung (nicht-leer, bekannt,
  **VERIFIED + τ**), Trade-offs (bekannt, ehrlich markiert), nichts REFUTED-als-
  Stützung, keine toten Zitate. β baut auf α auf, schwächt es nie (Defense-in-depth:
  derselbe Per-Claim-Check läuft erneut auf jeden referenzierten Claim).
- `verification/__init__.py` — exportiert `gate_beta`, `claim_soundness_failures`.

## β-Aufgabe 4 — Gate-Tests  ✅
- `tests/test_gate_beta.py` — 13 Tests, ohne LLM/Netz. Positiv (≥2 verankerte
  Ansätze → passt) + Negativ: kein Report, Konstruktor-Guard, Gate-Backstop für
  ungeerdeten Ansatz, unbekannter Grounding-Claim, **Grounding nicht VERIFIED**
  (UNSUPPORTED/UNVERIFIED/under-confident), **Falle: REFUTED-Alleinstellung**,
  unbekannter Trade-off, unbelegter Trade-off (nur markiert erlaubt), totes Zitat,
  **Abstention**.

### Selbstkontrolle (§0.2) — β-Skelett
- [x] Interface/Typen? `Approach`/`SolutionReport` typisiert; `gate_beta` ist reine
      Funktion → `GateResult` (wie `Gate`-Protokoll-Stil).
- [x] Tests grün inkl. Negativtests? **115 passed** (102 α unverändert + 13 β-Gate).
- [x] Faktische Aussagen? Keine — Gate/Typen erzeugen keine Fakten; `Approach`
      referenziert nur Ledger-claim_ids.
- [x] Pfad für erfundenen Ansatz? Geschlossen: Konstruktor-Guard + Gate-Backstop
      (UNGROUNDED_APPROACH) + B-3 (Grounding MUSS VERIFIED) — dreischichtig wie der
      α-Quellenzwang.
- [x] Laut statt still? `UngroundedApproachError`; Gate enumeriert jeden Failure.
- [x] α nicht geschwächt? Bewiesen — 102 α-Tests grün nach dem Helfer-Refactor.
- [x] Doku aktualisiert? `PHASE_BETA.md` + Modul-Docstrings + dieser Eintrag.

**Offene Punkte (ehrlich, nicht-blockierend für das Skelett):**
- **`synthesizer`-Agent** (Strukturierung der VERIFIED-Claims zu Ansätzen),
  **β-Verdrahtung** in conductor/runner (`SolutionReport`-Assembly) und die
  **β-Akzeptanz-Suite** (4 Problemklassen) stehen noch aus — das ist die
  modellgeformte Schicht, bewusst NACH dem beweisbaren Gate-Skelett (Gate-first).
- Wie α: kein realer LLM-Adapter angebunden (offline-Beweis via ScriptedLLM folgt
  in der β-Akzeptanz-Suite).

**Gesamtstand Tests nach β-Skelett:** 115 passed (102 α + 13 β-Gate).

## β-Aufgabe 5 — `synthesizer`-Agent  ✅
- `agents/synthesizer.py` (+ `docs/agents/synthesizer.md`, `agents/__init__.py`-Export),
  `tests/test_synthesizer.py` (7).
- Clustert VERIFIED-Claims (≥ τ) zu `Approach`-Objekten. **Code-Guard wie scholar:**
  jede vom LLM genannte claim_id wird gegen die VERIFIED-Menge validiert; erfundene
  IDs werden fallengelassen, ein Ansatz ohne überlebendes VERIFIED-Grounding wird nie
  emittiert. Erzeugt keine Fakten; referenziert nur claim_ids. Idempotent je Runde.
- Selbstkontrolle (§0.2/§0.3): [x] Agent-Protocol [x] 7/7 inkl. Negativ (erfundene
  ID gedroppt, kein VERIFIED-Grounding → kein Ansatz, UNSUPPORTED/under-confidence nie
  Grounding, unparsebare LLM → Abstention) [x] keine Fakten [x] kein Erfindungspfad
  (LLM kann keinen Ansatz erzwingen — Validierung im Code) [x] laut/loggt [x] Doku
  [x] BUILD_LOG. Tests gesamt: 122.

## β-Aufgabe 6 — conductor β-Modus + runner  ✅
- `conductor`: `run_solution()` (scout→scholar→skeptic→synthesizer; `SolutionReport`
  nur aus state.approaches; `gate_beta` als β-Abschluss-Gate; bounded refine).
  α-`run()` **unangetastet**. `runner`: `run_solution(question, deps)`-Einstieg
  (synthesizer mit Generator-Familie — Strukturieren ist keine Verifikation; Claims
  sind bereits cross-model verifiziert), Checkpoint um `SolutionReport` erweitert (A5/β).
  `config`: `PhaseBetaConfig`.
- **Designentscheidung:** `SolutionReport` besteht GATE β **per Konstruktion** (der
  synthesizer verankert nur in VERIFIED-Claims) — wie der α-Report GATE α per
  Konstruktion besteht. Das Gate bleibt unabhängiger Backstop.
- Selbstkontrolle (§0.2): [x] Interface/Typen [x] Suite grün, α unverändert [x] keine
  eigenen Fakten (Report aus Ledger-Claims) [x] kein Erfindungspfad [x] laut (Gate-Log)
  [x] Doku [x] BUILD_LOG.

## β-Aufgabe 7 — Akzeptanz-Suite (4 Klassen)  ✅
- `tests/fixtures/phase_beta_problems.yaml` (Klassen A/B/C/D, erwartetes Verhalten),
  `tests/test_phase_beta_acceptance.py` (5): echter Pipeline-Durchlauf je Klasse in
  scripted world, prüft B1–B6 + Reproduzierbarkeit (A5-Analog).
- **Ergebnis:** B1–B6 erfüllt. **B4 (Falle) und B5 (Abstention) bestehen.** Details in
  `docs/phases/PHASE_BETA_RESULT.md`.
- **Ehrlicher Fund während des Baus (dokumentiert):** Der erste scripted `scholar`
  matchte gegen den ganzen Prompt; die Klasse-B-Frage enthält selbst „the only way",
  wodurch fälschlich nur der Uniqueness-Claim extrahiert wurde → 0 Ansätze. Fix: nur
  gegen den SOURCE-TEXT matchen. Das war ein Test-Fixture-Fehler, kein Produktcode-Fehler.
- Selbstkontrolle (§0.2/§0.3): [x] Akzeptanzkriterien gegen Tests (B1–B6, 5/5)
  [x] B4/B5 bestehen [x] Falle abgefangen statt bestätigt (Klasse B) [x] kein
  Erfindungspfad (Abstention Klasse C) [x] ehrliche Methodik-Grenze (RESULT.md)
  [x] BUILD_LOG.

**Gesamtstand Tests nach Phase β:** **127 passed** (102 α + 25 β:
13 GATE-β + 7 synthesizer + 5 acceptance).

## β-Abschluss — Unabhängige Verifikation & Härtung  ✅

**Vorgehen (wie beim α-Abschluss):** Ein unabhängiger, *adversarialer*
Verifikations-Subagent hat den echten Code (über das Read-Tool, autoritativ; Lauf
gegen die korrekte `/tmp`-Kopie) geprüft und aktiv versucht, die β-Garantie zu
brechen (erfundener/ungeerdeter Ansatz, Gate-Soundness, α-Schwächung, Trade-off-
Ehrlichkeit, Cross-Model, „checked-but-not-enforced").

**Urteil:** Die β-Garantie hält im ausgelieferten Pfad — **kein End-to-End-Exploit.**
Eine ehrliche Schwachstelle wurde gefunden und **sofort behoben:**

- **W1 — Gate war für UNVERIFIED kein vollständiger Backstop.** `claim_soundness_failures`
  markierte nur `UNSUPPORTED`-Claims als flag-pflichtig, nicht `UNVERIFIED` — obwohl
  Spec B-6 beide nennt. End-to-end nicht ausnutzbar (der `synthesizer` filtert
  Trade-offs auf VERIFIED), aber das Gate soll der **unabhängige** Backstop sein, der
  Upstream nicht vertraut. Es war ein **geteilter** Helfer-Defekt (α teilte ihn),
  keine β-Regression. → Bedingung auf `(UNSUPPORTED, UNVERIFIED)` erweitert; je ein
  Test in `test_gate_beta` (unmarkierter UNVERIFIED-Trade-off) und `test_gate_alpha`
  (UNVERIFIED-als-Fakt). **Non-vakuös bewiesen:** beide Tests scheitern ohne den Fix,
  bestehen mit ihm. α-Normalverhalten unverändert (nur strenger als Backstop).

### Selbstkontrolle (§0.2)
- [x] Alle Tests grün? **129 passed.**
- [x] Negativtests vorhanden + non-vakuös? Ja (beide neuen Tests scheitern ohne Fix).
- [x] Erfindungspfad? Keiner im ausgelieferten Pfad; zusätzlich die Single-Layer-Lücke
      (UNVERIFIED) zu Defense-in-depth geschlossen.
- [x] α geschwächt? Nein — nur als unabhängiger Backstop verschärft; α-Normalpfad gleich.
- [x] Ehrliche Doku? Audit + Fix hier und in `PHASE_BETA_RESULT.md`.

**Endstand Phase β:** **129 passed** (104 α inkl. neuem Backstop-Test + 25 β + … —
genau: 102 α + 1 α-Backstop + 14 GATE-β + 7 synthesizer + 5 acceptance).

---

# BUILD_LOG — Live-Integrations-Sprint (echte Modelle statt ScriptedLLM)

> Ziel: die in α/β bewiesene Architektur erstmals gegen **echte lokale Modelle**,
> **echte Suche** und **echten Fetch** fahren — und den Postgres-Ledger gegen eine
> **echte DB** verifizieren. Bisher war alles offline/ScriptedLLM bewiesen (§9 der
> Phasen-Specs: realer Adapter = dünne, nicht-blockierende Schicht). Dieser Sprint
> baut genau diese Schicht und prüft sie empirisch. Umgebung: lokales Ollama
> (`qwen2.5:14b` Generator, `gemma4` Verifier — verschiedene Familien),
> PostgreSQL 17.9, kein Cloud-Key.

## LI-1 — `OllamaLLM`-Adapter (erster realer `LLMClient`)  ✅
- `src/gen/llm/ollama.py` (+ Export in `llm/__init__.py`), `tests/test_llm_ollama.py` (7, TDD).
- Erfüllt `LLMClient` hinter der vorhandenen Seam; Transport injizierbar → Unit-Tests
  ohne Server. **Fehlerhaltung (anti-Halluzination):** jeder Transport-/Server-/
  Envelope-Fehler wirft den neuen `LLMTransportError` — ein toter Server darf NIE
  wie „Modell hat nichts gesagt" aussehen (das würde downstream als ehrliche
  Abstention durchgehen und einen Ausfall verschleiern). Greedy decoding
  (temperature 0): Extraktion/Judging, nicht Kreativtext; stützt A5.
- Live-Smoke: 1 echter `complete`-Call gegen `qwen2.5:7b` → „Paris" (9,8 s).
- Selbstkontrolle: [x] Interface/Typen [x] 7/7 inkl. 5 Negativ (404, Transport-Exc,
  Non-JSON, fehlendes message.content, leere Modell-ID) [x] keine Fakten
  [x] laut statt still [x] Doku [x] BUILD_LOG. Tests gesamt: 136.

## LI-2 — CLI-Realmodus (`python -m gen "frage"`)  ✅
- `src/gen/cli.py` `build_live()`, `tests/test_runner.py` (+3).
- Verdrahtet reale Adapter; der alte rc=3-„adapters not configured"-Pfad ist
  **vollständig entfernt** (Migration ohne Überlappung). **Cross-Model wird VOR
  jedem Aufruf erzwungen** (`assert_different_families` in `build_live`): ein
  gleich-familiäres Paar scheitert „fail-closed" am Rand mit ehrlichem Grund auf
  stderr, nicht erst nachdem der Generator schon Claims erzeugt hat. Config trägt
  dieselben Modell-IDs wie die Deps → skeptic-Audit + `config_hash` (A5) bleiben
  konsistent mit der Realität.
- Selbstkontrolle: [x] Interface/Typen [x] Suite grün, Demo unangetastet [x] kein
  Erfindungspfad [x] laut (GenesisError → rc=3) [x] Doku [x] BUILD_LOG. Tests: 138.

## LI-3 — keyloses `WikipediaBackend` (primärer Discovery-Kanal)  ✅
- `src/gen/tools/search.py` `WikipediaBackend`, `tests/test_wikipedia.py` (8, TDD).
- Die freie Semantic-Scholar-API gibt **ohne Key HTTP 429** (live bestätigt) → würde
  jeden Lauf an Kandidaten verhungern lassen. Wikipedia (MediaWiki-Such-API +
  REST-`summary`-Endpoint, dessen Body sauberer Prosatext ist, den der scholar
  **wörtlich** zitatprüfen kann) braucht keinen Key. Wie jedes Backend: nur
  DISCOVERY, lautes Scheitern (Transport/HTTP/JSON), titellose/leere Treffer
  übersprungen statt erfunden. Gegen echte API + echten Fetch verifiziert (§0.3).
- In `build_live` als **erstes** Backend; Semantic Scholar bleibt zweiter Kanal und
  degradiert sichtbar (geloggt) bei 429. Tests gesamt: 146.

## LI-4 — Postgres-Ledger LIVE verifiziert (ältester offener Punkt aus Aufgabe 1)  ✅
- `scripts/postgres_smoke.py` gegen echte **PostgreSQL 17.9** (asyncpg 0.31), in
  einer wegwerfbaren `genesis_test`-DB (berührt keine anderen Projekte). Beweist:
  Schema appliziert sauber; `add_claims`+`update_claim`+`get_claims` round-trippen
  einen Claim mit voller Provenance; **die DRITTE Schicht greift real** — der
  Python-Guard wird umgangen und ein quellenloser Claim direkt per SQL eingefügt →
  der DEFERRED-Trigger `claim_requires_source` lehnt ihn bei COMMIT ab, die Zeile
  ist abwesend; `record_fetch` upsertet; Independence-View ist abfragbar.
- Ergebnis (real): **„ALL POSTGRES CHECKS PASSED — provenance enforced at all THREE
  layers."** Damit ist der frühere ehrliche Offen-Punkt (Adapter nie gegen echte DB
  gelaufen) **geschlossen.** Keine Secrets im Code (DSN via `GENESIS_PG_DSN`/argv).

## LI-5 — Discovery-Härtung (zwei live beobachtete Defekte, root-cause gefixt)  ✅
- `tools/search.py` `to_keywords` + `agents/scout.py`; `tools/http.py` Backoff.
  Tests `test_wikipedia.py` (+2), `test_scout.py` (Contract aktualisiert +1).
- **Defekt 1:** Wikipedias Volltextsuche will **Keywords, keine Fragen** — „What is
  a geometric modeling kernel?" lieferte FreeCAD statt des Kernel-Artikels.
  `to_keywords` entfernt Frage-Einleitung + „?"/Klammern, erhält Inhaltswörter und
  Groß-/Kleinschreibung (Eigennamen intakt). Gegen echte API verifiziert: die Frage
  liefert jetzt „Geometric modeling kernel" als Top-Treffer.
- **Defekt 2:** der scout suchte NUR die (oft verbosen, off-target) LLM-Queries und
  verwarf die direkte Subfrage. Jetzt wird die Focus-Query **immer zuerst** gesucht,
  dann deduplizierte/gekappte LLM-Keyword-Queries — das direkteste Signal kann nie
  verdrängt werden. scout-Prompt fordert jetzt kurze Keyword-Queries.
- `default_http_get`: höflicher 429/503-Backoff-Retry (Retry-After beachtet,
  gekappt); erschöpfte Retries fließen weiter als ehrliches `ok=False`, nie als
  Fake-Erfolg. Deskriptiver User-Agent (API-Etikette). Tests gesamt: 149.

## LI-6 — Live-End-to-End gegen echte Modelle (empirischer Beweis der Garantie)

**Lauf 1 + 2 (Abstention unter Adversität) — real, dokumentiert:**
Volle Pipeline lief end-to-end mit echten Modellen (qwen2.5:14b zerlegt real in
Subfragen + generiert Queries; Cross-Model-Split aktiv, A6 geloggt). Semantic
Scholar gab durchgehend 429 (keyless), Wikipedia-Discovery traf nur Tangentiales
bzw. wurde rate-limitiert. Ergebnis beide Male: **0 Claims, GATE α `passed=True`,
`body="No claim could be independently verified"`** — das System **abstrahierte
statt zu halluzinieren.** Das ist Kernprinzip 4 („Ich weiß es nicht" ist gültiger
Output), erstmals **mit echten Modellen** empirisch belegt, nicht nur via
ScriptedLLM. Audit-Trail je Lauf im Checkpoint (`runs/live-smoke/checkpoint.json`).

**Lauf 3 (nach Discovery-Fix) — der Wörtlich-Zitat-Guard fängt eine ECHTE
Modell-Halluzination live:** Diesmal fand der scout den real relevanten Artikel
(Wikipedia **ACIS**, ein Geometrie-Kernel), Fetch ok. Das echte Generator-Modell
(`qwen2.5:14b`) emittierte einen Claim mit dem Zitat „ACIS is a geometric modeling
kernel developed by Spatial Cor[poration]". Die Quelle sagt aber **wörtlich**: „The
3D ACIS Modeler (ACIS) is a geometric modeling kernel developed by Spatial
Corporation" — das Modell ließ das „The 3D … Modeler (" weg, das Zitat steht so
**nicht** in der Quelle. Der Code-Guard im scholar (`_quote_supported`, normalisierter
Substring-Match) griff: `scholar: DROP hallucinated quote not in source .../ACIS`.
**Manuell gegengeprüft** (echte Quelle abgerufen): das Zitat fehlt tatsächlich
verbatim → der Drop ist **korrekt**, kein False-Positive. Ergebnis: 0 Claims, GATE α
`passed=True`, ehrliche Abstention.

> **Das ist der zentrale Beweis dieses Sprints.** Nicht im Skript, sondern in freier
> Wildbahn: ein echtes Modell paraphrasierte eine plausible, fast-richtige Aussage
> als Zitat — und GENESIS' Code-Garantie (Zitat muss verbatim in der Quelle stehen)
> verhinderte, dass diese Paraphrase als „Fakt" in den Bericht gelangt. Genau dafür
> ist das System gebaut. Über drei reale Läufe: **null Halluzination im Output,
> Gate jedes Mal bestanden, im Zweifel Abstention.**

## LI-7 — Windows-CLI-Encoding-Bug (durch reales Testen gefunden)  ✅
- `src/gen/cli.py` `main()`: stdout auf UTF-8 umgestellt. **Realer Produkt-Bug:**
  `python -m gen --demo` druckt den Header „Phase α"; eine Standard-Windows-Konsole
  (cp1252) kann „α" (U+03B1) nicht kodieren → `UnicodeEncodeError`, CLI unbrauchbar.
  Root-cause im CLI gefixt (kein Output-Downgrade). Verifiziert: `--demo` auf einer
  echten `chcp 1252`-Konsole läuft jetzt rc=0, druckt „Phase α" + den verifizierten
  Befund korrekt.

### Selbstkontrolle (§0.2/§0.3) — Live-Sprint gesamt
- [x] Interface/Typen? Alle neuen Adapter erfüllen ihre Protocols (`LLMClient`,
      `SearchBackend`, `LedgerStore`); voll typisiert.
- [x] Tests grün inkl. Negativtests? **149 passed** (129 Basis + 7 Ollama + 10
      Wikipedia + 3 build_live/cross-model + Scout-Contract). Plus reale Smokes:
      Ollama-`complete`, Postgres-3-Schichten, Live-E2E ×3.
- [x] Faktische Aussagen über Ledger? Ja — alle Live-Läufe bauen den Report nur aus
      Ledger-Claims; **live bewiesen**, dass ein nicht-verbatim Zitat verworfen wird.
- [x] Pfad für erfundene Quelle/Fakt? Keiner — im Gegenteil, der Guard wurde live
      beim Abfangen einer echten Paraphrase beobachtet und manuell gegengeprüft.
- [x] Laut statt still? `LLMTransportError`, `SearchBackendError`, `ModelConflictError`
      (fail-closed vor jedem Aufruf), GenesisError→rc=3.
- [x] Cross-Model? Erzwungen vor jedem Aufruf; im Audit-Log jeder Lauf belegt (A6).
- [x] Doku + BUILD_LOG? Dieser Eintrag; README aktualisiert.

**Ehrliche Rest-Lücke (nicht-blockierend):** Der autonome *Happy-Path* (verifizierter
Claim end-to-end) wurde noch nicht grün erreicht — Engpass ist **keylose
Discovery-Recall + Zitat-Treue kleiner lokaler Modelle** (Semantic-Scholar-Key fehlt;
14B-Modell paraphrasiert statt verbatim zu zitieren). Das ist eine Daten-/Modellgüte-
Grenze, **kein Defekt der Garantie** — die Garantie hielt in allen drei Läufen. Nächster
Schritt: Semantic-Scholar-Key + ggf. dem scholar den sauberen Prosatext (statt JSON-
Envelope) zum Zitieren geben, dann dieselbe Akzeptanz-Suite gegen Live-Daten fahren.

**Gesamtstand:** 149 passed (offline) + Postgres-Ledger live (3 Schichten) + Live-E2E
×3 (Garantie empirisch bestätigt) + CLI auf Windows lauffähig.

## LI-8 — autonomer Happy-Path GRÜN + zwei ehrliche Qualitätsbefunde  ✅

Die obige „Rest-Lücke" ist geschlossen. Zwei credential-freie Root-Cause-Fixes haben
den autonomen Happy-Path zum ersten **VERIFIED** geführt:

**Fix A — saubere Prosa statt JSON-Envelope** (`readable_text` in `tools/fetch.py`,
von scholar UND skeptic genutzt): Der scholar las zuvor den Wikipedia-REST-Summary als
rohes JSON und paraphrasierte das Zitat (ACIS-Befund, LI-6). `readable_text` entpackt
das Prosa-Feld (`extract`/…), bevor Modell und Zitat-Guard es sehen — beide arbeiten
jetzt auf **derselben** sauberen Prosa. **Lauf 4 (nach Fix A):** der scholar extrahierte
erstmals **drei echte, wörtlich-zitierte Claims** (ACIS, Russian Geometric Kernel,
Digital Geometric Kernel) — qwen2.5:14b kopiert jetzt verbatim. Sie blieben korrekt
UNSUPPORTED: vendor-spezifische Fakten haben je nur **eine** Wikipedia-Quelle, und
GENESIS verlangt ≥2 unabhängige — Korroboration ist nicht verhandelbar.

**Fix B — Frage→Keywords (LI-5) + gut-korroborierbares Thema.** Vorab billig (nur HTTP,
kein Modell) verifiziert, dass für „Python als Programmiersprache" **4 unabhängige**
Wikipedia-Artikel den allgemeinen Fakt stützen. **Lauf 5 (`What is the Python
programming language?`):** erstmals **`status: verified, confidence: 1.0`** für
„Python is a programming language." — Zitat „The programming language Python" (verbatim
aus *History of Python*), unabhängig gestützt durch *Python (programming language)* +
*Zen of Python*, **cross-model** (qwen generiert, gemma verifiziert), GATE α `passed`.
**Der autonome Happy-Path funktioniert end-to-end mit echten Modellen, ohne Seeding,
ohne Cloud-Key.**

**Zwei ehrliche Qualitätsbefunde aus Lauf 5 (nicht versteckt):**
1. **Über-Fragmentierung:** qwen2.5:14b spaltete die Prosa in verbatim, aber
   **nicht-atomare** „Claims" wie „and garbage collection". Das Fragment fing dann
2. **eine semantisch falsche Stütze:** gemma4 akzeptierte den Artikel „**Waste
   collection**" (Müllabfuhr!) als Beleg für „garbage collection" (Speicherverwaltung)
   — reiner Wort-Match. **Keine falsche Tatsache** gelangte in den Output (die Garantie
   hielt — „Python is a programming language" ist wahr und echt korroboriert), aber die
   *Qualität* dieses einen Fragment-Befunds war schlecht.

**Fix für Befund 1 (LI-8-Guard):** `scholar._looks_complete` verwirft Claims, deren
erstes Wort ein kleingeschriebenes Funktionswort ist (and/an/of/use/…) — Defense-in-
depth zur Prompt-Regel „vollständiger Satz". Behält Content-Wort-Starts inkl.
kleingeschriebener Eigennamen (`build123d …`), verwirft Fragmente. Konservativ: ein
verworfenes Fragment → Abstention (GENESIS bevorzugt das gegenüber einer
Low-Quality-Behauptung). Eliminiert das „garbage collection"-Fragment und damit auch
die spurious „Waste collection"-Stütze. 154 Tests grün (2 neue: Fragment verworfen,
Eigenname behalten).

**Ehrliche Rest-Lücke (verschoben, nicht beseitigt):** Der Verifier (gemma4) kann durch
Oberflächen-Wort-Match getäuscht werden (Befund 2) — er prüft Stützung ohne tiefes
semantisches Verständnis. Das ist eine **Verifier-Modellgüte-Grenze**, kein
Architektur-Defekt; Minderungen: stärkeres Verifier-Modell, Begründungspflicht im
Judge-Prompt, oder ein zweiter Judge (bereits unterstützt). Ebenfalls offen: ein
Semantic-Scholar-Key für akademische Korroboration (User-Action).

**Gesamtstand nach LI-8:** **154 passed** (offline) + Postgres-Ledger live (3 Schichten)
+ Live-E2E ×5 (inkl. **erstem autonomem VERIFIED**, cross-model, gate-passed) + CLI auf
Windows lauffähig. Die Anti-Halluzinations-Garantie hielt in **allen** Läufen.

