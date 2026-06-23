# Depth-Audit: `src/gen/pipelines/techniker.py` (T05)

**Verdikt vor Fix: FACADE.** **Verdikt nach Fix: REAL (generischer Pfad input-getrieben).**

## Befund (Facade-Smell)

`map_to_techniker_spec(concept, ingenieur, physiker)` hatte zwei Pfade:

- **Jetpack-Branch** (`'jetpack' in idea or any('jetpack' in a.name ...)`): reichhaltig, 4 konkrete Montageschritte (Tether-Anchor-Plate, Recovery, Bohrungen, Endkontrolle), detaillierte Werkzeug-, Zugangs-, Fehler- und Prüflisten. → REAL für diesen Kanon.
- **Generischer `else`-Branch**: gab **fixe** Werte zurück
  - immer exakt ein `MontageSchritt("Grundplatte vorbereiten", … ["Schleifer"], …)`
  - `werkzeug_liste = ["Schleifer"]`
  - `pruef_schritte = ["Endkontrolle"]`, `wartungs_plan=["Grundwartung"]`, `reparatur_hinweise=["Austausch"]`
  - `zusammenfassung = "Minimal TechnikerSpec für noch nicht detailliert analysierte Idee."`
  Diese Werte ignorierten `concept`, `ingenieur` **und** `physiker` vollständig (außer der Kopie von `source_idea` in den Top-Level-Feldern).
  Zwei beliebige Nicht-Jetpack-Inputs produzierten identischen Output. Die Headline „deterministischer Mapper von SystemConcept + IngenieurSpec + PhysikerSpec zu TechnikerSpec" galt nur für den Jetpack-String.
  → Verstoß gegen „keine stillen Defaults bei faktischen Dingen" + „jede Behauptung lebt im Fakten-Ledger".

Zusätzlich fehlte der dokumentierte Fail-Loud-Pfad: docstring versprach ValueError bei negativem Thrust-ähnlichem (hier: fehlendem Signal), aber ein leerer/blanker Input erzeugte den Stub.

## Fix (input-getrieben + ehrliche Lücke + Gate)

Neue Hilfsfunktion `_derive_generic_techniker_spec(concept, ingenieur, physiker)` leitet jetzt aus den **tatsächlichen** prior-Stein-Feldern ab:

- **Montage-Plan**: 1:1 aus `concept.main_assemblies` (jede Assembly → `MontageSchritt` mit name=`Montage {name}`, beschreibung aus purpose+interfaces, input/output/check).
- **Werkzeuge pro Schritt**: aus `ingenieur.cad_anforderungen` + `toleranzen` (zyklisch, dedupliziert); Top-Level `werkzeug_liste` ist die Vereinigung aller referenzierten Werkzeuge.
- **Typische Fehler**: matching aus `ingenieur.failure_modes` (Name/Baugruppe-Overlap) oder explizites `Lücke: keine typischen Fehler aus Ingenieur-Failure-Modes für diese Baugruppe`.
- **Prüfschritte**: direkt 1:1 aus `physiker.falsifikations_plan` (`{name}: Erwartete Messgröße '{erwartete_messgroesse}' messen. Abbruch bei: {abbruchkriterium}`) oder `Lücke`.
- **Wartung/Reparatur**: aus vorhandenen `failure_modes` (Periodische Prüfung auf … / Bei Auftreten von …) oder `Lücke`.
- **Zusammenfassung**: reflektiert wörtlich `source_idea`, Zählungen von Assemblies/FM/FPs, Ableitungsquelle und Markierung von Lücken.
- **Gate-Einhaltung** (durch Konstruktion):
  - Jeder Schritt hat `input`, `output`, `pruefpunkt`.
  - Jeder in einem Schritt referenzierte Tool-String steht in `werkzeug_liste`.
- **Abstention bei fehlendem Signal**:
  - `source_idea.strip() == ""` **und** `len(main_assemblies) == 0` → `ValueError` (exakte Nachricht dokumentiert, kein Stub).
  - Idea vorhanden, aber keine Assemblies → ein expliziter Lücke-Schritt (kein "Grundplatte"-Canned).
  - Fehlende FM/FPs/CAD-Hints → `Lücke:`-Marker in den betroffenen Listen (keine fabrizierte Sicherheit/Prozedur).

Der **Jetpack-Branch ist byte-identisch erhalten** (protected regression).

## Welche Inputs werden jetzt genuin konsumiert?

