# Depth-Audit: `src/gen/modal.py` — Modalanalyse / Eigenfrequenz-Eigenproblem

**Verdikt: REAL** — keine stillen Defaults, keine gefälschten Konstanten, kein Quellcode-Defekt gefunden. **Keine Änderung an `src/gen/modal.py`.**

## Geprüfte Headline-Ansprüche (Facade-Killer)

Neue Tests: `tests/test_modal_characterization.py` (11 Tests, alle grün; legacy `test_modal.py` unverändert grün). Jeder Test würde **scheitern**, wäre das Modul eine hohle Fassade, die kanonische Zahlen zurückgibt statt aus den Eingaben zu rechnen.

1. **Konsistente Masse = ρ·V (exakt) und mit ρ skalierend.**
   Auf einem handgebauten, nicht-degenerierten Referenz-Tetraeder (4 Knoten, 1 Tet, Volumen exakt 1/6 m³):
   - `total_mass == ρ/6` (rtol 1e-12),
   - ein translatorischer Block der assemblierten Massenmatrix (`m[0::3,0::3].sum()`) `== total_mass` (rtol 1e-12) — der dokumentierte „consistent mass sums to ρV"-Anspruch,
   - Verdopplung von ρ verdoppelt sowohl `total_mass` als auch die Block-Summe. Eine eingabe-unabhängige Konstante könnte diese lineare Skalierung nicht abbilden.

2. **Free-free Einzel-Tet → genau SECHS ~Null-Starrkörpermoden.**
   12 DOF → 12 Moden; die ersten sechs sind die Starrkörper-Nullen (3 Translationen + 3 Rotationen), jede `< 1e-6 ×` der ersten echten Deformationsfrequenz (`f[6] ≈ 3.23 kHz`); genau sechs liegen unter dieser Schranke. Diese strukturelle Signatur entsteht nur aus einem echten generalisierten Eigensolve `K·φ = ω²·M·φ`.

3. **`resonance_check`: ratio / ok / margin folgen den Eingaben.**
   - `ratio == first_natural_hz/excitation_hz`,
   - `margin_hz == first_natural_hz − factor·excitation_hz`,
   - `ok` kippt sowohl mit den Frequenzen (deutlich getrennt → True, near-resonant → False) als auch allein durch Änderung von `min_separation_factor` (2.5 ≥ 2.0 → True; 2.5 < 3.0 → False) — beweist, dass der Faktor wirklich konsumiert wird.

4. **Dokumentierte Guards feuern laut (Negativtests).**
   - `resonance_check` wirft `ValueError` bei `excitation_hz <= 0` (0.0 und negativ),
   - `natural_frequencies` wirft `GeometryError`, wenn alle 12 DOF fixiert sind („nichts zu schwingen").

5. **Property-based Invariante (Hypothesis).**
   Für zufällige Dichte (1…1e5) und uniformen Geometrie-Scale (0.1…10) gilt
   `total_mass == density · scale³ / 6` und die Massenmatrix-Block-Summe `== total_mass`
   (50 Beispiele) — Masse ist linear in der Dichte und kubisch im Längenmaßstab, eine echte Berechnung statt einer gespeicherten Konstante.

6. **gmsh-geschützter Closed-Form-Quervergleich.**
   Ein eingespannt-freier Stab konvergiert gegen `f₁ = c/(4L)`, `c = √(E/ρ)` (< 5 % auf grobem T10-Mesh). Der T10-Mesher braucht das optionale `gmsh`; der Test ist `pytest.importorskip('gmsh')`-geschützt, sodass das Gate ohne die optionale Abhängigkeit grün bleibt. (In dieser Umgebung ist gmsh installiert → der Test lief und bestand.)

## 4 Linsen
- **L1 Wahrheit:** Jede faktische Zahl ist gegen eine geschlossene Form geankert (ρV, ρ/6, sechs Starrkörper-Nullen, c/(4L)). Keine unbelegte Behauptung.
- **L2 Drift:** Docstring-Versprechen (consistent mass sums to ρV; sechs Starrkörpermoden; Raises Geometry_/ValueError) decken sich exakt mit dem getesteten Verhalten.
- **L3 Vollständigkeit/Naht:** Massenmatrix, Eigenproblem, Resonanz-Check und beide Guards abgedeckt; T10-Pfad über die bestehende `fem3d_quadratic`-Naht quergeprüft.
- **L4 Realisierbarkeit:** Tests laufen offline, deterministisch, rein in numpy; der einzige optionale Pfad (gmsh) ist sauber geskippt.

## Abgleich GENESIS_PLATFORM_PLAN
Deckt die CAE-Kern-Achse „Modal/Resonanz" als ehrlich verifizierten δ-Physik-Validator ab (Wiring: `physics_validation` „resonance"-Validator, `physics_selection`-Recipe Trigger `vibration.excitation_frequency`, `gate_delta_physics`). Honest boundary unverändert dokumentiert: lineare, ungedämpfte Kleinverschiebungs-Modalanalyse; der lineare Tet ist in Biegung übersteif (Frequenz HOCH-verzerrt) — daher der T10-Pfad.
