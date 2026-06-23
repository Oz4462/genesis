# DEPTH AUDIT — `pipelines/architekt.py`

**Modul:** `src/gen/pipelines/architekt.py`
**Headline-Anspruch (PLATFORM_PLAN §3.4 / 4.1):** „Aus dem Funken eine belastbare
Systemstruktur machen" — `map_to_system_concept(idea)` mappt eine Idee auf ein `SystemConcept`.
**Datum:** 2026-06-23 · **Aufgabe:** T04

---

## Verdikt

**Vorher: PARTIAL-FACADE.** Der reiche, ehrliche Output existierte NUR für den hartcodierten
Jetpack-Substring (`"jetpack" in idea.lower()` bzw. `"mensch"+"fliegen"`). Für jede andere Idee
lieferte der `else`-Zweig ein **fixes** Konzept, das die Eingabe `idea` nicht konsumierte:

- `requirements`, `assemblies`, `variants`, `open_decisions`, `zusammenfassung` waren für ALLE
  Nicht-Jetpack-Ideen byte-identisch → zwei verschiedene Ideen ergaben dasselbe Konzept (Facade).
- `idea` floss nur in `source_idea` (durchgereicht), nicht in den abgeleiteten Inhalt. Der
  Headline-Verb *„aus dem Funken machen"* hielt also nur für den einen kanonischen String.
- Leere/Whitespace-`idea` ergab still einen (sinnlosen) Stub statt lautem Fehler — ein
  fabrizierter Output für eine fehlende Eingabe (Verstoß gegen „keine stillen Defaults").

**Nachher: REAL (generischer Pfad).** Der generische Pfad leitet seinen Inhalt jetzt
nachweislich aus dem `idea`-Text ab; der Jetpack-Pfad bleibt als geschützter Spezialfall
verbatim erhalten.

---

## Was real gemacht wurde (nur Verhalten, keine Signaturänderung)

1. **Idee fließt in den Inhalt:** Der verbatim (stripped) `idea`-Text erscheint in einer
   Anforderung, im Zweck der Hauptbaugruppe, in den `open_decisions` und in der
   `zusammenfassung`. Zwei verschiedene Ideen ergeben damit *unterscheidbare* `SystemConcept`s.
2. **Ehrliche Abstinenz bleibt:** `open_decisions` markiert weiterhin explizit
   „needs full analysis" + „noch nicht im Detail abgeleitet" — es wird KEINE vollständige
   Fach-Analyse (detaillierte Anforderungen/Baugruppen) vorgetäuscht, die nicht durchgeführt wurde.
3. **Negativpfad:** leere/whitespace-`idea` → `ValueError` (kein fabrizierter Stub für eine
   Nicht-Eingabe). Im Docstring dokumentiert.
4. **Jetpack-Pfad unverändert:** 4 Anforderungen, 5 Baugruppen, 6 Varianten, 3 offene
   Entscheidungen, Signatur-Zusammenfassung — als Naht-geschützte Regression im Test gepinnt.

Die Signaturen von `SystemRequirement`, `AssemblyConcept`, `SystemConcept` und
`map_to_system_concept` sind **unverändert** (downstream-Importer wie `designer`,
`integrator`, `lumencrucible` kompilieren weiter; alle deren Tests bleiben grün).

## Tests (`tests/test_architekt_characterization.py`)

Facade-Killer (scheiterten am alten else-Zweig) + Regression + 2 Property-Tests (Hypothesis):

- zwei verschiedene generische Ideen → verschiedener Inhalt (Facade-Killer);
- `idea`-Text taucht in Anforderung UND Zusammenfassung auf;
- `open_decisions` bleibt ehrlich („needs full"/„noch nicht");
- leere/whitespace `idea` → `ValueError` (parametrisiert + Property);
- Jetpack-Pfad verbatim (4/5/6/3 + Signatur-Satz), „mensch+fliegen"-Trigger trifft denselben Pfad;
- Property: für jede non-blanke Nicht-Jetpack-Idee wird der Text konsumiert und das Konzept
  ist wohlgeformt + ehrlich-abstinent.

**11 Tests grün.** Vollständige Suite der Architekt-Konsumenten (architekt, designer,
integrator, techniker, …) bleibt grün; die 2 `test_lumencrucible.py`-Fehler sind
**vorbestehend auf der Baseline** (per `git stash` verifiziert) und unabhängig von dieser Änderung.

## 4 Linsen

- **L1 (Wahrheit):** Der Output folgt jetzt aus der Eingabe, nicht aus einer Konstante; ohne
  Eingabe ehrlicher `ValueError` statt geratenem Stub. `quelle`/`run_id`-Provenance bleibt.
- **L2 (Drift):** Headline „aus dem Funken eine Systemstruktur" deckt sich jetzt mit dem Code
  für JEDE Idee, nicht nur Jetpack. Keine stillen Defaults mehr (Kernprinzip).
- **L3 (Vollständigkeit/Naht):** Jetpack-Pfad als Naht-geschützte Regression erhalten;
  öffentliche Dataclass-Signaturen byte-stabil → downstream-Pipelines bleiben kompatibel.
- **L4 (Realisierbarkeit):** Edge-Cases (leere/whitespace-Idee, Idee mit Anführungszeichen,
  zwei-Ideen-≠-eine-Map) abgedeckt; deterministisch; keine neue Dependency außer Hypothesis
  (Test-only, bereits deklariert).

**Offen / nächster Stein:** echte Anforderungs-/Baugruppen-Ableitung aus den prior
Grenz-Outputs (statt Idee-Spiegelung) — in `open_decisions` ehrlich als „needs full analysis"
vermerkt.
