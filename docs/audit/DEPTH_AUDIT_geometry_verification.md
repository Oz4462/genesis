# Depth-Audit: `src/gen/geometry_verification.py` (BREP-vs-analytic cross-check)

**Verdikt: REAL (mit minimalem gezielten Fix, iterativ gehärtet).** `verify_geometry` ist ein echter Cross-Check:
es baut den exakten OpenCASCADE-BREP-Solid und vergleicht gegen die unabhängige analytische
Schicht (volume_of / aabb_of). Die Headline (Erkennen einer vom deklarierten Maß abweichenden
Geometrie) wird durch den Test nachgewiesen. Echter Defekt (extent isclose vs. conservative AABB
für Shrinking) + Folgefehler im L4-Guard (ließ (-abs_tol,0] und 0 durch) behoben. Guard jetzt
`e <= 0.0` (fängt negatives/zero auf nonzero_volume ab); Property + Negative-Tests erweitert
um Band-Probing und explizite Guard-Coverage. Fix/Test/Audit in Scope.

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

6. **Determinismus:** identischer Node+Quantities → identisches Ergebnis-Dict (A5-Vertrag).

7. **L4 Guard für negative/zero Extent (Round-3 Review):** Guard gehärtet (`e <= 0.0` statt `< -abs_tol`);
   fängt nun auch Werte in (-abs_tol,0] und exakt 0 auf nonzero_volume Solids ab (würden sonst
   vom <=-Check akzeptiert, obwohl geometrisch widersprüchlich zu vol>tol). Property-Sweep (mit
   kleinen Werten ~1e-8) + dedizierter Guard-Test + Asserts in allen Positivfällen prüfen, dass
   nonzero_volume immer positive Extents liefert und bad cases ok=False erzwingen. Kein stilles
   Akzeptieren von widersprüchlichen Werten.

8. **Fail-loud Guards:** fehlende Quantity-Id → GeometryError (laut, nie geratener Wert 0).

## 4-Linsen-Notiz
- **L1 Wahrheit:** Zwei unabhängige Wege (exakter OCCT-BREP-Volumen + analytische Formel
  bzw. AABB) müssen übereinstimmen. Der Test cross-checkt gegen im-Test nachgerechnete
  Anker (4/3 π r³, box-Volumen) und gegen die reale Kernel-Antwort — keine Halluzination.
- **L2 Drift:** Degenerate-Pfad vermeidet explizit den crashenden BoundingBox-Aufruf auf
  void-Shape; Volumen-Upper-Bound erlaubt nur <= (mit tol); extent jetzt ebenfalls
  bound-check (nie größer als declared AABB) statt isclose; Guard `e <= 0` (Round-3) fängt
  explizit (-tol,0] und 0 auf nonzero ab (würden sonst akzeptiert). Kein stiller Default.
  Trimming-Diff (kleineres Extent) liefert jetzt korrekt ok=True.
- **L3 Vollständigkeit/Naht:** Positivfälle (Box, Sphere, rotate-cylinder, trimming-Diff mit
  schrumpfendem Extent) + Upper-Bound-Diff + Degenerate + Property (inkl. Cylinder + near-zero
  Sweep + positive-extent-Assert bei nonzero) + dedizierter Guard-Test decken alle Pfade
  + Schrumpfungs-Naht + die Zero/Neg-Extent-Kontradiktion. 
- **L4 Realisierbarkeit:** Der Test respektiert die ehrliche Grenze (cadquery optional;
  nur echte silent-wrong-Defekte führen zu Änderung). Guard-Update + Test-Coverage gezielt
  für die vom Review identifizierten Lücken (keine blanket; defensiv für kernel pathology).

## Geänderte Quelldateien
- `src/gen/geometry_verification.py`: 
  - extent_ok-Logik (upper-bound <= statt isclose für conservative AABB / Shrinking-Ops).
  - L4-Guard gehärtet (Round-3): `if any(... or e <= 0.0 ...)` (statt `< -abs_tol`) + erweiterter
    Kommentar. Verhindert Akzeptanz von (-abs_tol,0] und 0 auf nonzero_volume Solids (würden
    vom <=-Check sonst true ergeben). Keine blanket-Änderungen.

- `tests/test_geometry_verification_characterization.py`: 
  - trimming-difference (exercises shrink → ok=True).
  - Property-Sweep erweitert (kleine Werte ~1e-8 zum Band-Probing; + asserts `nonzero_volume => all brep_extent > 0`).
  - Neuer dedizierter Test `test_extent_guard_on_nonzero_volume_rejects_non_positive_extents` (erklärt
    warum kernel keine bad-Extent-Solids produziert, deckt Guard-Contract + zero-input-Fälle).
  - Positive-Tests (box/sphere/trim/contained) + zero-dim-Test ergänzt um positive-extent- und
    Guard-Assertions.

- `docs/audit/DEPTH_AUDIT_geometry_verification.md`: aktualisiert (Round-3 Guard-Härtung + Coverage).

## Test
`tests/test_geometry_verification_characterization.py` — neue Charakterisierung (erweitert auf
Guard-Coverage); cadquery-optional via importorskip; unter cad-venv-Python alle Assertions grün
(inkl. Box/Sphere/trim ok+positive-extents, trimming-shrink (ok=True trotz kleiner brep_extent),
degen/zero-input → ok=False + extent<=0, Property mit near-zero-Sweep + nonzero=>ext>0 Asserts,
dedizierter Guard-Test für non-positive auf nonzero, Consumption, Det, Missing-Q-Error).
Legacy unverändert.

Volle Charakterisierungs-Suite (neu) + Kernel-Proben (inkl. Guard-Edge-Probing): bestanden.
