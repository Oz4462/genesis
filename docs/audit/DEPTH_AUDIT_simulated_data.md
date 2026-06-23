# DEPTH AUDIT — `src/gen/discovery/simulated_data.py`

**Datum:** 2026-06-23 · **Aufgabe:** T05 (Depth-Audit + Härtung) · **Verdikt: REAL** (eine echte
silent-default-Lücke gefunden + geschlossen).

## Was das Modul behauptet
INVENTOR §10: GENESIS regrediert nicht nur auf vom Nutzer gelieferte Zahlen, sondern **erzeugt
seine eigenen Daten** — `problem_from_simulation` sampelt eine geschlossene Form `sim_fn` log-uniform
über die Eingabe-Bereiche, baut daraus eine selbst-generierte `DiscoveryProblem`, und
`discover_from_simulation` lässt die dimensionale SR-Engine das Gesetz daraus wiederfinden.

## Befund (4 Linsen)

**L1 Wahrheit — REAL, kein Fassaden-Konstrukt.** Die Charakterisierungstests beweisen:
- Die Zielspalte ist **exakt** `sim_fn`, punktweise auf die gesampelten Eingabespalten angewandt
  (`test_target_is_exactly_sim_fn_of_the_sampled_inputs`) — die Daten sind berechnet, nicht erfunden;
  die Spalte spannt echte Magnituden (log-uniform), keine degenerierte Konstante.
- Eine ganze **Familie** zufälliger Potenzgesetze `m^a·v^b` (property-based, Hypothesis) wird mit den
  exakten Exponenten zurückgewonnen — der dimensionale Solve ist echte lineare Algebra, kein
  memorierter Treffer. Verschiedene `sim_fn` → verschiedene wiedergefundene Exponenten.
- `baked` schließt Konstanten korrekt (Round-Trip-Identität, property-based): `baked(**x)` ==
  `sim_fn(**x, **constants)` für alle positiven Eingaben.

**L2 Drift — geschlossen.** Gefundene Lücke: **Namens-Kollision war eine stille Korruption.** Die
Engine identifiziert jede Quelle (Eingabe ODER Konstante) per Name in **einem** Exponenten-Dict.
Zwei Eingaben gleichen Namens (oder Eingabe == Konstante) ließen die `cols`-Comprehension still auf
eine Spalte kollabieren und fütterten die Engine mit einem korrupten Problem (zwei verschiedene
Größen → ein Eintrag), statt laut zu scheitern — ein Verstoß gegen „keine stillen Defaults". 
**Fix:** ein minimaler Eindeutigkeits-Guard in `problem_from_simulation`, der laut `ValueError`
wirft. Getestet durch `test_guard_rejects_duplicate_input_names` /
`test_guard_rejects_input_name_colliding_with_constant`.

**L3 Vollständigkeit/Naht — alle dokumentierten Guards getestet.** Leere Eingaben, zu wenige Samples
(`n_samples < 2`), nicht-positives/nicht-endliches Ziel, schlechter `InputSpec`-Bereich
(`lo>=hi`, `lo<=0`, NaN) feuern jeweils ein `ValueError` (inkl. parametrisierter + NaN-Fälle).
Negativ-Kontrolle: eine additive Form `y = x + x³` wird **nicht** fälschlich als `bestaetigt`
bestätigt (R² unter der Schwelle) — ehrliche Abstention statt fabrizierter Bestätigung.

**L4 Realisierbarkeit — Determinismus (A5) bewiesen.** Gleicher Seed → byte-identische Daten +
Verdikt; anderer Seed → andere Magnituden, aber dasselbe Gesetz (datengetrieben, nicht seedgetrieben).

## Quelländerung
Nur ein Guard hinzugefügt (Namens-Eindeutigkeit von Eingaben + Konstanten); öffentliche Signaturen,
Sampling-Logik und bestehendes Verhalten unverändert. Alle vorbestehenden Tests bleiben grün
(`tests/test_discovery_simulated_data.py`).
