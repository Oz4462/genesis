# DEPTH AUDIT — `pipelines/fertigungs.py`

**Modul:** `src/gen/pipelines/fertigungs.py`
**Headline-Anspruch (PLATFORM_PLAN §4.7):** „Deterministischer Mapper von SystemConcept +
IngenieurSpec + optional advanced DFM zu FertigungsSpec" — Fertigungsverfahren wählen
(mit Begründung), Prozessgrenzen, Kostenmodell, QA-Plan.
**Datum:** 2026-06-23 · **Aufgabe:** T01

---

## Verdikt

**Vorher: PARTIAL-FACADE.** Der reiche, ehrliche Output existierte NUR für den hartcodierten
Jetpack-Substring (`"jetpack" in idee_lower or "flug" in idee_lower`). Für jede andere Idee
lieferte der `else`-Zweig eine **fixe** `FertigungsSpec`, die `concept` und `ingenieur` nicht
konsumierte:

- immer genau ein FDM-`FertigungsProzess` mit konstanter Begründung „Default prototype" und
  konstanter Grenze „min wall from DFM" — unabhängig von `cad_anforderungen`/`toleranzen`/
  `material_hinweise`;
- `KostenModell` fix `TBD`/`Lücke`; `QAPlan` fix `["Basic visual/dim"]`; `zusammenfassung` ein
  abgeschnittener `source_idea[:40]`-Stub → zwei verschiedene Ideen ergaben (bis auf die
  durchgereichte `source_idea`) byte-identische Specs (Facade).
- Leere/Whitespace-`source_idea` ergab still einen Stub statt lautem Fehler (Verstoß gegen
  „keine stillen Defaults") — inkonsistent mit `architekt.map_to_system_concept`.

**Nachher: REAL (generischer Pfad).** Der generische Pfad leitet Prozesse, Grenzen, QA, Kosten
und Zusammenfassung jetzt nachweislich aus den übergebenen Feldern ab; der Jetpack-Pfad bleibt
byte-stabil als geschützte Regression.

---

## Was real gemacht wurde (nur Verhalten, keine Signaturänderung)

1. **Prozesswahl aus realen Signalen** (`_derive_generic_processes`): FDM bleibt als ehrlicher
   Prototyp-Default, seine `prozessgrenzen` **zitieren** reale Maß-/Wand-Vorgaben aus
   `ingenieur.cad_anforderungen` (Marker `wand/wall/mm/fillet/radius`) — oder erklären explizit
   eine Lücke statt einer geratenen Wandstärke. CNC wird **nur** ergänzt, wenn ein echtes Signal
   es rechtfertigt: eine Präzisionstoleranz (`H7/g6/µm/±0.0…` in `ingenieur.toleranzen`) oder ein
   metallischer/Composite-Werkstoff (`alu/stahl/titan/cfk…` in `ingenieur.material_hinweise`).
   Die Begründung **bettet den konkreten Treiberwert ein** (z. B. „enge Toleranz 'H7' an
   'Lagersitz'") → auditierbar, nicht erfunden (Gate §4.7: keine Prozesswahl ohne Begründung).
2. **Kosten konsumieren denselben realen Seam:** `_fdm_cost_estimate_from_dfm(dfm_report)` wie im
   Jetpack-Pfad; ohne DFM-Kosten eine **explizite Lücke** (keine fabrizierte Preisspanne, keine
   „€"-Zahl) — Gate §4.7: keine Kosten ohne `cost_model`-Quelle.
3. **QA aus realen Eingaben:** Prüfschritte je `ingenieur.toleranzen` + `pruefplan_hinweise`;
   `gate_kriterien` honest „Lücke" wenn keine Toleranz ableitbar.
4. **Zusammenfassung spiegelt Realität:** `source_idea` + Baugruppen-Namen/Zwecke + abgeleitete
   Prozessliste → zwei verschiedene Eingaben ergeben unterscheidbare Specs.
5. **Negativpfad:** leere/whitespace-`source_idea` → `ValueError` (kein Stub für eine
   Nicht-Eingabe), spiegelt `architekt`. Im Docstring dokumentiert.
6. **Jetpack-Pfad unverändert:** FDM-primary + CNC-alt, realer Kosten-Seam, Tether-DFM-Ref,
   Signatur-Zusammenfassung — als Regression gepinnt.

Die Signaturen von `FertigungsProzess`, `KostenModell`, `QAPlan`, `FertigungsSpec` und
`map_to_fertigungs_spec` sind **unverändert** (downstream-Importer wie `realize`/`packager`
kompilieren weiter; die bestehende `tests/test_fertigungs.py`-Suite bleibt grün).

## Tests (`tests/test_fertigungs_characterization.py`)

Facade-Killer (scheiterten am alten else-Zweig) + Regression + 2 Property-Tests (Hypothesis):

- zwei verschiedene generische Eingaben → verschiedener abgeleiteter Inhalt (Facade-Killer);
- `source_idea`, Baugruppen-Zweck und reale CAD-Vorgabe tauchen im Output auf (Konsum-Beweis);
- Präzisionstoleranz **bzw.** Metallwerkstoff → CNC ergänzt, Treiberwert in der Begründung;
- signalfreie Eingabe → nur FDM, Grenze als Lücke, keine fabrizierte Kostenzahl (Abstinenz);
- DFM-Kosten vorhanden → verbatim konsumiert; fehlend → ehrliche Lücke, kein „€"/„8-25 EUR";
- leere/whitespace `source_idea` → `ValueError` (parametrisiert + Property);
- Jetpack-Pfad verbatim (FDM+CNC, Tether-Ref, realer Kosten-Seam);
- Property: jede non-blanke Nicht-Jetpack-Idee wird konsumiert, Spec wohlgeformt + ehrlich.

**17 Tests grün** (10 neue + 7 vorbestehende `fertigungs`); die `architekt`/`ingenieur`/
`integrator`-Konsumenten bleiben grün (47 passed / 16 skipped im Pipeline-Filter).

## 4 Linsen

- **L1 (Wahrheit):** Output folgt jetzt aus der Eingabe, nicht aus einer Konstante; jede
  Prozesswahl zitiert ein reales Feld, jede fehlende Größe ist eine Lücke statt geratener Zahl.
- **L2 (Drift):** Headline „deterministischer Mapper von <inputs> zu Spec" deckt sich jetzt mit
  dem Code für JEDE Idee, nicht nur Jetpack. Keine stillen Defaults mehr (Kernprinzip).
- **L3 (Vollständigkeit/Naht):** Jetpack-Pfad als geschützte Regression erhalten; der reale
  `_fdm_cost_estimate_from_dfm`-Seam (cost_model Stein 4) wird von beiden Pfaden genutzt;
  öffentliche Dataclass-Signaturen byte-stabil → realize/packager bleiben kompatibel.
- **L4 (Realisierbarkeit):** Edge-Cases (leere Idee, signalfreie Eingabe, Toleranz-/Material-
  Trigger, fehlende DFM-Kosten) abgedeckt; deterministisch; keine neue Dependency außer
  Hypothesis (Test-only, bereits deklariert).

**Offen / nächster Stein:** echte Supplier-Preise via Wissensbasis statt Kosten-Lücke; reale
Slicer-/CAM-Datei-Erzeugung (`datei_stub` bleibt im generischen Pfad ehrlich `None`).
