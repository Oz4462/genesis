# Research: CAD-Designfehler, die erst beim realen 3D-Druck sichtbar werden

> Recherchiert und verifiziert 2026-06-12 (Web-Research, kein LLM-Lauf).
> Implementierungs-Status pro Fehlerklasse: **GEBAUT** (deterministischer Check + Test),
> **EVIDENZ** (deterministisch gemessen, Verdikt beim Menschen) oder **LÜCKE** (ehrlich
> deklariert, nicht stillschweigend „bestanden").
> Implementierung: `src/gen/printability.py`, `src/gen/mesh_integrity.py`,
> `src/gen/orientation.py` (+ bestehend `dfm.py`, `tolerance.py`).
> Gate-Anbindung: `physics_validation.py` (Registry) + `physics_selection.py` (Recipes).

Der Kern der Recherche in einem Satz: **Die meisten Druckfehler sind keine
Geometriefehler, sondern Prozess-Physik** — sie existieren im CAD-Modell gar nicht
(Schichthaftung, Durchhang, Schrumpf, Quetschung der ersten Lage) und werden deshalb
von rein geometrischer Validierung systematisch übersehen.

---

## 1. Wand zu dünn — Wand druckt nicht oder bricht

Eine Wand unter zwei Extrusionsbreiten (2 × 0,4 mm Düse = 0,8 mm) druckt unzuverlässig
oder gar nicht; der Slicer lässt sie teils einfach weg. **Freistehende** (hohe, nicht
abgestützte) Wände brauchen mehr: ≥ 1,0 mm, sonst wackeln sie mit der Düse mit und
delaminieren.

- Supported wall ≥ 0,8 mm: **GEBAUT** (bestehend, `dfm.py::min_wall_formula`).
- Free-standing wall ≥ 1,0 mm: **GEBAUT** (`printability.unsupported_wall_check`) —
  der Distinktions-Test: 0,9 mm besteht die 0,8er-Regel und fällt freistehend durch.
- Quellen: Hydra Research FFF Design Rules; FacFox FDM Design Guideline; Forge Labs
  FDM Design Guide; Xometry FDM Design Tips.

## 2. Überhang über 45° — Durchhängen ohne Stützen

Flächen steiler als ~45° von der Vertikalen (konservativ; moderne Drucker schaffen
50–70°) sacken ohne Stützmaterial ab.

- **GEBAUT** (bestehend, `orientation.overhang_check`: 45°-Regel über das echte BREP,
  orientierungsabhängig, plus Stützvolumen-Obergrenze).
- Quellen: Hydra Research; Xometry; UltiMaker Design for FFF.

## 3. Brücke zu lang — die Decke zwischen zwei Auflagern sackt durch

Eine horizontale, beidseitig verankerte Decke („Bridge") druckt OHNE Stützen zuverlässig
bis ~10 mm Spannweite; darüber hängen die Stränge durch. Wichtig: Eine Brücke ist die
EINZIGE Ausnahme der Überhangregel — die Pauschalregel (jede flache Decke braucht
Stützen) ist für kurze Brücken zu konservativ, für Cantilever (nur einseitig verankert)
aber exakt richtig.

- **GEBAUT**, zweischichtig:
  - Quantity-Validator `printability.bridge_span_check` (Spann ≤ 10 mm), Recipe-Trigger
    `feature.bridge_span`.
  - Geometrisch `orientation.bridge_spans`: flache, abwärts gerichtete Dreiecks-Cluster
    über dem Druckbett; Randkanten klassifiziert als verankert (Nachbarfläche steigt ab)
    oder frei; Spann = Ausdehnung zwischen gegenüberliegenden verankerten Seiten (bei
    vier verankerten Seiten — Taschendecke — die KURZE Richtung, wie der Slicer brückt);
    ohne gegenüberliegendes Ankerpaar (Cantilever) unbridgebar → Stützen, egal wie klein.
  - Ehrliche Grenze: exakt für die achsenparallele CSG-Welt von GENESIS; gedrehte
    Brückenrichtungen degradieren zum konservativen „braucht Stützen", nie zum False-Pass.
- Quellen: Hydra Research (<10 mm); Xometry; FacFox (10 mm zuverlässig, 30 mm mit
  Durchhang).

## 4. Loch zu klein / Loch schrumpft — Bohrung unbrauchbar

Vertikale Löcher drucken systematisch UNTERMASS (Materialkompression + Düsenzug),
horizontale Löcher sacken zusätzlich oben durch (werden oval). Minimal zuverlässig:
2,0 mm horizontal (1,0 mm vertikal). Kompensation: horizontal ≈ +0,3 mm Durchmesser
designen (≈ eine Schichthöhe), vertikal slicer-seitig (XY hole compensation) oder
untermaßig designen und aufbohren.

- Min-Loch 2,0 mm: **GEBAUT** (bestehend, `dfm.py`).
- Kompensations-Konstanten: **GEBAUT** als Referenzwissen
  (`printability.FDM_HORIZONTAL_HOLE_COMPENSATION_MM = 0.3`); der Fit-Folgeschaden
  läuft über den Clearance-Check (unten). Ein universeller Vertikal-Schrumpfwert ist
  drucker-/materialabhängig → **LÜCKE** (dokumentiert, kein erfundener Standardwert).
- Quellen: Hydra Research (a ≈ 0,3 mm); goodprints3d; Kingroon (Orca hole
  compensation); Simplify3D-Forum.

## 5. Passung ohne Prozess-Spiel — Teile klemmen trotz korrekter Toleranzrechnung

Der Worst-Case-Toleranz-Stack kann positiv sein und die gedruckten Teile klemmen
TROTZDEM: Der FDM-Prozess selbst frisst ~0,1–0,2 mm. Designregel: ≥ 0,2 mm Spiel für
lose Passungen, ≥ 0,1 mm für stramme.

- **GEBAUT** (`printability.fdm_fit_clearance_check`, Floors 0,2/0,1 mm; negatives
  Spiel = Interferenz fällt durch, ohne Exception — das ist legitime Eingabe). Ergänzt
  den bestehenden ISO-2768-Worst-Case-Stack (`tolerance.py`), ersetzt ihn nicht.
- Quellen: Hydra Research (~0,2 loose / ~0,1 tight); Xometry.

## 6. Pin/Boss zu dünn — bricht beim ersten Einsatz

Freistehende Pins unter ~3 mm Durchmesser drucken unzuverlässig und scheren an der
ersten Schicht ab (aggressivste Guides erlauben 1,8 mm = 4 Extrusionsbreiten). Unter
5 mm: Fase/Fillet am Fuß gegen Schichtscherung.

- **GEBAUT** (`printability.pin_diameter_check`: ≥ 3,0 mm konservativ,
  `fillet_recommended` < 5 mm).
- Quellen: Forge Labs; FacFox; Hydra Research (1,8 mm-Schranke dokumentiert).

## 7. Modelliertes Gewinde zu klein — Gewinde strippt sofort

Gedruckte Gewinde funktionieren ab M5 (vertikal orientiert); darunter: Heat-Set-Insert
oder nach dem Druck schneiden (Kernloch: Tap 90 % / Self-Tap 96 % / Insert 98 % des
Außendurchmessers).

- **GEBAUT** (`printability.thread_size_check`: ≥ M5, `use_insert_or_tap` als ehrliche
  Alternative im Ergebnis).
- Quellen: Hydra Research; KingStar Mold; FacFox.

## 8. Schrift/Detail zu fein — Prägung verschmilzt zum Klumpen

Erhabene (embossed) Details brauchen ≥ 0,9 mm Breite (zwei Bahnen müssen einen freien
Grat bilden), gravierte (engraved) ≥ 0,5 mm (die Düse muss nur eine Lücke lassen);
Schrift praktikabel ab ~4-mm-Font bei 0,5 mm Tiefe/Höhe.

- **GEBAUT** (`printability.emboss_detail_check`, kind="emboss"/"engrave").
- Quellen: Hydra Research (0,9/0,5 mm); Laser Scanning UK (4-mm-Font-Regel).

## 9. Last quer zu den Schichten — das Teil delaminiert unter der Nennfestigkeit

**Der meist-übersehene Fehler überhaupt.** FDM-Teile sind anisotrop: Quer zu den
Schichten (Z) trägt nur die Schichthaftung — über 55 % Festigkeitsverlust gegenüber
den Datenblatt-(XY-)Werten ist die Literaturzahl. Jeder Statik-/Ermüdungs-Check, der
mit der Nennfestigkeit rechnet, ist auf dem Z-Lastpfad um Faktor ~2 unkonservativ.

- **GEBAUT** (`printability.layer_adhesion_check`: zulässig = 0,45 × Nennfestigkeit,
  Retention pro qualifiziertem Material/Profil überschreibbar; Druckspannung quer zu
  den Schichten delaminiert nicht → vorzeichenbehaftete Eingabe wird abgelehnt statt
  still uminterpretiert). Recipe-Trigger `print.stress_across_layers` + `material.uts`.
  Schlüssel-Test: 30 MPa quer bestehen die nominalen 50 MPa — und das Gate fällt
  trotzdem ehrlich durch (22,5 MPa zulässig).
- Ehrliche Grenze: 0,45 ist ein konservativer Default aus der „>55 % Verlust"-Zahl,
  kein Material-Messwert; die Druckrichtung selbst (welche Spannungskomponente quer
  liegt) muss deklariert werden — GENESIS rät sie nicht.
- Quellen: FacFox (FDM verliert >55 % Z-Festigkeit); Ahn et al. 2002 (Anisotropic
  material properties of FDM ABS — der Klassiker); RapidMade; Springer/MDPI-Studien
  (Schichthöhe als dominanter Z-Festigkeits-Parameter).

## 10. Elephant Foot — die erste Lage quillt über, Passungen am Boden klemmen

Die ersten Lagen werden auf das Bett gequetscht und bleiben warm → der Fuß des Teils
bulgt 0,1–0,5 mm nach außen. Folgen: Maßfehler an der Basis, klemmende Passungen,
kippelige Standflächen. Designseitige Abhilfe: ~0,3 mm Fase (Chamfer, KEIN Fillet —
ein Radius an der Bodenkante verschlechtert Warping) an der Bodenkante; slicer-seitig
Initial Layer Horizontal Expansion −0,2…−0,4 mm.

- **GEBAUT** (`orientation.first_layer_report`: erkennt scharfe Bodenkante = vertikale
  Wand trifft Druckbett im 90°-Winkel → `elephant_foot_risk` + empfohlene 0,3-mm-Fase).
- Quellen: Hydra Research (~0,3 mm Basis-Fase); Wevolver; Sovol/QIDI/Anycubic/Creality
  Elephant-Foot-Guides; Tom's Hardware.

## 11. Keine/zu kleine Auflagefläche — das Teil haftet nie

Ein Teil ohne ebene Druckbett-Kontaktfläche (Kugel, Punkt-/Linienkontakt) scheitert
vor der zweiten Schicht. Klassischer CAD-Fehler: Bauteil „schwebt" minimal über z=0
oder hat nur eine gekrümmte Unterseite.

- **GEBAUT** (`orientation.first_layer_report`: `plate_contact=False` bei
  Kontaktfläche 0 — die Kugel im Test).

## 12. Warping — große flache Teile ziehen sich an den Ecken hoch

Thermischer Schrumpf zieht große flache erste Lagen an den Ecken vom Bett (ABS/ASA/
Nylon/PC stark, PLA/TPU schwach). Abhilfen sind Material-/Prozesswahl (Brim, Einhausung,
Betttemperatur), designseitig: große Platten teilen, runde Ecken, KEINE Fillets an der
Bodenkante.

- **EVIDENZ, kein Verdikt** (`first_layer_report` liefert Footprint, Kontaktfläche,
  Höhe als Entscheidungsgrundlage). Ein universeller Schwellwert „ab x mm² warpt es"
  existiert nicht seriös (material-/prozessabhängig) → bewusst KEIN erfundenes Limit.
  **LÜCKE** ehrlich deklariert.
- Quellen: Amolen Warping-Guide; Medium/Wikifactory Ultimate Design Guide; skyryedesign.

## 13. Scharfe Innenecken — Spannungsrisse ab Werk

Scharfe Innenecken sind Kerben: Spannungskonzentration beim Drucken (Warping-Risse)
und im Einsatz. Designregel: Fillets ≥ 1 mm an Innenecken; an der Bodenkante Fase
statt Fillet (s. §10).

- Teilweise **GEBAUT** über die bestehende Kerb-Achse (`notch_fatigue_check`, Kt-FEM):
  wenn die Kerbe deklariert ist, wird sie gerechnet. Geometrische AUTO-Erkennung
  scharfer Innenecken aus dem CSG: **LÜCKE** (deklariert; das CSG-Vokabular hat noch
  kein Fillet-Primitiv, ein erkannter Verstoß wäre aktuell nicht behebbar beschreibbar).
- Quellen: Xometry; skyryedesign; Hydra Research (Fillets > Ø1 mm).

## 14. Kaputtes Mesh — non-manifold, Löcher, geflippte Normalen, inside-out

Der klassische „sieht im CAD perfekt aus, Slicer spinnt"-Fehler: Das STL ist keine
geschlossene, konsistent orientierte 2-Mannigfaltigkeit. Slicer raten dann (oder
verweigern), Drucke werden hohl/invertiert/löchrig.

- **GEBAUT** (`mesh_integrity.stl_integrity_check`), exakt statt heuristisch:
  - wasserdicht + konsistent gewickelt ⟺ jede gerichtete Kante genau 1× und ihre
    Umkehrung genau 1× (eine Bedingung fängt Loch UND Flip/non-manifold);
  - Euler-Charakteristik χ = V − E + F = 2 − 2g (Euler–Poincaré): Box-Mesh muss χ=2
    liefern, der Capstone-Halter mit Durchgangsloch χ=0/Genus 1 — die Topologie
    beweist, dass das Loch im Mesh ist;
  - Divergenzsatz-Volumen > 0 ⟺ Normalen nach außen — das perfekt wasserdichte,
    konsistente, aber INSIDE-OUT gedrehte Mesh fängt NUR dieser Test (eigener Test);
  - degenerierte (Null-Flächen-)Facetten gezählt; unparsbares STL → Exception statt
    Verdikt.
- Ehrliche Grenze: Vertex-Matching ist EXAKT (korrekt für Single-Kernel-Tessellation
  wie `brep_stl.py`, bewiesen am Capstone); fremde Meshes mit gejitterten Vertices
  können falsche „offene Kanten" melden — eine Weld-Toleranz wird nicht geraten.
- Quellen: Botsch et al., *Polygon Mesh Processing* (Euler–Poincaré, Mesh-Volumen);
  Slicer-Reparaturklassen (PrusaSlicer/Cura non-manifold/not watertight).

## 15. Einheiten-/Maßstabsfehler — das Teil kommt 25,4× zu groß/klein

STL trägt keine Einheit; CAD-Exporte in Zoll statt mm sind ein Klassiker.

- Strukturell abgedeckt: GENESIS-Quantities tragen Einheiten, C-15 prüft Dimensionen,
  `physics_selection` konvertiert nur über die verifizierte Einheitentabelle und
  verweigert opake Einheiten; der STL-Export schreibt kernel-exakte mm-Geometrie, das
  Mesh-Volumen wird gegen das exakte Kernel-Volumen bewiesen. Ein separater
  „Plausibilitäts-Check Bauraumgröße" wäre raterisch → nicht gebaut.

## 16. Naht (Seam), Ringing, Stringing, Slicer-Tuning

Sichtbare Z-Naht, Schwingungsartefakte, Fäden — reale Druckfehler, aber PROZESS-, nicht
Design-Fehler: Sie sind im CAD nicht adressierbar (außer Naht-Platzierung an Kanten,
eine ästhetische Slicer-Entscheidung).

- **LÜCKE per Scope** (ehrlich: außerhalb der Design-Validierung; GENESIS macht dazu
  bewusst keine Aussage).

---

## Verdrahtung (was davon läuft automatisch)

| Fehlerklasse | Check | Auto-Select-Trigger (measurand) |
|---|---|---|
| Brücke zu lang | `bridge_span` | `feature.bridge_span` |
| Passung klemmt | `fdm_fit_clearance` | `fit.clearance` |
| Pin zu dünn | `pin_diameter` | `feature.pin_diameter` |
| Gewinde zu klein | `thread_size` | `feature.thread_major_diameter` |
| Freie Wand zu dünn | `unsupported_wall` | `feature.unsupported_wall_thickness` |
| Prägung zu fein | `emboss_detail` | `feature.emboss_width` |
| Quer-Schicht-Last | `layer_adhesion` | `print.stress_across_layers` (+ `material.uts`) |

Geometrisch (über das BREP, cadquery-optional): `overhang_check` (bestehend),
`bridge_spans`, `first_layer_report`. Mesh-seitig: `stl_integrity_check` auf dem
exportierten STL. Alle deterministisch, offline, ohne LLM.

## Quellen (Research 2026-06-12)

- Hydra Research — Design Rules & Best Practices for FFF 3D Printing
  (https://www.hydraresearch3d.com/design-rules)
- Xometry Pro — FDM 3D Printing Design Tips (https://xometry.pro/en/articles/fdm-design-tips/)
- FacFox Docs — FDM Design Guideline (https://facfox.com/docs/kb/fdm-design-guideline);
  How 3D Printing direction/orientation affects strength
  (https://facfox.com/docs/kb/how-3d-printing-direction-orientation-affects-strength)
- Forge Labs — FDM Design Guidelines (https://forgelabs.com/fdm-design-guide/)
- 3D On Demand — Design Guidelines for FDM (wall thickness, tolerances, file prep)
- goodprints3d — Why Do 3D Printed Holes Come Out Too Small?
- Kingroon — Understanding Orca Slicer Hole Compensation
- Wevolver / Sovol / QIDI / Anycubic / Creality / Tom's Hardware — Elephant-Foot-Guides
- Amolen — How to Solve the 3D Printing Warping Problem
- Laser Scanning UK — FDM printing rules and considerations (4-mm-Schrift-Regel)
- Ahn, Montero, Odell, Roundy, Wright (2002) — Anisotropic material properties of
  FDM ABS (Rapid Prototyping Journal) — der Klassiker zur Z-Anisotropie
- Botsch, Kobbelt, Pauly, Alliez, Lévy (2010) — *Polygon Mesh Processing* —
  Euler–Poincaré + Divergenzsatz-Mesh-Volumen
