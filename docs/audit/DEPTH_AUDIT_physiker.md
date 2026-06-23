# Depth-Audit: `src/gen/pipelines/physiker.py` (T02)

**Verdikt vor Fix: PARTIAL-FACADE.** **Verdikt nach Fix: REAL (generischer Pfad input-getrieben).**

## Befund (Facade-Smell)

`map_to_physiker_spec(concept, ingenieur)` hatte zwei Pfade:

- **Jetpack-Branch** (`'jetpack' in idea or 'jetpack' in assembly.name`): reichhaltig, handkuratiert, 4 Domänen, 3 Gleichungen, 3 Budgets, 3 Falsi-Pläne (mit echten Naht-Referenzen). → REAL für diesen Kanon.
- **Generischer `else`-Branch**: gab **fixe** Werte zurück
  (`PhysikDomäne("Grundmechanik", …)`, `ModellGleichung("F=ma", "F = m * a", …)`, `UnsicherheitsBudget("Masse", "±5%", …)`, ein generischer Falsi, eine fixe Zusammenfassung).
  Weder `concept.source_idea` / `main_assemblies` noch `ingenieur.lastfaelle`, `failure_modes` oder `material_hinweise` wurden gelesen.
  → Zwei beliebige Nicht-Jetpack-Inputs erzeugten **identische** `relevante_domaenen` + `falsifikations_plan` etc.
  Headline „deterministischer Mapper von SystemConcept + IngenieurSpec zu PhysikerSpec“ galt nur für den Jetpack-String.
  → Verstoß gegen „keine stillen Defaults bei faktischen Dingen“ + L2-Drift + L4-Edge (stiller falscher Wert).

Der alte generische Output war ein klassischer Facade: er tat so, als würde Physik modelliert, lieferte aber immer dasselbe unabhängig von den deklarierten Lastfällen.

## Fix (input-getrieben + ehrliche Lücke)

Neue private Helper (mit Typ-Annotationen + Docstrings + dokumentierten Fehlerfällen):

- `_derive_domaenen(ingenieur)` — je Lastfall → „Kräfte & Dynamik“ (mit kraft_oder_moment + beschreibung zitiert); je FailureMode → „Ausfall- und Bruchmechanik“; bei Materialkennwerten → „Materialphysik“. Bei Null-Signal: eine explizite „Grundmechanik (Lücke)“-Domäne.
- `_derive_gleichungen(ingenieur)` — je Lastfall/FM ein benanntes „Kraft-/Lastbilanz …“ / „Versagensmodell …“ mit `formel = "Lücke: spezifische Gleichung … nicht aus … ableitbar ohne zusätzliche Annahmen"`. Niemals eine physikalische Formel fabriziert (kein F=ma, keine Einheiten geraten).
- `_derive_budget(ingenieur)` — UnsicherheitsBudget je Lastfall/FM mit `wert="Lücke: keine quantitative Unsicherheit deklariert"`. Kein ±5%-Stub.
- `_derive_falsifikationsplan(ingenieur)` — je Lastfall ein „Lastfall-Verifikation: …“ mit `erwartete_messgroesse` aus der Kraft-Beschreibung; je FM aus dessen `detection`. Bei Null-Signal: expliziter Lücken-Eintrag.
- `_build_zusammenfassung(concept, ingenieur)` — spiegelt `source_idea` + Assembly-Namen + Zählung der Last/FM/Materialeinträge wider.

Guard am Anfang des Generic-Pfads (vor Ableitung):
```python
if not concept.source_idea.strip() and not ingenieur.lastfaelle:
    raise ValueError("... no actionable signal; refusal (ValueError) instead of a canned ...")
```
Per Spec: nur bei **beidem** (blank idea UND keine Lastfälle) → ValueError. Bei Idee ohne Lasten → ehrliche Lücken (Abstention).

Der **Jetpack-Branch ist byte-identisch erhalten** (protected regression, inkl. aller Strings, Counts, Quellen).

Quelle-String bekommt bei Generic einen Zusatz „+ input-driven generic (Lücken statt Fabrikation)“ (nicht im Jetpack-Pfad).

## Welche Inputs werden jetzt genuin konsumiert?

| Output-Feld                | abgeleitet aus |
|----------------------------|----------------|
| `relevante_domaenen`       | `ingenieur.lastfaelle[*].{name,kraft_oder_moment,beschreibung,quelle}` + `failure_modes[*]` + Material-Kennwerte |
| `modell_gleichungen`       | lastfaelle / failure_modes (Namen + Einheiten-Hinweise); Formel immer Lücke-Text |
| `unsicherheits_budget`     | lastfaelle + failure_modes (keine Konstante) |
| `falsifikations_plan`      | lastfaelle (kraft_oder_moment → erwartete_messgroesse) + failure_modes (detection) |
| `zusammenfassung`          | `concept.source_idea` + `concept.main_assemblies[*].name` + Zählungen von lastfaelle/failure_modes/material |
| `source_idea` (passthrough)| `concept.source_idea` (wie zuvor) |

