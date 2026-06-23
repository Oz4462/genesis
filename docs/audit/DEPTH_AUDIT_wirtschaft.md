# Depth-Audit: `src/gen/pipelines/wirtschaft.py`

**Datum:** 2026-06-23 · **Task:** T01 · **Modul:** Wirtschafts-/Produkt-Pipeline (erster Stein, PLAN §4)

## Verdikt

**Vorher: PARTIAL-FACADE → Nachher: REAL (input-driven, ehrliche Lücken).**

Der Jetpack-Zweig war von Anfang an reich und geerdet. Der generische `else`-Zweig war
jedoch eine Fassade: er gab **konstante** `TBD`/`Lücke`-Strings zurück, völlig unabhängig
von den Eingaben — nur die `zusammenfassung` enthielt einen 40-Zeichen-Schnipsel der
`source_idea`. Zwei verschiedene Ideen ergaben (bis auf den Schnipsel) byte-identische
`KostenStruktur`, `Markt` und `reparatur_modell`. Das verletzt das Kernprinzip *„keine
stillen Defaults bei faktischen Dingen"*.

## Was real gemacht wurde

`map_to_wirtschaft_spec` leitet den generischen Pfad jetzt nachweislich aus den echten
Eingabe-Feldern ab (drei kleine, klar benannte Helfer):

| Output | abgeleitet aus (echtes Signal) |
| --- | --- |
| `kosten.prototype` | `concept.main_assemblies` + `ingenieur.lastfaelle` (Anzahl-Treiber) |
| `kosten.low_volume` | `ingenieur.material_hinweise` (+ Metall/Composite-Marker), `toleranzen` |
| `kosten.target_volume` | `concept.open_decisions` (blockiert Serienkosten) |
| `kosten.repair_cost` | `ingenieur.failure_modes` (Inspektionspunkte) |
| `markt.zielgruppe` | `concept.requirements` (trägt die verbatim Idee) |
| `markt.stueckzahl_ramp` | `concept.variants` (Ramp) |
| `markt.lieferkette` | `concept.main_assemblies` (zu beschaffende Baugruppen) |
| `markt.skalierung` | `concept.open_decisions` (Gate: kein Skalierungspfad ohne Klärung) |
| `reparatur_modell` | `ingenieur.failure_modes` + `pruefplan_hinweise` |

**Ehrlichkeit statt Erfindung:** Es wird **keine** EUR-Zahl/Stückzahl geraten. Cost wird
als auditierbarer *qualitativer Treiber* ausgedrückt (Anzahlen, Werkstoffart); wo ein
Signal wirklich fehlt, steht ein expliziter `Lücke: …`-String. Das deckt das §4-Gate
(„no cost claim without source/estimate, no scaling without repair path").

**Negativ-Pfad:** Leere/Whitespace-`source_idea` → `ValueError` (spiegelt
`architekt`/`fertigungs`), statt eines fabrizierten Stubs.

## Geschützte Regression

Der Jetpack-Zweig und die öffentlichen Dataclass-Signaturen (`KostenStruktur`/`Markt`/
`WirtschaftSpec`, alle `frozen`) sind **byte-stabil**. `test_jetpack_branch_unchanged`
prüft die exakten kanonischen Strings; `test_public_dataclasses_are_frozen_with_expected_fields`
fixiert die Feldmengen. Der bestehende `tests/test_wirtschaft.py` bleibt grün.

## Tests (`tests/test_wirtschaft_characterization.py`)

1. **Facade-Killer** — zwei verschiedene Nicht-Jetpack-Eingaben ⇒ in *jedem* abgeleiteten
   Feld unterschiedlich; Anzahlen/Namen tauchen nachweislich auf (Input wird konsumiert).
2. **End-to-end** über die echten `architekt`/`ingenieur`-Mapper: zwei Ideen ⇒
   unterscheidbare `zielgruppe`/`zusammenfassung`.
3. **Ehrliche Abstention** — signalfreie Eingabe ⇒ ausschließlich `Lücke`-Strings, **kein**
   `EUR` auf dem No-Signal-Pfad.
4. **Negativtest** — leere/Whitespace-Idee ⇒ `ValueError` (parametrisiert).
5. **Property-based** (Hypothesis) — Determinismus (gleiche Eingabe → gleiche Spec, A5)
   und `source_idea`-Erhalt über zufällige Nicht-Jetpack-Ideen.

`PYTHONPATH=src pytest tests/test_wirtschaft_characterization.py tests/test_wirtschaft.py`
→ **11 passed**. Begleitend grün: `test_lernmaschine.py`, `test_fertigungs.py`.

## 4 Linsen

- **L1 Wahrheit:** Keine geratenen Zahlen mehr; jede Aussage zitiert ein konsumiertes Feld
  oder deklariert eine Lücke.
- **L2 Drift:** Generischer Pfad folgt jetzt demselben „input-driven + ValueError-Guard"-
  Muster wie `architekt`/`fertigungs` (kein Sonderweg).
- **L3 Vollständigkeit/Naht:** Jetpack-Zweig + Dataclass-Signaturen unverändert →
  Downstream-Importer (`__init__`, `lernmaschine`) kompilieren weiter.
- **L4 Realisierbarkeit:** Helfer sind klein, deterministisch, ohne neue Dependency
  (Hypothesis ist bereits deklariert).

**Offen (ehrlich):** echte gerangte Kosten brauchen die Naht zu `fertigungs`/`cost_model`
+ Wissensbasis-Lieferantenpreise; Marktdaten/Stückzahlziele brauchen eine echte
Marktanalyse-Quelle. Beides ist als `Lücke` markiert, nicht fingiert.
