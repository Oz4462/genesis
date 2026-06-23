# DEPTH AUDIT — `pipelines/software.py`

**Modul:** `src/gen/pipelines/software.py`
**Headline-Anspruch (PLATFORM_PLAN §4):** „deterministischer Mapper von SystemConcept
(+ Elektriker/Techniker prior) zu SoftwareSpec" — Steuerung, Embedded, APIs, Tests,
Updatefähigkeit, Fehlerzustände.
**Datum:** 2026-06-23 · **Aufgabe:** T04

---

## Verdikt

**Vorher: PARTIAL-FACADE.** Der reiche, ehrliche Output existierte NUR für den hartcodierten
Substring (`"jetpack" in idee` bzw. `"flug"`). Für jede andere Idee lieferte der `else`-Zweig
eine **fixe** `SoftwareSpec`, die `concept` und `ingenieur` nicht konsumierte:

- immer genau eine `MainController`-Komponente, eine `BasicAPI` (`input="none"`),
  eine `UpdatePfad("Manual flash", "No rollback (Lücke)", …)` und ein einzeiliger Testplan —
  byte-identisch für ALLE Nicht-Jetpack-Ideen → zwei verschiedene Ideen ergaben dieselbe Spec.
- `concept.main_assemblies` und `ingenieur.failure_modes` flossen NIRGENDS in den Output —
  der Headline-Anspruch „Mapper von <inputs> zu Spec" hielt nur für den einen Kanon-String.
- `rollback="No rollback"` wurde als analysiertes Faktum behauptet, obwohl keine
  Rollback-Analyse stattfand (Verstoß gegen „keine stillen Defaults" / „kein fabriziertes Faktum").
- leere/blanke Idee ohne Baugruppen ergab still denselben Stub statt eines lauten Fehlers.

**Nachher: REAL (generischer Pfad).** Der generische Pfad leitet seinen Inhalt jetzt
nachweislich aus `concept.main_assemblies`, `concept.source_idea` und `ingenieur.failure_modes`
ab; der Jetpack-Pfad bleibt byte-stabil.

---

## Was real gemacht wurde (nur Verhalten, keine Signaturänderung)

1. **Embedded aus Baugruppen:** je steuerungs-relevanter `AssemblyConcept` (Heuristik
   `_needs_control` über Name/Zweck/Interfaces) entsteht eine `EmbeddedComponent`. Rein
   strukturelle Baugruppen (z. B. „Rahmen", „Liegefläche") werden NICHT zu Controllern
   (keine Fabrikation). Gibt es keine, fällt der Code ehrlich auf einen `SystemMonitor` mit
   deklarierter Lücke zurück.
2. **Fehlerzustände aus Ingenieur:** `_failure_states_for` mappt jede `FailureMode`, deren
   `aus_baugruppe` zur Baugruppe passt, in die `fehler_zustaende` der Komponente — plus den
   universellen `comm_loss`-Baseline. Gate-Intent „no unhandled failure state" ist erfüllt:
   jede Komponente listet ≥1 Fehlerzustand.
3. **Testplan aus Failure-Modes:** je deklariertem `FailureMode` ein Fault-Injection-Eintrag
   (mit Detection); ohne Failure-Modes eine explizite Lücke statt eines erfundenen Tests.
