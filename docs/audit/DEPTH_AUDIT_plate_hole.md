# Depth-Audit: `src/gen/plate_hole.py`

**Datum:** 2026-06-24
**Auditor:** T04 (claude)
**Verdikt:** **REAL** — kein faktischer Facade-Anteil. Keine Quell-Änderung nötig
(„change nothing if correct").

## Was das Modul behauptet
Den Spannungskonzentrationsfaktor **Kt** an einem Loch **berechnet** zu liefern statt
die konservative Kirsch-Konstante `Kt = 3` der Statik-Schicht (PHASE_DELTA §9) nur zu
behaupten. Es vernetzt das klassische Platte-mit-Loch-Benchmark (gmsh, am Loch
verfeinert), zieht das Viertel-Symmetrie-Modell auf Zug und liest die echte
Spitzenspannung an der Lochkante.

## Wie der Facade-Verdacht getestet wurde (`tests/test_plate_hole_characterization.py`)
Ein hohler Facade — der einfach die Konstante `3.0` zurückgäbe — würde „in einem Band
um 3" landen und so den Alt-Test bestehen. Die neuen Checks schließen das aus:

1. **FEM-Observablen + Arithmetik, nicht Literal** — der Ergebnis-Dict trägt exakt
   `{"kt","far_field_sxx","peak_sxx","n_tets"}`, und `kt == peak_sxx / far_field_sxx`
   bis 1e-12. Der Wert ist eine Reduktion gelöster Spannungen, kein Literal.
2. **Endlich-Breiten-Wert über Kirsch** — `kt ≈ 3.16` (d/W=0.2), **streng > 3.0** und
   `!= 3.0`. Die Endlich-Breiten-Korrektur ist vorhanden; eine Konstante könnte sie
   nicht erzeugen. Fernfeld `far_field_sxx ≈ 205` ≈ E·δ/L = 210 (das aufgeprägte
   Bruttofeld), bestätigt die Last-Randbedingung wird real verarbeitet.
3. **Kt ändert sich mit der Geometrie** — größeres Loch (d/W 0.2→0.3) hebt den
   Endlich-Breiten-Kt messbar (3.16→3.22, Δ > 0.01), und die Tet-Anzahl ändert sich
   (1660 vs 3276) — beweist, dass `hole_radius/width` das gelöste Feld treibt, kein
   gecachtes Konstantergebnis.
4. **T10 erreicht vergleichbares Kt auf gröberem Netz** — der quadratische Löser liefert
   `kt ≈ 3.17` mit nur **683** Tets gegen **1660** beim feinen linearen Lauf (`n_tets`
   strikt kleiner, |Δkt| < 0.2). Der höherwertige (linear-strain) Tet leistet echte
   Arbeit; T10 aliast nicht den linearen Pfad.
5. **Property-Test (Hypothesis, ohne gmsh)** — die Kt-**Definition** `kt = peak/far`
   wird auf einem handgebauten 2-Element-Feld über 60 Beispiele gepinnt: die Reduktion
   erholt für jede `(far, ratio)`-Kombination exakt das Verhältnis. Ein Facade, der das
   Feld ignoriert und 3.0 zurückgäbe, fiele für jedes Beispiel durch.
6. **Determinismus** — zwei Läufe liefern byte-identische Dicts (A5-Reproduzierbarkeit).

## Negativtest (ALWAYS-RUN — fail-loud-Gate)
`_require_gmsh` muss bei fehlendem gmsh **laut** mit `core.errors.GeometryError` und der
dokumentierten Botschaft scheitern (Paketname + Fallback auf den `Kt=3`-Bound der
Statik-Schicht), nicht still defaulten. Realisiert durch Vergiften von
`sys.modules['gmsh'] = None`, sodass der lazy `import gmsh` einen `ImportError` wirft —
läuft also **unabhängig davon**, ob gmsh installiert ist (hier IST es installiert). Die
Positiv-Hälfte (`_require_gmsh()` gibt das Modul zurück) ist separat per `importorskip`
getestet. „Ein Gate ohne Test existiert nicht."

## 4 Linsen
- **L1 Wahrheit:** Jeder faktische Zahlenwert (Kt, Fernfeld) ist aus dem FEM berechnet
  und gegen die geschlossene Kirsch-Form + Endlich-Breiten-Korrektur verankert; keine
  ungequellte Behauptung.
- **L2 Drift:** Dokstring-Versprechen (4 Dict-Keys, Band ~3.0–3.5, Konvergenz, gmsh
  optional, `GeometryError`-Botschaft) decken sich 1:1 mit dem Code — kein Drift.
- **L3 Vollständigkeit/Naht:** Linearer (T4) **und** quadratischer (T10) Pfad geprüft,
  beide Solver-Nähte (`solve_elasticity`, `solve_elasticity_t10`/`t10_nodal_stresses`)
  laufen real; gmsh-Naht beidseitig (vorhanden/abwesend) abgedeckt.
- **L4 Realisierbarkeit:** Ehrliche Grenze bleibt dokumentiert (lineare Elastizität,
  Konstant-Dehnungs-Tets, Endlich-Breiten-Kt ≠ exakt 3, In-Plane-Konzentration, keine
  volle 3-D-Ermüdung/Bruch). Test erzwingt nichts darüber hinaus.

## Ergebnis
Modul-Quelle **unverändert**. Hinzugefügt: `tests/test_plate_hole_characterization.py`
(7 Tests: 5 gmsh-gated numerisch + Property + ALWAYS-RUN-Negativ-Gate) und dieses
Audit-Dokument. Voller Lauf: `7 passed`.
