# Depth-Audit: `src/gen/fem3d_quadratic.py`

**Verdikt: REAL.** Der 10-Knoten-Quadrat-Tetraeder (T10) implementiert echte lineare Verzerrung (quadratische Ansatzfunktionen) in reinem numpy. Keine Source-Änderung nötig (`change nothing if correct`); die Charakterisierung mit handgebautem Einzel-Element + Property-Tests beweist, dass _b_matrix / t10_stiffness / t10_nodal_stresses / t10_mass / _t10_mass_reference **rechnen** statt Konstanten zu emittieren.

## Headline-Claim
> "the 10-node quadratic tetrahedron is a genuine linear-strain element, not a stub."

## Was geprüft wurde (tests/test_fem3d_quadratic_characterization.py — 10 Tests, alle grün)

### gmsh-FREE Element-API auf einem explizit handgebauten T10
Einzelnes Element mit **expliziten Corner- + Edge-Midpoint-Koordinaten** (kein Mesher):
- `_shape_grads` / `_b_matrix`: 10×3 bzw. 6×30 korrekt; linearer Verschiebungszustand (u = G·x) → exakte konstante Verzerrung an allen 4 Gauss-Punkten (Patch-Test, atol=1e-12).
- `t10_nodal_stresses`: an allen 10 Knoten (Ecken + Kantenmitten) identische Spannung = D·ε (linear-strain Recovery live).
- `t10_stiffness`: 30×30, symmetrisch, exakt linear in E; bei geometrischer Skalierung s=2 skaliert K exakt ×2 (B ~ 1/s, |J| ~ s³ → Netto-Faktor s).
- `t10_mass` + `_t10_mass_reference`: exakte baryzentrische Massenmatrix (Summe=1, geschlossene Formel ohne Quadratur); Gesamtmasse = ρV exakt; linear in ρ.

**Input wird konsumiert** (Facade-Killer):
- E ×2 → K ×2 (rtol 1e-9)
- Geometrie ×2 → K ×2 (rtol 1e-9)
- ρ ×2 → M ×2
- anderer nu → andere K (nicht konstant)
- Strain-Komponenten verändern recovered B@u exakt

### Property-Based (Hypothesis)
- `@given` über 6 Voigt-Komponenten: Patch-Test recovert **jede** beliebige konstante Verzerrung auf Maschinengenauigkeit (25 Beispiele).
- `@given(scale)`: K(E) == scale * K(1) exakt.

### Negativtests (dokumentierte + natürliche Fail-Loud-Pfade)
- Flaches (vol=0) Tet → `np.linalg.LinAlgError` (singulärer J in _b_matrix / t10_stiffness) — laut, kein stilles NaN/0.
- `box_mesh_t10` unter abwesendem gmsh → `GeometryError` (exakter Pfad in _require_gmsh via patch.dict simuliert; nur cross-checks sind mit `pytest.importorskip("gmsh")` geschützt).

### Optionale gmsh-Cross-Checks
Nur `pytest.importorskip("gmsh")` guardet `box_mesh_t10` (kleine Box als Verfügbarkeits-Probe). Die eigentlichen Beweise sind alle gmsh-frei.

Legacy `test_fem3d_quadratic.py` wurde nicht angerührt (no-churn).

## Beweis gegen Canned / Stub
Eine Stub-Implementierung (z.B. harte K mit fixed numbers, B=0, M immer ρV/10) würde
- den Patch-Test mit beliebigem G reißen,
- bei E-Skalierung oder Größen-Skalierung nicht exakt ×Faktor liefern,
- nicht die exakte _t10_mass_reference (Faktor 1/420 etc.) reproduzieren.

Alle Verhältnisse und die 1e-12-Recovery sind nur möglich, wenn die Formeln (Shape, B-Aufbau, 4-Pt-Gauss, exakte Integral-Masse, D-Matrix) wirklich ausgeführt werden.

## Änderungen
- Keine Edit an `src/gen/fem3d_quadratic.py` (Test lief grün, keine silent-wrong/ missing-guard-Defekte aufgedeckt).
- **`tests/test_fem3d_quadratic_characterization.py`**: NEU (autoritative Charakterisierung; Legacy unberührt).
- **`docs/audit/DEPTH_AUDIT_fem3d_quadratic.md`**: NEU (per Task-Scope).

## L1–L4
- **L1 Wahrheit:** Patch-Test + Skalierungsgesetze + exakte Massenformel sind gegen geschlossene Mathematik (B@u=ε, K~E, K~s, ∫NᵢNⱼ) geankert — nicht behauptet.
- **L2 Drift:** Nutzt exakt die bestehenden internen (_b_matrix, _elasticity_matrix, _t10_mass_reference) und public Signaturen; keine Parallel-Implementierung.
- **L3 Naht:** Schließt die Lücke "ist der T10-Element-Level echt (linear-strain) oder nur Deklaration?" zwischen Legacy-Uniform-Tests und der δ-Physik-Nutzung von quadratic tets.
- **L4 Realisierbarkeit:** Degenerierte Geometrie (vol=0) und fehlendes gmsh scheitern laut (LinAlg/GeometryError); kein silent default; End-to-End-Determinismus durch reinen numpy-Pfad.

Volle quadratic-Suite (neu + Legacy): alle relevanten Tests grün. Keine Source-Änderung.
