# PHASE α — Anti-Halluzinations-Fundament

> **Zweck dieser Datei:** Vollständige, operative Spezifikation der ersten Stufe. So detailliert, dass Claude Code ohne Rückfragen implementieren kann und jede Entscheidung gegen ein Akzeptanzkriterium prüfbar ist.
>
> **Warum diese Stufe zuerst:** Wenn das System halluziniert, ist jede weitere Fähigkeit (Ideation, CAD, Simulation) wertlos — sie würde auf Lügen aufbauen. Anti-Halluzination ist nicht ein Feature, sondern das Fundament. Wir beweisen es isoliert, bevor wir darauf bauen.

---

## 1. Was Phase α leistet (Scope)

**Input:** Eine Problem-/Frage-Formulierung eines Menschen (Text).
**Output:** Ein *Recherche-Bericht*, in dem **jede faktische Behauptung** an einen Ledger-Eintrag mit ≥1 abrufbarer Quelle gebunden ist und einen Verifikations-Status trägt.

**In Scope:**
- Intake einer Frage
- Breite Recherche (`scout`)
- Tiefe Quellenlesung + Faktenextraktion (`scholar`)
- Unabhängige Verifikation jedes Fakts (`skeptic`, Cross-Model)
- Fakten-Ledger mit Quellenzwang
- Ein Verifikations-Gate, das den Bericht nur durchlässt, wenn die Gate-Bedingung erfüllt ist
- Reproduzierbarer Lauf (run_id, Checkpoint, Logs)

**Explizit NICHT in Scope (kommt in späteren Phasen):**
- Ideengenerierung, Lösungsvorschläge (Phase β)
- CAD/Spezifikation (Phase γ)
- Simulation (Phase δ)
- Selbstlernen (Phase ζ)
- GUI (CLI/MCP genügt für α)

---

## 2. Datenfluss (Phase α)

```
                    ┌──────────────────────────────────────────────┐
   Mensch ──Frage──▶│ conductor (Orchestrator)                      │
                    │  - erzeugt run_id, init State                 │
                    └───────┬──────────────────────────────────────┘
                            │ Claim-Anforderung: "belege Fakten zu X"
                            ▼
                    ┌───────────────┐   roh: Kandidaten-Quellen
                    │ scout         │──────────────┐
                    │ (Breite)      │              │
                    └───────────────┘              ▼
                                           ┌───────────────┐
                                           │ scholar       │  liest Primärquellen,
                                           │ (Tiefe)       │  extrahiert ATOMARE Fakten
                                           └───────┬───────┘
                                                   │ Claim(text, source[], span)
                                                   ▼
                                           ┌───────────────┐
                                           │  LEDGER       │  speichert jeden Claim
                                           │  (status=     │  als UNVERIFIED
                                           │   UNVERIFIED) │
                                           └───────┬───────┘
                                                   │ alle UNVERIFIED claims
                                                   ▼
                                           ┌───────────────┐
                                           │ skeptic       │  ANDERES Modell.
                                           │ (Verifikator) │  Versucht jeden Claim zu
                                           │  Cross-Model  │  widerlegen / unabh. zu stützen
                                           └───────┬───────┘
                                                   │ status ∈ {VERIFIED, REFUTED,
                                                   │           UNSUPPORTED}
                                                   ▼
                                           ┌───────────────┐
                                           │  GATE α        │ Bedingung prüfen (s.u.)
                                           └───────┬───────┘
                                bestanden ─────────┤───────── nicht bestanden
                                          ▼                         ▼
                                  Bericht an Mensch        zurück an scout/scholar
                                  (nur VERIFIED +          (gezielt nachrecherchieren)
                                   markierte Lücken)       oder als Lücke ausweisen
```

---

## 3. Die Agenten in Phase α

Jeder Agent erfüllt das `Agent`-Protocol (`core/interfaces.py`). Detail-Prompts in `docs/agents/`.

### 3.1 `conductor`
- **Aufgabe:** Lauf initialisieren, Frage in recherchierbare Teilfragen zerlegen, Sub-Agents in Reihenfolge aufrufen, State halten, Gate auslösen, Endbericht zusammenstellen.
- **Halluzinations-Regel:** `conductor` erzeugt **selbst keine Fakten**. Er orchestriert nur. Jede faktische Aussage muss aus dem Ledger stammen.
- **Input:** `Question`
- **Output:** `Report` (nur aus Ledger-Einträgen zusammengesetzt)