| Output-Feld          | abgeleitet aus |
|----------------------|----------------|
| `montage_plan[*].{name,beschreibung,input,output,pruefpunkt,zugang,typische_fehler}` | `concept.main_assemblies[*].{name,purpose,interfaces,quelle}` + matching `ingenieur.failure_modes` |
| `montage_plan[*].werkzeuge` + `werkzeug_liste` | `ingenieur.cad_anforderungen` + `ingenieur.toleranzen` |
| `pruef_schritte`     | `physiker.falsifikations_plan[*].{name,erwartete_messgroesse,abbruchkriterium}` |
| `wartungs_plan` / `reparatur_hinweise` | `ingenieur.failure_modes[*].{name,aus_baugruppe,beschreibung,detection}` |
| `zusammenfassung`    | `concept.source_idea`, `#assemblies`, `#failure_modes`, `#falsifikations_plan` |
| `source_idea`        | verbatim aus `concept` (unverändert) |

## Test-Beleg (`tests/test_techniker_characterization.py`)

- **Facade-Killer**: zwei distinkte Nicht-Jetpack-Inputs (verschiedene Assemblies + Failure-Modes + CAD-Hints) → distinkte `montage_plan` Namen und Inhalte; Input-Namen (`"Greifer"`, `"Motor blockiert"`, `"Bohrmaschine"`) tauchen nur im richtigen Spec auf.
- **Input-Fluss**:
  - Assembly-Namen → Montage-Namen + Beschreibung + Input/Output.
  - CAD/Tol-Strings → Werkzeuge in Schritten + Liste.
  - Physiker-Falsi → Pruef-Schritte (Name + Messgröße + Abbruch).
  - FM → `typische_fehler` (matching) + Wartung/Reparatur.
- **Gate-Tests**: jeder Schritt hat input/output/pruefpunkt; `step.werkzeuge ⊆ werkzeug_liste`.
- **Negativtest (ValueError)**: leerer source_idea + keine Assemblies → exakter `ValueError` mit der dokumentierten Nachricht.
- **Honest-Gap**: Idea vorhanden, Assemblies leer → Lücke-Schritt (kein Canned).
- **Protected Regression**: Jetpack-Branch liefert exakt 4 Montage, 5 Werkzeuge, 3 Prüf, 3 Wartung, 3 Reparatur + originale Namen/Inhalte.
- **Property-based (Hypothesis)**: für beliebige (jetpack/flug-freie) Mengen von Assemblies + FMs gilt: `#montage == #assemblies` (oder 1 Lücke), und jeder Input-Name erscheint exakt in den abgeleiteten Listen (kein stilles Verschlucken, keine Fabrikation).
- **Real-Mapper Regression**: generische Idee über die echten `map_to_system_concept` + ingenieur + physiker → abgeleiteter (nicht-konstanter) TechnikerSpec.

## 4 Linsen

- **L1 Wahrheit**: keine erfundenen Montage-Prozeduren, Werkzeuge oder Prüfschritte mehr; alles entweder aus Input-Feldern abgeleitet oder als `Lücke:` deklariert. Kein stiller Default.
- **L2 Drift**: Headline („aus SystemConcept + IngenieurSpec + PhysikerSpec ableiten") deckt sich jetzt mit dem Code für *alle* Inputs, nicht nur den Jetpack-Kanon. Der generische Pfad ist deterministisch und reproduzierbar.
- **L3 Vollständigkeit/Naht**: Naht zu CAD/DFM (via cad_anf/tol), Manufacturing-Check, Prüfständen und Realisierungspaketen bleibt erhalten; Jetpack-Demo unangetastet (L3 seam check bestanden). Keine Änderung an Dataclass-Signaturen.
- **L4 Realisierbarkeit/Edge**: leerer Input + keine Assemblies → lauter ValueError (nicht Crash oder Fake); nur-Assemblies- und nur-FM-Pfade; fehlende CAD/FPs → ehrliche Lücken; Tool-Gate und Schritt-Integrität (input/output/check) durch Konstruktion + explizite Tests gesichert. Keine blanket NaN/Inf-Guards (per Scope).

## Backlog-Bezug

`GENESIS_PLATFORM_PLAN.md §4.4` (Techniker-Pipeline, vierter Stein). Die Umsetzung erfüllt die Anforderung eines „deterministischen Mappers" für alle Inputs und das Gate „jeder Schritt hat Input, Output und Check; kein Schritt verlangt ein nicht vorhandenes Werkzeug".

Offen (ehrlich als Lücke markiert):
- Detaillierte Zugänglichkeits-/Erreichbarkeitsanalysen (CAD/DFM nötig).
- Konkrete Lieferanten-spezifische Werkzeug- und Material-Hinweise (Wissensbasis + costing später).
- Volle Integration in `realize`/`bundle`/`packager` (nachgeliefert durch Integrator).

Der Audit ist pro Modul isoliert und kollidiert nicht mit parallel laufenden T05-Tasks für die anderen vier Fach-Pipelines.
