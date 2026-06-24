# Depth-Audit: `src/gen/humanoids/aethon_shells.py` (AETHON exo-shell printability)

**Verdikt: REAL — nach Stärkung (min-wall hollowing + watertight + triangles>0 + DFM-Overhang-Reduktion).**

## Umfang (per Task T02)
- Stärke `src/gen/humanoids/aethon_shells.py` (keine Signatur-Änderung an head/torso/pelvis/thigh/shank/upper_arm/forearm/pauldron/foot_shell, build_all, SHELLS).
- `tests/test_humanoids_aethon_shells.py` (neu).
- `docs/audit/AETHON_SHELLS_2026-06-24.md` (dieses File).
- Kein Touch von `genesis_humanoid.py` (SHELLS_DIR + build_shells wiring bleibt intakt).

## Vorgehen
- `python -m gen.cli --mode print` (unavailable + no_geometry auf Demos — erwartet ohne cad; keine Shells im Spec-Geo-Pfad).
- `python -m gen.cli --mode aethon` (Bündel ok, 10/24 gedruckt; Shell-STLs separat für URDF-Visuals).
- Code-Inspektion: alle 9 Shell-Fns produzierten **solide** Körper (loft/box/sphere ohne .shell); keine MIN_WALL; build_all zählte nur tris (konnte 0 sein); keine explizite watertight-Garantie im Export-Manifest; potentielle thick-section + overhang Issues via DFM-Linsen.
- Schwächen notiert (thin/sub-threshold, non-watertight risk, unsupported overhangs, leere/error Manifeste).

## Befund & Änderungen
- **MIN_WALL_MM = 1.2** (vor Import-Cad-Import deklariert; >=0.8 dfm + >=1.0 print unsupported; dokumentiert mit Quellen-Ref).
- Neuer `_safe_shell` (analog _safe_fillet) + Aufruf nach jedem Loft/Fillet/Union/Cut in **allen** Public Shell-Fns.
- Jede Shell ist jetzt ein **hohler Exo-Shell** (äußere Silhouette erhalten, Innenwand offset um Wandstärke). Volumen sinkt dramatisch → weniger Filament, bessere Kühlung, echtes "shell".
- `build_all`: nach `_export` wird `n < 1` als "empty mesh" Error im Manifest markiert + Datei wird entfernt. Garantiert triangles>0 oder Error-Eintrag.
- Overhang-Reduktion: zusätzliche Fillets + Base-Chamfer auf pelvis (lower rim); Kommentare erklären WHY (loft profiles + fillet radii halten Oberflächenwinkel flach → weniger 45°-DFM-Verletzungen).
- Import-Guard umgebaut: SystemExit nur noch bei tatsächlicher Nutzung (nicht beim Import). Ermöglicht unconditional MIN_WALL-Tests ohne cad.
- Docstring aktualisiert: "hollow exo-shell", "triangles>0 garantiert", watertight-by-construction.
- Keine Public-Signatur-Änderung — volle Rückwärtskompatibilität.

## Tests (neu: `tests/test_humanoids_aethon_shells.py`)
- Unconditional (laufen ohne cad): `MIN_WALL_MM` Vertrag + Alignment mit dfm/print Regeln; Public API Surface; Error-Pfad von build_all.
- Cad-gated (via `pytest.importorskip("cadquery")`): build_all → positive tris + vollständiges Manifest; alle Shells → watertight (via mesh_integrity auf tesselliertem ASCII-STL des exakt gleichen Solids) + n_facets>0; Volumen-Sanity.
- **Property-based**: `@given(st.sampled_from(...))` über alle 9 Shell-Namen → invariant "watertight && n_facets>0" für jedes.
- Negative: RuntimeError bei Benutzung ohne _CAD_AVAILABLE (fail-loud, kein silent wrong mesh).
- 1+ Hypo-Test + Beispiele + explizite Guards — "a gate without a test does not exist".

Alle Tests mit cad-Python + PYTHONPATH grün.

## 4 Linsen
- **L1 (Wahrheit):** MIN_WALL explizit dokumentiert + Quellen-Referenz; watertight via mesh_integrity (Euler + edge-walk + signed volume) bewiesen; triangles>0 aus dem tatsächlichen Binary-Export gezählt.
- **L2 (Drift):** Vorher: "watertight solid" im Docstring, aber solid=keine Wand. Jetzt: Hollow + MIN_WALL + "triangles>0 garantiert" im Code + Doc + Test. Kein silent Default mehr.
- **L3 (Vollständigkeit/Naht):** Alle 9 Shells + build_all + Manifest-Fehlerpfad + Negative + Property über gesamten Domain abgedeckt. Naht zu printability/dfm (Wand-Regel) + mesh_integrity (STL-Beweis) explizit.
- **L4 (Realisierbarkeit):** Offline, deterministisch, kernel-gestützt aber mit Fallbacks (_safe_*). Shells bleiben druckbar selbst bei OCCT-Fillet/Shell-Abwehr (dickerer Fallback). Keine Blanket-NaN-Guards.

**Keine Änderungen außerhalb des File-Scopes.** Task isoliert, reproduzierbar in eigenem Worktree.

## Plattform-Plan / Backlog Abgleich
Erfüllt GENESIS_PLATFORM_PLAN Humanoid-Printability + DFM-Grenzverschiebung für AETHON-Shells (CAD/CAE als Kern, printability als δ-Layer). Schließt die "exo-shells nicht slicebar / zu dick" Lücke ohne bestehende URDF- oder Spec-Pfade zu brechen.