### 3.2 `scout` (Breite)
- **Aufgabe:** Zu jeder Teilfrage breit Kandidaten-Quellen finden (Web, arXiv, PubMed, Semantic Scholar, Patente, GitHub). Sammelt URLs/IDs + Kurzbegründung der Relevanz. **Extrahiert noch keine Fakten** — nur Quellen-Kandidaten.
- **Tools:** `web_search`, `academic_search`, `web_fetch`
- **Halluzinations-Regel:** Gibt nur Quellen zurück, die tatsächlich abgerufen wurden. Eine Quelle, die nicht geladen werden konnte, wird als `fetch_failed` markiert, nicht erfunden.
- **Input:** `SubQuestion`
- **Output:** `list[SourceCandidate]`

### 3.3 `scholar` (Tiefe)
- **Aufgabe:** Kandidaten-Quellen **vollständig lesen** (nicht nur Snippets), und daraus **atomare Fakten** (Claims) extrahieren. Ein Claim = eine einzelne, einzeln prüfbare Aussage. Jeder Claim trägt: Quelle(n), Textstelle/Span, wörtliches Stützzitat-Minimum (kurz!), eigene Confidence.
- **Tools:** `web_fetch`, Dokument-Reader
- **Halluzinations-Regel:** Ein Claim, der nicht direkt aus der gelesenen Quelle ableitbar ist, darf nicht entstehen. Interpolation/„allgemeines Wissen" ist verboten — wenn die Quelle es nicht sagt, gibt es keinen Claim.
- **Input:** `list[SourceCandidate]`, `SubQuestion`
- **Output:** `list[Claim]` (Status beim Erzeugen immer `UNVERIFIED`)

### 3.4 `skeptic` (Verifikator — das Herz)
- **Aufgabe:** Jeden `UNVERIFIED`-Claim unabhängig prüfen. Drei mögliche Ausgänge:
  - `VERIFIED` — durch ≥1 **unabhängige** weitere Quelle gestützt **oder** Primärquelle eindeutig und vertrauenswürdig.
  - `REFUTED` — eine glaubwürdige Quelle widerspricht.
  - `UNSUPPORTED` — keine unabhängige Stützung gefunden; bleibt eine unbelegte Behauptung.
- **Pflicht-Mechanismus Cross-Model:** `skeptic` läuft auf einer **anderen Modellfamilie** als `scholar`. Begründung: Single-Family-Bias. Bei Uneinigkeit zwischen Modellen → niedrigere Confidence, ggf. zweiter Judge.
- **Pflicht-Mechanismus Unabhängigkeit:** Eine Quelle, die schon `scholar` genutzt hat, zählt für `skeptic` **nicht** als unabhängige Bestätigung. `skeptic` muss neue Quellen suchen.
- **Tools:** `web_search`, `web_fetch`, `academic_search` — **eigene** Suchen, nicht scholar's Quellen wiederverwenden.
- **Input:** `list[Claim]` (UNVERIFIED)
- **Output:** `list[Claim]` (Status gesetzt, Verifikations-Quellen angehängt, Confidence aktualisiert)

---

## 4. Das Verifikations-Gate (GATE α)

Das Gate ist als reine Funktion implementiert (`verification/gates.py`), testbar ohne LLM.

### Gate-Bedingung (konfigurierbar, Defaults unten)
Der Bericht passiert das Gate **nur wenn alle** Bedingungen erfüllt sind:

