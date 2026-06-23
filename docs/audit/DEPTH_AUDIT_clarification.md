# Depth-Audit: `src/gen/clarification.py`

**Verdikt: REAL.** Keine Quell-Änderung nötig — das Modul ist genuin measurand-getrieben,
nicht kaschiert. Nachgewiesen durch `tests/test_clarification_characterization.py`
(12 Tests, davon 2 property-based mit Hypothesis).

## Was geprüft wurde (Facade-Killer)

Alle Specs werden über die **echten** `core.state`-Konstruktoren (`Specification`,
`Quantity`, `ValueOrigin`) und die **echten** `physics_selection.RECIPES` gebaut; die
Recipe-Anker (`shaft.torque`, `column.axial_load`, `vessel.pressure`) werden direkt aus
dem Katalog gelesen, damit der Test der Quelle folgt statt Werte zu duplizieren.

1. **Ein fehlender Input einer indizierten Recipe → genau eine gezielte Frage.**
   Spec mit Trigger `shaft.torque` + alle Inputs außer `material.shear_strength` → exakt
   eine `ClarifyingQuestion` für genau diesen Measurand, `priority == 1`,
   `unblocks == ("shaft torsion",)`. `is_underspecified` → `True`.

2. **`priority` zählt indizierte Checks, `unblocks` listet die allein-freigeschalteten.**
   `material.yield_strength` wird von **zwei** indizierten Checks (column buckling +
   pressure vessel) als jeweils einziger fehlender Input gebraucht → **eine** Frage,
   `priority == 2`, `unblocks == (buckling, vessel)`. Beweist EVPI-Zählung + Sole-Unblock-
   Menge, kein konstantes Label.

3. **Input wird wirklich konsumiert (a):** Hinzufügen des fehlenden Measurands kippt die
   Spec von einer Frage auf null (`before != after`). Entfernen eines zweiten
   Buckling-Inputs schrumpft `unblocks` von `{buckling, vessel}` auf `{vessel}` — der
   Sole-Unblock-Satz folgt der tatsächlich vorhandenen Menge.

4. **Honest abstention (b, Negativfall):** physikfreie Spec (Measurands ohne Recipe-
   Trigger), leere Spec und vollständig spezifizierte Spec liefern jeweils `[]` und
   `is_underspecified is False` — kein Nörgeln, keine erfundene Frage.

5. **`apply_answers`:** fügt nur **nicht** bereits deklarierte Measurands hinzu, mit
   stabiler id `q_clarified_<measurand_mit_unterstrichen>`, `origin is DECISION`,
   überschreibt eine bestehende Deklaration **nie** (Wert bleibt), liefert ein **neues,
   unmutiertes** Spec-Objekt zurück.

## Property-based (Invarianten)

- `apply_answers` über beliebige frische Measurand-Mengen: fügt genau diese hinzu, jede
  mit dokumentierter id/`DECISION`-Herkunft, mutiert die Eingabe nie und ist **idempotent**
  (zweite Anwendung derselben Antworten — jetzt schon vorhanden — wächst nicht).
- `clarifying_questions` ist deterministisch und nach `(-priority, measurand)` sortiert;
  es fragt nie nach einem bereits deklarierten Measurand (nur nach Fehlendem),
  `priority >= 1`.

## 4 Linsen

- **L1 (Wahrheit):** Fragen entstehen ausschließlich aus indizierter, aber nicht
  evaluierbarer Physik (Trigger vorhanden ∧ Input fehlt). Kein faktischer Default — fehlt
  ein Wert, wird gefragt, nicht geraten (Kernprinzip „keine stillen Defaults").
- **L2 (Drift):** Keine Quell-Änderung; Verhalten exakt wie dokumentiert. `priority`/
  `unblocks` driften nicht von ihrer Docstring-Definition ab (per Test verankert).
- **L3 (Vollständigkeit/Naht):** Legacy-Test `test_clarification.py` bleibt grün (10
  passed); der neue Test ist additiv (`_characterization`-Suffix), keine Kollision.
- **L4 (Realisierbarkeit):** Rein offline/deterministisch, keine neuen Deps; Hypothesis
  ist bereits deklariert. Volle Suite unberührt.

**Fazit:** `clarification.py` erfüllt seinen Vertrag genuin — kein Facade, keine Korrektur.
