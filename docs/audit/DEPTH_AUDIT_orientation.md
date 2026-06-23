# Depth-Audit: `src/gen/orientation.py`

**Modul:** orientationsabhängige DFM über dem BREP — `overhang_check`,
`bridge_spans`, `first_layer_report` (die δ-DFM-Schicht auf dem OpenCASCADE-Kernel).

**Verdikt: REAL** (mit einer minimalen Härtung des dokumentierten Fehlerpfads).

## Was geprüft wurde

Neuer Test: `tests/test_orientation_depth.py` (cadquery/OCP via `pytest.importorskip`
am Modulkopf → der volle Gate bleibt grün ohne den CAD-Extra; in dieser Umgebung
ist cadquery nicht installiert, also skippt die Datei sauber). Jeder Headline-Claim
wurde in einen falsifizierbaren Test verwandelt — kein Smoke-Test:

- **`overhang_check` ist geometrie- UND orientierungsgetrieben, keine Konstante:**
  - flacher, achsenparalleler Quader (Baurichtung +Z) → `needs_support=False`,
    `overhang_area==0`, `worst_overhang_deg==0` (selbsttragend);
  - eine horizontale, vom Bauteller abgehobene Decke (Platte auf Pfeiler) →
    `needs_support=True`, `overhang_area>0`, `worst_overhang_deg>0` — beweist, dass
    die Normalen-/Winkel-Mathematik über das Mesh wirklich läuft;
  - **derselbe** Zylinder kippt sein Verdikt mit der Baurichtung: aufrecht (+Z) →
    `False`, liegend (+X) → `True` — beweist, dass `build_dir` ein konsumierter
    Live-Input ist, nicht ignoriert wird;
  - Determinismus (gleiche Toleranz → identisches Dict) und ein **Property-Test**
    (Hypothesis): ein achsenparalleler Quader beliebiger positiver Maße ist flach
    gedruckt IMMER selbsttragend — eine konstant-zurückgebende Fassade könnte diese
    Invariante über den Zufalls-Eingaberaum nicht halten.
- **`bridge_spans` misst die Spannweite aus dem Mesh:** kurze, an den Beinen
  verankerte Decke (Span ≤ `FDM_MAX_BRIDGE_MM`=10) → `ok=True`; breite (30 mm) →
  `needs_support=True`; die gemeldete Spannweite verfolgt den Spalt (6 mm → 12 mm
  vergrößert `worst_span`). Konstante ausgeschlossen.
- **`first_layer_report` unterscheidet echten Flächenkontakt von der Konvergenz-Probe:**
  Quader auf dem Teller → `plate_contact=True`, `contact_area>0` (~100 mm² = 10×10-Boden),
  `vanishing_contact=False`; ein liegender Zylinder (Linienkontakt) → `plate_contact=False`
  über die 16×-Verfeinerungs-Probe (entweder gar keine Band-Fläche oder eine, die unter
  Verfeinerung verschwindet) — keine fabrizierte Haftung.
- **Negativtest (fail-loud):** ein degeneriertes leeres Boolean (`A − B` mit `B ⊇ A`)
  → `ValueError("tessellation produced no triangles")` aus `first_layer_report` UND
  `bridge_spans`. Kein stiller Fehlverdikt.

## Gefundener Defekt + Fix (degenerierter Solid → fail-loud, alle drei Pfade)