1. **Keine versteckten Fakten:** Jeder faktische Satz im Berichtsentwurf ist auf einen Ledger-Claim gemappt. (Kein Claim → Satz wird entfernt oder Gate schlägt fehl.)
2. **Kein REFUTED im Bericht:** Claims mit Status `REFUTED` dürfen nicht als Tatsache auftauchen (höchstens explizit als „widerlegt" benannt).
3. **UNSUPPORTED nur als solches markiert:** `UNSUPPORTED`-Claims dürfen erscheinen, aber **nur** explizit gekennzeichnet als „unbelegt / Annahme".
4. **Mindest-Confidence für VERIFIED:** `confidence ≥ τ` (Default τ = 0.7).
5. **Quellen abrufbar:** Jede zitierte Quelle hat einen erfolgreichen Fetch im Ledger (kein „toter" Verweis).

### Bei Nicht-Bestehen
- `conductor` entscheidet pro fehlerhaftem Claim: gezielt nachrecherchieren (zurück an scout/scholar, begrenzte Runden) **oder** als Lücke ausweisen.
- Es gibt ein **Runden-Limit** (Default 3), um Endlosschleifen zu vermeiden. Danach: Bericht mit explizit ausgewiesenen Lücken.

---

## 5. Akzeptanzkriterien Phase α (so wird „fertig" gemessen)

Phase α gilt als bestanden, wenn auf einem festen Test-Set von Fragen:

| # | Kriterium | Messung | Zielwert |
|---|---|---|---|
| A1 | **Null unbelegte Fakten** im finalen Bericht | manuelle + automatische Prüfung: jeder faktische Satz ↔ Ledger-Claim mit Quelle | 100 % |
| A2 | **Erfundene Quellen = 0** | jede Quelle muss erfolgreich gefetcht worden sein | 0 erfundene |
| A3 | **Bekannte Falschaussage wird abgefangen** | Test-Fragen mit eingebauter Falle (Frage impliziert Falschannahme) → System markiert REFUTED/UNSUPPORTED statt zu bestätigen | 100 % der Fallen |
| A4 | **Abstention funktioniert** | Frage ohne belegbare Antwort → System sagt „nicht belegbar", erfindet nichts | 100 % |
| A5 | **Reproduzierbarkeit** | gleicher run_id + Config + Ledger-Snapshot → gleicher Bericht | deterministisch |
| A6 | **Cross-Model aktiv** | Log beweist: skeptic-Modell ≠ scholar-Modell | erfüllt |

> **A3 und A4 sind die wichtigsten.** Sie messen genau das, was du als Kernproblem benannt hast: dass das System nicht „irgendwas schreibt", sondern Lücken und Fallen erkennt.

---

## 6. Test-Set (Beispiel-Struktur)

`tests/fixtures/phase_alpha_questions.yaml` enthält Fragen in vier Klassen:
- **Klasse A — belegbar/wahr:** klare Antwort existiert (z.B. „Welcher CAD-Kernel liegt build123d und CadQuery zugrunde?" → OCCT/Open Cascade).
- **Klasse B — Falle:** Frage enthält falsche Vorannahme („Warum ist X die einzige Methode für Y?" wo X nicht einzig ist).
- **Klasse C — unbelegbar:** keine seriöse Quelle (Spekulation über Zukunft, private Daten).
- **Klasse D — strittig:** Quellen widersprechen sich → System muss Dissens abbilden, nicht eine Seite erfinden.

Jede Frage hat erwartetes Verhalten (nicht erwartete Wortlaute, sondern erwartete *Status*).

---

## 7. Konfiguration (Defaults)

`config.yaml`:
```yaml
phase_alpha:
  confidence_threshold: 0.7      # τ für VERIFIED
  max_refine_rounds: 3           # Anti-Endlosschleife
  require_independent_source: true
  min_sources_for_verified: 2    # außer eindeutige Primärquelle
  models:
    generator: "<modellfamilie A>"   # scout, scholar
    verifier:  "<modellfamilie B>"   # skeptic  (MUSS ≠ generator)
    judge:     "<modellfamilie C>"   # optionaler zweiter Judge bei Dissens
  search_backends: [web, arxiv, pubmed, semantic_scholar]
```

---

## 8. Was Claude Code in Phase α konkret baut (Reihenfolge)

1. `core/interfaces.py` — Protocols: `Agent`, `Tool`, `LedgerStore`, `Gate`.
2. `core/state.py` — `RunState`, `Question`, `SubQuestion`, `SourceCandidate`, `Claim`, `Report` (+ Enums für Status).
3. `core/errors.py` — typisierte Fehler (FetchFailed, NoIndependentSource, ModelConflict, ...).
4. `sql/001_ledger.sql` — Ledger-Tabellen + Constraints (Quellenzwang als DB-Constraint).
5. `ledger/store.py` — Ledger-Implementierung gegen das `LedgerStore`-Protocol.
6. `verification/gates.py` — `gate_alpha()` als reine, getestete Funktion.
7. `verification/cross_model.py` — Cross-Model-Judging-Helfer.
8. `agents/scout.py`, `agents/scholar.py`, `agents/skeptic.py`, `agents/conductor.py`.
9. `tests/` — zuerst Gate-Tests (A1–A6), dann Agent-Tests mit gemockten Tools.
10. CLI/MCP-Einstieg: `run(question) -> Report`.

> **Reihenfolge-Begründung:** Erst Datenmodell + Ledger + Gate (alles testbar OHNE LLM), dann Agenten. So ist das Anti-Halluzinations-Skelett beweisbar korrekt, bevor ein einziger LLM-Token fließt.

---

## 9. Offene Detailentscheidungen für Phase α (bewusst markiert)
- Konkrete Modellfamilien A/B/C — abhängig von Budget/lokaler Inferenz (Ollama auf 1080 Ti für günstige Teilschritte denkbar).
- Vektor-DB: pgvector (auf vorhandener TimescaleDB) vs. Qdrant — für α genügt pgvector.
- `academic_search`-Backends: welche APIs zuerst (Semantic Scholar hat freie API).
Diese sind in α **nicht blockierend** — Interfaces sind so geschnitten, dass die konkrete Wahl hinter Adaptern austauschbar bleibt.