4. **API mit Kontrakt:** eine `StatusAPI` über die abgeleiteten Komponenten mit nicht-leerem
   `input`/`output`/`sicherheit` (Gate „no API without contract"); Befehls-/Schreib-Pfad als
   explizite Lücke markiert, nicht still behauptet.
5. **Update/Rollback ehrlich:** `rollback="UNBEKANNT — Rollback-Fähigkeit nicht analysiert
   (explizite Lücke)"` statt des alten geratenen `"No rollback"`.
6. **Zusammenfassung spiegelt die echte `source_idea`** + Komponenten-/API-/Failure-Mode-Zahl.
7. **Negativpfad:** blanke `source_idea` UND leere `main_assemblies` → `ValueError`
   (kein fabrizierter Stub für eine nicht-vorhandene Eingabe). Im Docstring dokumentiert.

Die Signaturen von `EmbeddedComponent`, `APISpec`, `UpdatePfad`, `SoftwareSpec` und
`map_to_software_spec` sind **unverändert** (downstream-Importer `integrator`, `lumencrucible`,
`lernmaschine` kompilieren weiter; ihre Tests bleiben unverändert grün bzw. pre-existing rot).

## Beobachteter, bewusst NICHT geänderter Defekt (out of scope)

Der Jetpack-Zweig enthält einen pre-existing Tippfehler: `update = UpdatePfad(...),` (Komma am
Zeilenende) wickelt `update_pfad` in ein 1-Tupel statt eines `UpdatePfad`. Da die Aufgabe den
Jetpack-Zweig **byte-stabil** verlangt, wird er nicht angefasst; der Regressionstest prüft
robust über `str(spec.update_pfad)` (wie der Legacy-Test). Empfehlung für einen separaten Task:
das Komma entfernen.

## Tests (`tests/test_software_characterization.py`)

Facade-Killer (scheiterten am alten else-Zweig) + Regression + 1 Property-Test (Hypothesis):

- zwei verschiedene generische Ideen → verschiedene Komponenten-Namen, Zusammenfassung UND
  Testplan; Failure-Modes landen in der richtigen Komponente + im Testplan (Facade-Killer);
- steuerungs-relevante Baugruppe → Komponente, strukturelle Baugruppe → keine;
- Gate: jede Komponente ≥1 Fehlerzustand, jede API mit nicht-leerem Kontrakt;
- Update-Rollback ist explizite Lücke, nie still „No rollback";
- blanke Idee + keine Baugruppen → `ValueError`; blanke Idee MIT Baugruppen funktioniert;
- keine Steuer-Baugruppe → ehrlicher `SystemMonitor`-Fallback mit Lücke;
- Jetpack-Pfad verbatim (Thrust/Tether/overtemp/GroundTelemetry/4er-Testplan, Signatur-Satz);
- Property: jede non-blanke Nicht-Jetpack-Idee wird konsumiert, alle Gate-Invarianten halten.

**15/15 Tests grün** (inkl. Legacy `test_software.py`). `test_integrator.py` grün.
Die 2 `test_lumencrucible.py`-Fehler sind **pre-existing auf der Baseline** (per `git stash`
verifiziert) und unabhängig von dieser Änderung.

## 4 Linsen

- **L1 (Wahrheit):** Der Output folgt jetzt aus `concept`/`ingenieur`, nicht aus einer
  Konstante; Rollback wird als unbekannt deklariert statt falsch behauptet; ohne Eingabe
  lauter `ValueError`.
- **L2 (Drift):** Headline „Mapper von <inputs> zu Spec" deckt sich jetzt mit dem Code für
  JEDE Idee, nicht nur Jetpack. Keine stillen Defaults / kein fabriziertes Faktum mehr.
- **L3 (Vollständigkeit/Naht):** Jetpack-Pfad als geschützte Regression byte-stabil;
  öffentliche Dataclass-Signaturen unverändert → integrator/lumencrucible/lernmaschine bleiben
  kompatibel. Gate-Intent (≥1 Fehlerzustand, API mit Kontrakt) im Code erzwungen + getestet.
- **L4 (Realisierbarkeit):** Edge-Cases (blanke Idee ±Baugruppen, keine Steuer-Baugruppe,
  fehlende Failure-Modes, Idee mit Sonderzeichen via Property) abgedeckt; deterministisch;
  keine neue Dependency außer Hypothesis (Test-only, bereits deklariert).

**Offen / nächster Stein:** echte Steuer-Architektur aus Elektriker-/Techniker-Prior (Signale,
Wartung/Update) statt Baugruppen-Heuristik — in den Lücken-Strings ehrlich vermerkt.
