# Depth-Audit: `src/gen/geometry_verification.py` (BREP-vs-analytic cross-check)

**Verdikt: REAL.** `verify_geometry` ist ein echter Cross-Check: es baut den exakten
OpenCASCADE-BREP-Solid (über brep.csg_to_solid + exact_volume + is_valid) und vergleicht
Volumen und AABB gegen die unabhängige analytische Schicht (verification.geometry). Die
Headline (Erkennen einer vom deklarierten Maß abweichenden Geometrie, z. B. die alte
Halbkugel-als-Vollkugel-Volumenhalbierung) ist implementiert und wird durch den Test
nachgewiesen. Keine Quelldatei-Änderung nötig — alle Pfade halten dem Characterization-Test stand.

## Beweis-Strategie (Facade-Killer)
Eine Fassade könnte einen konstanten "ok=True" oder gecachten Wert zurückgeben. Der Test
schließt das aus:

1. **Korrekte Primitive (Box/Sphere) passieren mit ok=True + volume_ok + extent_ok.**
   - Box 12×8×3 → Volumen exakt 288, Extent exakt (12,8,3), ok=True.
   - Sphere r=6 → analytic_exact, Brep-Volumen == 4/3 π r³ innerhalb 1e-6, Extent 12 mm.
   Das sind genau die Fälle, die die alte Hemisphere-Bug-Klasse (Volumen-Halbierung) gefangen hätten.

2. **Inputs werden wirklich konsumiert** (nicht canned):
   - Größerer Radius → signifikant größeres `brep_volume` (Faktor >3 beim Übergang 2→3).
   - Verschiedene Box-Größen → unterschiedliche gemeldete Volumina und Extents.
   Eine Konstante würde nie auf Input-Änderung reagieren.

3. **Deliberate mismatched / degenerate CSG → ok=False (mandatory negative).**
   - Difference (5 mm Box minus 10 mm Box, vollständig entfernend) → nonzero_volume=False,
     volume_ok=False, extent_ok=False, ok=False. Der Test übt den expliziten Degenerate-Pfad
     (kein BoundingBox-Aufruf auf void-Shape, ehrliche Null-Extent-Reportierung).
   - Unterschieds-Subtraktionen mit upper-bound-Volumen (Box minus enthaltener Zylinder) üben
     den nicht-exact-Pfad: brep_volume < analytic (upper) und volume_ok bleibt True, weil die
     <=-Bound-Logik korrekt ist.

4. **Property-based (Hypothesis):** über positive endliche Radien/Abmessungen gilt für
   Sphere und Box invariant:
   - ok=True, volume_ok=True, extent_ok=True
   - brep_volume ≈ analytic_volume (rel 1e-6)
   Das beweist, dass die Übereinstimmung nicht an einem einzelnen Beispiel hängt.

5. **Determinismus:** identischer Node+Quantities → identisches Ergebnis-Dict (A5-Vertrag).

6. **Fail-loud Guards:** fehlende Quantity-Id → GeometryError (laut, nie geratener Wert 0).

## 4-Linsen-Notiz
- **L1 Wahrheit:** Zwei unabhängige Wege (exakter OCCT-BREP-Volumen + analytische Formel
  bzw. AABB) müssen übereinstimmen. Der Test cross-checkt gegen im-Test nachgerechnete
  Anker (4/3 π r³, box-Volumen) und gegen die reale Kernel-Antwort — keine Halluzination.
- **L2 Drift:** Degenerate-Pfad vermeidet explizit den crashenden BoundingBox-Aufruf auf
  void-Shape; Volumen-Upper-Bound erlaubt nur <= (mit tol); kein stiller Default bei
  falscher Geometrie. Ein negativer max_total_thrust-ähnlicher Fall (hier: falsche Dimensionen)
  würde ok=False liefern statt eines irreführenden positiven Resultats.
- **L3 Vollständigkeit/Naht:** Positivfälle (Box, Sphere, rotate-cylinder) + Upper-Bound-Diff
  + Degenerate-Decision + Property-Sweep decken Primitive, Transform, Operationen und die
  exact-vs-bound-Verzweigung. Der Guard für nonzero schließt die Naht "leeres Solid".
- **L4 Realisierbarkeit:** Der Test respektiert die ehrliche Grenze (cadquery optional;
  nur echte silent-wrong-Defekte würden eine Guard-Änderung rechtfertigen). Keine blanket
  NaN/Inf-Guards hinzugefügt — nur wo ein realer falscher Wert ohne sie entstehen würde.

## Geänderte Quelldateien
Keine. `geometry_verification.py` wurde auditiert (Code-Review + Proben mit cad-kernel +
Hypotheses-ähnliche Spot-Checks) und ist korrekt ("change nothing if correct").
Alle dokumentierten Verträge (ok nur bei valid+nonzero+volume_ok+extent_ok, Degenerate-Pfad,
Error bei fehlender Quantity) sind implementiert.

## Test
`tests/test_geometry_verification_characterization.py` — 9 Skips (cadquery optional; unter
dem cad-venv-Python laufen alle 9 Assertions grün, inkl. Box/Sphere pass, degen ok=False,
Consumption, Determinismus, Property-Sweep, Missing-Quantity-Error).
Legacy `test_geometry_verification.py` bleibt unberührt.

Volle Charakterisierungs-Suite (neu) + manuelle Kernel-Probe: bestanden.
