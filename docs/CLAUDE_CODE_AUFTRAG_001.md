# CLAUDE CODE — AUFTRAG 001
## Phase α fertigstellen: Agenten + erster End-to-End-Lauf

> **An Claude Code:** Dies ist ein verbindlicher Bauauftrag. Lies zuerst
> `CLAUDE.md`, `docs/VISION.md` und `docs/phases/PHASE_ALPHA.md` vollständig.
> Bei jedem Konflikt gewinnen die Kernprinzipien in `CLAUDE.md §Kernprinzipien`.
> Arbeite die Aufgaben in Reihenfolge ab. Nach JEDER Aufgabe: Selbstkontrolle
> (siehe unten). Kein Fortfahren, wenn die Selbstkontrolle nicht besteht.

---

## 0. ARBEITSWEISE (gilt für den gesamten Auftrag — nicht verhandelbar)

### 0.1 Struktureller Aufbau
- Jede Aufgabe hat einen **klaren Anfang** (was, warum, gegen welches Interface)
  und ein **klares Ende** (Definition of Done erfüllt, Selbstkontrolle bestanden).
- Baue **gegen die Interfaces** in `src/gen/core/interfaces.py`, niemals gegen ein
  konkretes Framework. Framework-spezifisches kommt hinter Adapter.
- Eine Datei = eine Verantwortung. Keine Sammeldateien, keine Gott-Module.
- Reihenfolge strikt einhalten: erst Dinge, die OHNE LLM testbar sind, dann LLM-Anbindung.

### 0.2 Selbstkontrolle nach JEDER Aufgabe (Pflicht-Ritual, erweitert auf Ultra-Workflow + 4 Linsen)
Nach jeder einzelnen Aufgabe führe diese **erweiterte** Checkliste aus und dokumentiere das
Ergebnis in `docs/BUILD_LOG.md` (anlegen, falls nicht vorhanden). Dies ist jetzt der
**Ultra-Standard** (siehe `docs/4_LINSEN_PRINZIP.md` + autonome Aktivierung via genesis-ultra-workflow Skill).

```
[ ] Erfüllt der Code das Ziel-Interface? (Typen geprüft)
[ ] Tests grün? (inkl. mindestens 1 Negativtest)
[ ] Erzeugt der Code faktische Aussagen? Wenn ja: läuft JEDE über das Ledger
    mit Quelle? (sonst BUG)
[ ] Gibt es einen Pfad, auf dem ein erfundener Wert/Quelle entstehen könnte?
    Wenn ja: schließen, BEVOR weitergebaut wird.
[ ] Ist das Verhalten bei Fehlern laut (Exception) statt still (Default)?
[ ] Doku-Datei des Moduls/Agenten aktualisiert?
[ ] BUILD_LOG.md Eintrag geschrieben (Aufgabe, Ergebnis, offene Punkte)?
[ ] L1 (Wahrheits-Linse) bestanden + Beleg (Abgleich mit PLATFORM_PLAN.md)
[ ] L2 (Drift-/Grounding-Linse) bestanden + Check gegen vorherigen Stand/Goldset
[ ] L3 (Vollständigkeits-/Naht-Linse) bestanden + Seams + PLATFORM_PLAN-Outputs/Gates
[ ] L4 (Realisierbarkeits-Linse) bestanden + Fidelity + Testbarkeit + Gate-Kompatibilität
```
Wenn ein Punkt „nein" ist: **stoppen, beheben, erst dann weiter.**

**Zusätzlich für Agenten/Subagenten (§0.3 erweitert):** Jeder Subagent, der Inhalte produziert, bekommt die Instruktion, nach seiner Sub-Aufgabe die volle erweiterte Selbstkontrolle (0.2 + 4 Linsen mit explizitem Abgleich zum aktuellen GENESIS_PLATFORM_PLAN-Abschnitt) als Selbst-Report mit Belegen zu liefern, bevor Control zurückgegeben wird. Kein Fake-Erfolg.

### 0.3 Halluzinationsprüfung bei Agenten UND Subagenten
- Wenn du Subagenten startest: jeder Subagent, der faktische Inhalte produziert,
  bekommt die explizite Anweisung „kein Fakt ohne abrufbare Quelle; im Zweifel
  ‚nicht belegbar‘ statt erfinden".
- Nach jedem Agenten-/Subagenten-Output, der Fakten enthält: **Selbstkontrolle
  gegen Halluzination** — stichprobenartig mindestens eine Quelle tatsächlich
  abrufen und prüfen, ob sie die Aussage stützt. Stützt sie nicht → Aussage
  verwerfen, nicht beschönigen.
- Der `skeptic`-Mechanismus (Cross-Model, neue unabhängige Quellen) ist die
  systemische Form davon — aber auch DU als bauender Agent prüfst deine eigenen
  Zwischenergebnisse mit demselben Misstrauen.

### 0.4 Skills situativ finden und nutzen
- **Bevor** du eine Aufgabe beginnst, prüfe: Gibt es ein passendes Skill für genau
  diese Tätigkeit? (z. B. Dokumenterstellung, Datenanalyse, Frontend, MCP-Server-Bau.)
- Wenn ja: lies das SKILL.md zuerst und nutze es. Skills enthalten umgebungs-
  spezifisches Wissen, das du sonst nicht hast.
- Tätigkeit → Skill prüfen → nutzen. Niemals „aus dem Gedächtnis" bauen, wenn ein
  Skill existiert. Das gilt für jede neue Tätigkeitsart im Verlauf des Auftrags.
- Wenn unklar ist, ob ein Skill existiert: aktiv suchen, bevor du anfängst.

---

