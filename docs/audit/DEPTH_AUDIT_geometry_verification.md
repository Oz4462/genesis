# Depth-Audit: `src/gen/geometry_verification.py` (BREP-vs-analytic cross-check)

**Verdikt: REAL (mit minimalem gezielten Fix).** `verify_geometry` ist ein echter Cross-Check:
es baut den exakten OpenCASCADE-BREP-Solid und vergleicht gegen die unabhängige analytische
Schicht (volume_of / aabb_of). Die Headline (Erkennen einer vom deklarierten Maß abweichenden
Geometrie) wird durch den Test nachgewiesen. Ein echter Defekt wurde gefunden und behoben
(siehe unten): extent_ok verwendete isclose gegen conservative AABB → falsches Fail bei
legitimen Shrinking-Ops (Difference). Fix + Test + Audit sind in Scope.

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
   Sphere, Box *und Cylinder* invariant:
   - ok=True, volume_ok=True, extent_ok=True
   - brep_volume ≈ analytic_volume (rel 1e-6)
   Das beweist, dass die Übereinstimmung nicht an einem einzelnen Beispiel hängt.

5. **Trimming-Difference (L3/L4 edge case aus Review):** Box minus rand-überlappendes Tool
   → realisiertes BREP-Extent kleiner als deklariertes Outer-AABB (analytic gibt immer Minuend).
   Vorher: extent_ok=False trotz korrekter Geometrie. Jetzt (bound check): ok=True, während
   Volume-Upper und Schrumpfung nachgewiesen werden. Das schließt die "trim vs declared envelope"-Lücke.

5. **Determinismus:** identischer Node+Quantities → identisches Ergebnis-Dict (A5-Vertrag).

6. **Fail-loud Guards:** fehlende Quantity-Id → GeometryError (laut, nie geratener Wert 0).

## 4-Linsen-Notiz
- **L1 Wahrheit:** Zwei unabhängige Wege (exakter OCCT-BREP-Volumen + analytische Formel
  bzw. AABB) müssen übereinstimmen. Der Test cross-checkt gegen im-Test nachgerechnete
  Anker (4/3 π r³, box-Volumen) und gegen die reale Kernel-Antwort — keine Halluzination.
- **L2 Drift:** Degenerate-Pfad vermeidet explizit den crashenden BoundingBox-Aufruf auf
  void-Shape; Volumen-Upper-Bound erlaubt nur <= (mit tol); extent jetzt ebenfalls
  bound-check (nie größer als declared AABB) statt isclose; zusätzlich finite-Guard nach
  nonzero. Kein stiller Default. Trimming-Diff (kleineres Extent) liefert jetzt korrekt ok=True.
- **L3 Vollständigkeit/Naht:** Positivfälle (Box, Sphere, rotate-cylinder, trimming-Diff mit
  schrumpfendem Extent) + Upper-Bound-Diff + Degenerate + Property (inkl. Cylinder) decken
  Primitive/Transform/Operationen + exact-vs-bound + die Schrumpfungs-Naht (AABB als Upper
  für Diff). Der nonzero-Guard + neue finite-Extent-Guard schließen pathologische Solids.
- **L4 Realisierbarkeit:** Der Test respektiert die ehrliche Grenze (cadquery optional;
  nur echte silent-wrong-Defekte führen zu Änderung). Die extent-Änderung ist minimal und
  gezielt (keine blanket NaN/Inf, nur wo ein realer falscher ok-Wert bei Shrinking-Op entstand).
  Zusätzlich defensiver finite-Guard für BB nach nonzero.

## Geänderte Quelldateien
- `src/gen/geometry_verification.py`: minimaler Fix der extent_ok-Logik. AABB ist immer
  ein *sound upper bound* (difference liefert stets den Minuend-Box; rotate ist konservativ).
  Bidirektionales isclose hat legitime Schrumpfungen durch trimming-Difference fälschlich als
  Mismatch gewertet (extent_ok=False → ok=False trotz korrekter Geometrie). Geändert auf
  `brep <= analytic + tol` (wie der non-exact Volume-Pfad) + finite/>=0 Guard gegen pathologische
  nonzero Solids. Dazu erklärender Kommentar. Keine anderen Änderungen (keine blanket Guards,
  keine Verhaltensänderung für korrekte exakte Primitive).

- `tests/test_geometry_verification_characterization.py`: neue Tests + Erweiterung:
  trimming-difference-Fall (Box minus überlappenden Tool am Rand) der jetzt ok=True liefert
  (schrumpft Extent, Volumen-Upper-Bound), Property-Sweep jetzt mit Cylinder, explizite
  Asserts auf legitimately smaller brep_extent.

- `docs/audit/DEPTH_AUDIT_geometry_verification.md`: aktualisiert (honest narrative).

## Test
`tests/test_geometry_verification_characterization.py` — neue Charakterisierung (10+ Tests;
cadquery-optional via importorskip inside numeric bodies; unter cad-venv-Python laufen alle
Assertions grün, inkl. Box/Sphere pass (ok+volume_ok+extent_ok), trimming-Diff (legit shrink
→ ok=True), degen ok=False, Consumption, Determinismus, Property (Sphere/Box/Cylinder),
Missing-Quantity-Error + finite-Guard-Pfad).
Legacy `test_geometry_verification.py` bleibt unberührt (no churn).

Volle Charakterisierungs-Suite (neu) + manuelle Kernel-Proben + Trim-Fix-Verify: bestanden.
