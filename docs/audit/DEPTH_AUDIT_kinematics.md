# Depth-Audit: `src/gen/kinematics.py` (δ closed-form robot axes)

**Verdikt: REAL.** Die vier DH/IK/Torque/ZMP-Achsen sind echte Closed-Form-Implementierungen, keine Stubs. Keine Quelländerung nötig — `kinematics.py` bleibt byte-stabil. Der neue Test `tests/test_kinematics_characterization.py` (16 Fälle + 3 Hypothesis-Property-Tests) ist der ausführbare Beweis.

## Umfang
Vier δ-Layer-Bausteine, je gegen eine geschlossene Form / Hand-Rechnung geprüft:
`forward_kinematics_dh`, `inverse_kinematics_2r`, `static_joint_torques`, `zmp_balance_check`
(plus `reach_check` als Workspace-Helfer).

## Befund: die Achsen rechnen echt (keine Fassade)
Die Charakterisierungs-Tests beweisen für jede Achse zweierlei —
(a) die Kennzahl-Behauptung hält gegen einen unabhängigen Anker (bzw. die trigonometrische Identität), und die Ausgabe ändert sich sinnvoll, wenn ein treibender Eingang variiert (der Eingang wird *konsumiert*, ist keine Konstante), und
(b) der dokumentierte Fail-Loud-Pfad feuert exakt.

| Funktion | Closed Form / Anker | Beweismethode |
|---|---|---|
| `forward_kinematics_dh` (planar 2R) | x = l₁·cosθ₁ + l₂·cos(θ₁+θ₂), y = l₁·sinθ₁ + l₂·sin(θ₁+θ₂) | Mehrere Winkel-Sets + Property über l,θ (Hypothesis) |
| `inverse_kinematics_2r` | FK→IK→FK round-trip (law of cosines) | Beide `elbow_up` Branches + unreachable-NaN-Fall |
| `static_joint_torques` | τ_base = m·g·L (horizontal, massless link + Payload) + ~0 vertikal | Exakter Anker + vertikaler Nullfall + Input-Consumed |
| `zmp_balance_check` | ZMP_x = com_x − (com_z/g)·a_x; margin = min(dist to edges)/half_width | Centered=1 / Edge=0 / Outside flips + exakte Shift-Property |

Bewegungs-Beweise (jede treibende Variable verschiebt den Output messbar): θ-Variation verschiebt FK-Position; mehr Payload/Masse → höheres Drehmoment; accel_x verschiebt ZMP linear (genau); kleinere l1/l2 verändert reach/ik.

## Guards / Negativpfade (alle fail-loud, getestet)
- `forward_kinematics_dh`: ValueError bei leerer Kette.
- `inverse_kinematics_2r` / `reach_check`: ValueError bei nicht-positiven Link-Längen.
- `static_joint_torques`: ValueError bei Längen-Mismatch, nicht-positivem g, negativen Massen/Längen.
- `zmp_balance_check`: ValueError bei degeneriertem Support-Polygon (max ≤ min), negativem com_z, nicht-positivem g.
- (Spec-gemäß) non-positive Link-Längen, degenerate Support, length-mismatch alle heben ValueError.

0-Längen-Links werden bei static aktuell toleriert (Drehmoment 0, physikalisch ein Punkt-Link); das ist kein stiller Falschwert und wurde nicht als Defect gewertet (keine Änderung).

## 4 Linsen
- **L1 Wahrheit:** Jede Kennzahl gegen Closed-Form / handgerechneten Anker + Hypothesis-Property fixiert (DH ≡ trig, τ == m·g·L, ZMP-Shift exakt). Kein faktischer Wert ohne nachvollziehbare Herleitung.
- **L2 Drift:** Docstrings beschreiben exakt die implementierten Formeln + Guards (z.B. "Raises ValueError on non-positive link lengths", "degenerate support polygon", "length mismatch"). Keine Lücke. Kein stiller Default.
- **L3 Vollständigkeit/Naht:** Legacy-Test `test_kinematics.py` (10) bleibt grün; neuer Characterization-Test (16 + Props) deckt zusätzlich beide Elbow-Branches, mehrere Winkel, vertikales ~0-Torque, exakte ZMP-Shift-Formel, Property-Invarianten über den Eingaberaum und alle in der Spec genannten Negativfälle ab. Keine Überschneidung / Churn.
- **L4 Realisierbarkeit:** Die dokumentierten ehrlichen Grenzen (planar static gravity only, 2R closed-form IK nur, kein full 3D Newton-Euler / dynamic walking, kein full contact) bleiben als bewusste Nicht-Abdeckung im Modul-Docstring deklariert. Keine NaN/Inf blanket guards hinzugefügt (nur echte Defects würden das triggern). Stack-agnostisch, offline, deterministisch, keine neuen Deps (Hypothesis nur im Test).

## Geänderte Quelldateien
Keine. `kinematics.py` blieb byte-stabil ("change nothing if correct" — Pre-Analyse + Charakterisierungstests haben keinen echten Defect (silent wrong value / fehlender dokumentierter Guard) gefunden).

## Test
`tests/test_kinematics_characterization.py` — 16 passed (Property-Tests eingeschlossen). Zusammen mit legacy `tests/test_kinematics.py` (10 passed).

## Isolation / Task-Regeln
Nur die drei erlaubten Pfade berührt:
- src/gen/kinematics.py (nicht editiert)
- tests/test_kinematics_characterization.py (neu)
- docs/audit/DEPTH_AUDIT_kinematics.md (neu)

Kein Touch von BUILD_LOG.md, legacy tests, anderen Modulen oder src unterhalb — erfüllt strikte Modul-Split + "tests pass using only this task's files plus pre-existing repo files".

## Determinismus / Reproduzierbarkeit
Alle Tests deterministisch (feste Anker + Property mit bounded floats). Keine Wall-Clock / Zufall ohne Seed.