Der dokumentierte Fehlerpfad war für den natürlichen degenerierten Input **nicht
erreichbar**: sowohl `_mesh` (für `first_layer_report`/`bridge_spans`) als auch
`overhang_check` rufen `solid.BoundingBox()` **vor** der Tessellierung auf. Ein leeres
Boolean (`A − B` mit `B ⊇ A`) liefert einen flächenlosen `Compound` mit **voider**
OCCT-BoundingBox; deren Auslesen wirft einen opaken Kernel-Fehler, bevor das
`if not tris:`-Gate je erreicht wird → der zugesicherte
`ValueError("tessellation produced no triangles")` würde nie feuern, und
`overhang_check` würde entweder opak crashen oder (nach erfolgreicher Bbox) **still
`needs_support=False`** melden — genau der stille Fehlverdikt, den dieses Audit
beseitigt (Verletzung von „keine stillen/opaken Defaults").

**Empirisch verifiziert** (cadquery 2.8.0 in `/home/genesis/.venv-cad`):
`small.cut(big)` → `Compound`; `.Faces()` → `[]` (wirft **nicht**);
`.BoundingBox()` → `Standard_ConstructionError "Bnd_Box is void"`. Der Crash ist real.

Fix: ein vorgezogener Guard direkt nach `csg_to_solid`, in **`_mesh` UND
`overhang_check`** (der Review-Befund aus Runde 1 — overhang_check war zunächst
ungehärtet):

```python
if not solid.Faces():
    raise ValueError("tessellation produced no triangles")
```

plus in `overhang_check` ein `if not tris:`-Backstop nach `tessellate` (paritätisch zu
den `_mesh`-Konsumenten, fängt den All-Sliver-Fall: Flächen vorhanden, aber keine
verwertbaren Dreiecke). Ein gültiger Solid hat immer ≥1 Fläche und tesselliert zu
vielen Dreiecken → für jede reale Geometrie ein **No-op** (Kugel-Fixtur weiterhin
`needs_support=True`, area>0; Box/Zylinder unverändert). Nur der degenerierte/leere
Shape wird jetzt in allen drei öffentlichen Funktionen deterministisch mit der
dokumentierten Meldung abgewiesen statt mit einem Kernel-Crash oder stillem `False`.
Sonst **keine** Verhaltensänderung — die reichen Overhang-/Bridge-/First-Layer-Pfade
bleiben byte-stabil.

## Verifikation (tatsächlich ausgeführt, nicht nur skip)

cadquery ist im Haupt-venv nicht installierbar (downgradet numpy, bricht den Stack),
daher `pytest.importorskip` im Test → der volle Gate bleibt grün. Der reale Kernel
existiert aber isoliert in `/home/genesis/.venv-cad` (cadquery 2.8.0). Alle 14
Szenarien des Tests (inkl. **aller drei** Negativ-Pfade
`overhang_check`/`first_layer_report`/`bridge_spans` → `ValueError`) wurden dort über
einen eigenständigen Treiber gegen den echten OCCT-Kernel ausgeführt: **14 passed, 0
failed**. Damit ist der dokumentierte `ValueError`-Pfad nicht nur behauptet, sondern
real durchlaufen.

## 4 Linsen

- **L1 Wahrheits-Linse:** Verdikte sind aus Tessellierungs-Normalen/-Flächen und
  `build_dir` berechnet (überhang per Winkel zur Bau-Gegenrichtung; Span aus
  verankerten gegenüberliegenden Kanten; Plattenkontakt per Konvergenz-Probe). Keine
  faktische Aussage ohne geometrische Herleitung; Honest-Boundary (45°-FDM-Regel,
  Einzel-Baurichtung) im Docstring offengelegt.
- **L2 Drift-Linse:** Tests fixieren echtes Verhalten (Flip mit `build_dir`,
  Span-Tracking, Probe), nicht Implementierungsdetails. Property-Test deckt den
  Eingaberaum statt weniger Stützstellen ab.
- **L3 Vollständigkeits-/Naht-Linse:** Negativtest für **alle drei** öffentlichen
  Funktionen (`overhang_check` + beide `_mesh`-Konsumenten) — der Runde-1-Befund, dass
  overhang_check ungehärtet war, ist geschlossen; Determinismus geprüft; der vorgezogene
  Guard schließt die Naht zwischen „leeres Boolean" und dokumentiertem Fehlerpfad, ohne
  die `csg_to_solid`/`brep`- und `pipeline.assess_printability`-Schnittstellen zu
  verändern.
- **L4 Realisierbarkeits-Linse:** cadquery bleibt optional (lazy, importorskip); der
  Guard nutzt nur die vorhandene cadquery-`Shape.Faces()`-API (keine neue Abhängigkeit).
  Volle Suite bleibt grün, wo der CAD-Extra fehlt.

## Status

- `tests/test_orientation_depth.py`: skippt ohne cadquery (wie `test_orientation.py`);
  exerziert mit cadquery example-basierte Tests + 1 Property-Test inkl. **drei**
  Negativtests (je einer für overhang_check, first_layer_report, bridge_spans). Real
  gegen cadquery 2.8.0 ausgeführt: 14/14 grün.
- Quelle: vorgezogener `Faces()`-Guard in `overhang_check` UND `_mesh`, plus
  `if not tris`-Backstop in `overhang_check` (paritätisch zu den `_mesh`-Konsumenten).
  Keine Signatur-/Output-Änderung; keine neue Abhängigkeit.