## 1. AUFGABEN (in dieser Reihenfolge)

### Aufgabe 1 — Ledger-Implementierung
- Implementiere `src/gen/ledger/store.py` gegen das `LedgerStore`-Protocol.
- Backend: PostgreSQL nach `sql/001_ledger.sql`. Für Tests: eine In-Memory-
  Implementierung, die DIESELBEN Invarianten erzwingt (Quellenzwang!).
- Erzwinge: `add_claims` lehnt jeden Claim ohne Quelle ab (zusätzlich zum
  Konstruktor-Guard und DB-Constraint — drei Schichten).
- Tests: Quellenzwang, unabhängige-Quelle-Regel (View `v_non_independent_verifications`),
  Fetch-Aufzeichnung, Reproduzierbarkeit.
- **Selbstkontrolle 0.2 ausführen.**

### Aufgabe 2 — Cross-Model-Helfer
- Implementiere `src/gen/verification/cross_model.py`.
- Funktion, die sicherstellt: Verifier-Modellfamilie ≠ Generator-Modellfamilie,
  sonst `ModelConflictError` (siehe `core/errors.py`).
- Disagreement-Messung zwischen zwei Modell-Urteilen → senkt Confidence.
- Tests OHNE echte LLM-Calls (Modelle mocken), plus ein Negativtest
  (gleiche Familie → Error).
- **Selbstkontrolle 0.2 ausführen.**

### Aufgabe 3 — Tool-Adapter (Such-/Fetch-Backends)
- Implementiere Adapter gegen `Tool` und `SearchBackend`:
  Web-Search, Web-Fetch, mindestens ein akademisches Backend (Semantic Scholar
  hat freie API).
- Pflicht: ein Fetch-Fehler wird als `FetchFailedError` / `fetched_ok=False`
  behandelt — NIEMALS als erfolgreiche Quelle ausgegeben.
- Jeder erfolgreiche Fetch wird im Ledger via `record_fetch` protokolliert.
- Tests: Fehlschlag-Pfad explizit testen.
- **Selbstkontrolle 0.2 + Halluzinationsprüfung 0.3 ausführen.**

### Aufgabe 4 — Agenten (in dieser Reihenfolge: scout → scholar → skeptic → conductor)
Für JEDEN Agenten:
- Implementiere gegen das `Agent`-Protocol.
- Halte dich exakt an die Verantwortung/Grenzen der jeweiligen `docs/agents/*.md`
  (für `skeptic` existiert sie bereits; für die anderen lege sie an, gleicher Detailgrad).
- `scout`: nur Quellen-Kandidaten, keine Fakten.
- `scholar`: nur atomare Claims, jeder mit Quelle (sonst Konstruktor wirft).
- `skeptic`: Cross-Model, neue unabhängige Quellen, im Zweifel `UNSUPPORTED`.
- `conductor`: erzeugt SELBST keine Fakten; baut den Report nur aus Ledger-Claims.
- Tests je Agent mit gemockten Tools (positiv + negativ, inkl. „keine Quelle gefunden").
- **Nach JEDEM Agenten einzeln: Selbstkontrolle 0.2 + 0.3 ausführen.** Nicht alle
  vier bauen und dann einmal prüfen — nach jedem prüfen.

### Aufgabe 5 — End-to-End-Verdrahtung
- Verdrahte die Pipeline (Adapter zum gewählten Orchestrator hinter `core`).
- Einstieg: `run(question) -> Report` (CLI und/oder FastMCP — prüfe, ob ein
  MCP-Builder-Skill existiert und nutze es).
- Checkpointing + `run_id` + `config_hash` für Reproduzierbarkeit (Kriterium A5).
- **Selbstkontrolle 0.2 ausführen.**

### Aufgabe 6 — Akzeptanztest gegen die vier Frageklassen
- Lege `tests/fixtures/phase_alpha_questions.yaml` an: Klassen A (belegbar),
  B (Falle/falsche Vorannahme), C (unbelegbar), D (strittig).
- Fahre den echten End-to-End-Lauf. Prüfe gegen Akzeptanzkriterien
  `PHASE_ALPHA §5` (A1–A6).
- **A3 (Falle wird abgefangen) und A4 (Abstention) sind die wichtigsten.** Wenn
  die nicht bestehen, ist Phase α NICHT fertig — unabhängig davon, wie gut der Rest aussieht.
- Dokumentiere die Ergebnisse je Frageklasse in `docs/BUILD_LOG.md`.
- **Selbstkontrolle 0.2 + 0.3 ausführen.**

---

## 2. ABSCHLUSS DES AUFTRAGS (sauberes Ende)
- Alle Tests grün (`pytest -q`), keine offenen „nein" in der Selbstkontrolle.
- `docs/BUILD_LOG.md` enthält für jede Aufgabe einen Eintrag.
- Ein kurzes `docs/phases/PHASE_ALPHA_RESULT.md`: Welche Akzeptanzkriterien
  erfüllt, welche nicht, ehrlich. Bei nicht erfüllten: was fehlt konkret.
- **Keine Schönfärberei.** Wenn A3/A4 nur teilweise bestehen, schreib genau das.
  Eine ehrlich dokumentierte Lücke ist wertvoll; eine versteckte ist ein Risiko
  für das ganze Projekt.

---

## 3. ERINNERUNG AN DAS WARUM
Dieses System darf nicht halluzinieren — das ist sein einziger Existenzgrund.
Jede Abkürzung, die diese Garantie aufweicht, zerstört den Wert von allem
darüber. Lieber langsamer und beweisbar als schnell und unsicher. Groß denken,
hart bauen, niemals lügen.