## Test-Beleg (`tests/test_physiker_characterization.py`)

- **Facade-Killer** (2 distinkte Nicht-Jetpack-Inputs mit unterschiedlichen Lastfällen/Failure-Modes → distinkte Specs; „Tether-Zug“ vs. „Propulsion-Schub“ tauchen nur im jeweils korrekten Output auf; Kreuz-Kontamination unmöglich).
- **Fluss-Tests**: `LoadCase.kraft_oder_moment` → Domain + Falsi-Messgröße; `FailureMode.name`/`detection` → Falsi + Budget.
- **Material-Input**: MaterialSpec mit e_modul/dichte → Materialphysik-Domäne.
- **NEGATIVE (Abstention mit Lücken)**: nicht-leere Idee + 0 Lastfälle → alle Listen enthalten explizite „Lücke“-Texte, keine alten Canned-Strings (F=ma / ±5%).
- **NEGATIVE (ValueError)**: blank source_idea + 0 lastfaelle → exakter ValueError (parametrisiert).
- **Protected Regression**: Jetpack-Branch liefert exakt 4/3/3/3 + Signatur-Strings („E_in - E_out“, „F_tether = m * a“, „t_open < 3s“, „Jetpack“ in Zusammenfassung).
- **Real-Mapper-Regression**: generische Idee über `map_to_system_concept` + `map_to_ingenieur_spec` + `map_to_physiker_spec` → „Grundlast“ aus ingenieur-Generic fliesst in Output; Idee taucht in Zusammenfassung; kein F=ma-Canned.
- **Property-based (Hypothesis)**:
  - Für beliebige Listen von Lastfall-/FM-Namen (safe, jetpack/flug-frei): jeder Name taucht in abgeleitetem Output auf.
  - Für jede non-blank non-jetpack Idee via real Mapper: Zusammenfassung konsumiert die Idee.
- Alle Tests verwenden reale Konstruktoren (`SystemConcept(...)`, `IngenieurSpec(...)` etc.) + nur deklarierte Deps.

**11+ Tests grün.** Legacy `test_physiker.py` bleibt grün (len-Assertions + „minimal“-or-len-Falsi).

## 4 Linsen

- **L1 (Wahrheit)**: Keine erfundenen Gleichungen, Budgets oder „F=ma“ mehr. Alles ist entweder direkt aus prior-Stone-Feldern abgeleitet oder als explizite `Lücke` deklariert (mit Begründung im Text). `quelle` bleibt durchgehend.
- **L2 (Drift)**: Headline („die echte Physik … modellieren“ / „deterministischer Mapper …“) deckt sich jetzt mit dem Code für *jeden* Input, nicht nur Jetpack. Keine stillen Defaults.
- **L3 (Vollständigkeit/Naht)**: Naht zu Ingenieur (lastfaelle/failure_modes als primäre Signale), Architekt (assemblies/idea), Techniker/Integrator (PhysikerSpec als Input) bleibt; Jetpack-Demo unverändert; öffentliche Dataclasses + Signaturen byte-stabil.
- **L4 (Realisierbarkeit/Edge)**: 
  - blank + no-loads → lauter ValueError (kein geratener Stub).
  - Idee ohne Lasten → ehrliche Lücken (Abstention erlaubt).
  - Material- und FM-only-Pfade abgedeckt.
  - Property-Tests decken beliebige Kombinationen (inkl. 0) deterministisch ab.
  - Keine neue Runtime-Dep; Hypothesis nur für Test (bereits in dev-Deps).

## Backlog-Bezug

`GENESIS_PLATFORM_PLAN.md §4.3` (Physiker-Pipeline) + 2026-06-23 Team-Entscheidungen (Fach-Pipelines generic-branch-Fix, „change nothing if correct“ für Jetpack, „keine stillen Defaults“, „a gate without a test does not exist“, Characterization-Test + DEPTH_AUDIT statt Edit von Legacy-Tests).

Offen / ehrlich als Lücke vermerkt (müssen aus weiteren Stones kommen):
- Quantitative Formeln / Unsicherheitswerte (erfordern detaillierte Physik-Analyse + Wissensbasis / externe Daten).
- Dimensionsanalyse + konkrete Gültigkeitsgrenzen (werden in späteren Physiker-Stufen oder physics_validation nachgeliefert).

---

**Erstellt:** 2026-06-23 (T02). Keine Änderungen außerhalb des Scopes. Alle Änderungen durch Characterization-Tests getrieben und verifiziert.
