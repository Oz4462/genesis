# DEPTH AUDIT — `grenzverschiebung/teststand_architect.py`

**Modul:** `src/gen/grenzverschiebung/teststand_architect.py`
**Headline-Anspruch (PLATFORM_PLAN §3.3):** „Baut Prüfstände statt riskanter
Direktversuche" — Output ist ein `TestStandPlan` aus messbaren, sicheren `TestStandSpec`,
abgeleitet aus den realen Meilensteinen der `MilestoneLadder`.
**Datum:** 2026-06-23 · **Aufgabe:** T03

---

## Verdikt

**Vorher: PARTIAL-FACADE.** Der reiche, ehrliche Output (3 kuratierte Stands T0–T2)
existierte NUR für den hartcodierten Jetpack-Substring (`"jetpack" in traum` bzw.
`"mensch"+"fliegen"`). Für jede andere Leiter lieferte der `else`-Zweig EINEN fixen
`TestStandSpec` („T0 — Frontier Mapping Validation Rig"):

- `ladder.milestones` wurde im generischen Pfad **nie gelesen** — zwei völlig
  verschiedene Leitern ergaben denselben Plan (reine Facade, „stiller Default").
- `definition_of_done` und `risiken` der Meilensteine flossen **nirgends** in
  `messungen`/`sicherheitsmassnahmen` ein.
- Eine **leere** Leiter (`milestones == []`) erzeugte trotzdem einen erfundenen
  Stand statt ehrlich abstinent zu sein.

**Nachher: REAL (generischer Pfad).** Der headline-Verb *Prüfstände bauen* konsumiert
die Leiter jetzt nachweislich; der Jetpack-Pfad bleibt als geschützter Spezialfall
byte-stabil erhalten.

---

## Was real gemacht wurde (nur Verhalten, keine Signaturänderung)

1. **Ein Prüfstand pro realem Meilenstein** — der generische Zweig iteriert über
   `ladder.milestones`; jeder Stand zitiert seinen Meilenstein in `name`,
   `beschreibung` und `quelle` (Provenance).
2. **DoD → Messungen** (`_messungen_from_milestone`): jede `definition_of_done` IST
   das messbare Erfolgskriterium und wird zu einer Messung. Whitespace wird verworfen;
   ein Meilenstein OHNE messbare DoD wird ehrlich als `LÜCKE: … nicht prüfbar`
   markiert (keine fabrizierte Messung).
3. **Risiken → Sicherheitsmassnahmen** (`_sicherheit_from_milestone`): jedes
   deklarierte Risiko begründet eine konkrete Absicherung; ohne Risiko bleibt nur die
   ehrliche Boden-/Abbruch-Baseline (kein erfundenes Risiko).
4. **Ehrliche Abstinenz:** leere `ladder.milestones` → `stands == []` und eine
   `zusammenfassung`, die explizit sagt, dass keine Meilensteine geliefert wurden
   (kein kanonischer Stub).
5. **`dauer_aufwand`** verweist auf das `naechstes_experiment` des Meilensteins —
   auch dieses Feld wird konsumiert.

Signaturen von `TestStandSpec`, `TestStandPlan` und `build_test_stand` sind
**unverändert**; der Jetpack-Zweig ist wortgleich erhalten (geschützte Regression).

## Tests (`tests/test_teststand_architect_characterization.py`)

Facade-Killer (scheiterten am alten else-Zweig) + Regression + Property-Test (Hypothesis):
ein Stand pro Meilenstein mit aus DoD/Risiken abgeleiteten Feldern, zwei-Leitern-≠-Plan,
mehr-Meilensteine-≠-mehr-Stands, ehrliche Abstinenz bei leerer Leiter, LÜCKE-Markierung
ohne DoD, Baseline-Sicherheit ohne Risiko, Whitespace-Filter, intakter Jetpack-Pfad,
Property „jeder Meilenstein → genau ein Stand mit Provenance". **11 Tests grün**
(inkl. der 2 bestehenden in `test_teststand_architect.py`).

## 4 Linsen

- **L1 (Wahrheit):** Messungen/Sicherheit folgen aus dem Meilenstein-Inhalt, nicht aus
  einem geratenen Default; ohne Signal ehrliche LÜCKE bzw. leere `stands`. Provenance
  bleibt erhalten.
- **L2 (Drift):** Headline „Prüfstände bauen" deckt sich jetzt mit dem Code für JEDE
  Leiter, nicht nur Jetpack. Keine stillen Defaults mehr (Kernprinzip).
- **L3 (Vollständigkeit/Naht):** DoD und Risiken jedes Meilensteins werden konsistent
  geführt; Jetpack-Pfad als Naht-geschützte Regression erhalten; öffentliche Signaturen
  byte-stabil → Konsumenten (`safety_ladder`, `technology_roadmapper`,
  `bench_test_runner`) bleiben grün.
- **L4 (Realisierbarkeit):** Edge-Cases (leere Leiter, fehlende DoD, fehlende Risiken,
  Whitespace) sind abgedeckt; deterministisch, keine neuen Dependencies außer Hypothesis
  (Test-only, bereits deklariert).

**Offen / nächster Stein:** echte Sicherheits-/Mess-Typisierung (tethered/Wasser/Scale)
auch im generischen Pfad ableiten statt nur DoD/Risiken zu spiegeln; volle Integration
mit `technology_builder` + `bench_test_runner` + Wissensbasis.
