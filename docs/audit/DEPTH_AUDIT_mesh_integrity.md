# Depth-Audit: `src/gen/mesh_integrity.py` (δ STL sliceability proof)

**Verdikt: REAL.** Die Topologie- und Volumen-Rechnung ist exakt (gerichtete Kanten für watertight/consistent_winding, Euler-Poincaré chi = V−E+F, Divergenz-Volumen). Keine Heuristik, die immer "ok" sagt. Die neue Charakterisierung (`tests/test_mesh_integrity_characterization.py`) mit handgebautem Unit-Cube beweist es. Eine minimale Quell-Änderung war nötig, um die bereits exakt berechneten Zähler `open_edges`/`duplicated` in der Rückgabe sichtbar zu machen (sie steuern die Entscheidungen; der Test-Spec verlangt direkte Assertion).

## Headline-Claim
> stl_integrity_check performs exact manifold checks and signed-volume math on ASCII STL text; a watertight outward unit cube must report ok=True, watertight=True, consistent_winding=True, euler=2, genus=0, volume_positive=True, volume==1.0(±1e-9).

## Beweis (was wirklich konsumiert / berechnet wird)

Handgebauter watertight outward Unit-Cube (12 Dreiecke, 8 gemeinsame Vertizes, geometrisches Volumen exakt 1.0):

| Testfall | Erwartung (geschlossen / Hand) | Gemessen |
|----------|--------------------------------|----------|
| Gültiger Cube | ok, watertight, consistent, chi=2, genus=0, vol>0, vol≈1.0 | exakt erfüllt (fp 0.999... innerhalb 1e-9) |
| Ein Dreieck entfernt (Loch) | watertight=False, open_edges>0, ok=False + Issue | open_edges=3 (oder je nach Kante), Issue mit "open", ok=False |
| Alle Windungen umgekehrt (inside-out) | volume<0, volume_positive=False, ok=False; watertight+consistent bleiben True (Topologie perfekt) | exakt erfüllt |
| Nicht durch 3 teilbare Vertex-Anzahl | ValueError "multiple of three" | exakt |
| Keine Vertizes | ValueError "no vertices found" | exakt |

**Inputs werden konsumiert:**
- Entfernen einer Facette → open_edges >0 und watertight kippt (nicht konstant).
- Winding-Flip aller → volume wird exakt negiert (Divergenz-Formel reagiert auf Orientierung).
- Uniformes Skalieren (Property) → Volumen skaliert exakt mit scale³, Topologie-Flags invariant.

## Property-based (Hypothesis)
- `test_property_uniform_scale_preserves_topology_and_cubic_volume`: über scale ∈ [0.1,50] gilt chi=2/genus=0/watertight + volume == scale**3.
- `test_property_full_winding_reversal_negates_volume_but_keeps_watertight`: sign flip ohne Topologie-Änderung.

## Änderungen (nur weil der Test-Spec open_edges>0 verlangt)
- `src/gen/mesh_integrity.py`: 
  - `open_edges` und `duplicated` (die exakt im Edge-Walk berechneten Werte) werden jetzt in der Rückgabe-Dict mitgeliefert.
  - Docstring aktualisiert (Returns-Liste + kurze Begründung).
  - Modul-Header-Kommentar um einen Satz ergänzt.
- Keine Verhaltensänderung für bestehende Aufrufer (zusätzliche Keys sind unschädlich); alle Zahlen und Guards bleiben identisch.
- Legacy `tests/test_mesh_integrity.py` unangetastet (no churn).

## 4 Linsen
- **L1 Wahrheit:** Jede Flagge und das Volumen sind gegen die im Modul selbst dokumentierte Mathematik (Euler-Poincaré, Divergenzsatz, 2-Manifold-Kante) geprüft. Unit-Cube-Volumen = 1.0 und chi=2 sind unabhängig nachrechenbar.
- **L2 Drift:** Docstring versprach "exact, not heuristic"; der Test zeigt, dass die Zähler und Vorzeichen wirklich aus den Daten kommen (kein always-pass).
- **L3 Vollständigkeit/Naht:** Die vier vom Task-Spec geforderten Fälle (gültig / Loch / inside-out / Guards) + skalierende Property decken Happy + Negativ + Invariante. Naht zu brep/export/orientation/printability bleibt unberührt.
- **L4 Realisierbarkeit:** Randfälle (leere Datei, unvollständige Vertex-Listen) scheitern laut. Keine blanket NaN/Inf-Guards hinzugefügt — nur was der Test-Spec + fehlende Sichtbarkeit der exakten Zähler erforderte. Pure stdlib + Hypothesis (bereits im dev-Extra).

## Geänderte Quelldateien
- `src/gen/mesh_integrity.py` (nur Observability der bereits live berechneten exakten Zähler + Doku; "change nothing if correct" für die eigentliche Math)
- `tests/test_mesh_integrity_characterization.py` (neu, autoritativ)
- `docs/audit/DEPTH_AUDIT_mesh_integrity.md` (neu)

Legacy-Test und alle anderen Dateien unberührt.

## Test
`tests/test_mesh_integrity_characterization.py` — 7 passed (inkl. 2 Hypothesis-Properties + 2 obligatorische Negativ-Tests).

Zusammen mit Legacy: 6 passed + 1 skipped (cadquery).
