# CLAUDE.md — GENESIS (operativ)

> Dies ist die **operative** Arbeitsanweisung für Claude Code. Die Vision/Architektur steht in `docs/VISION.md`. Die aktuell zu bauende Stufe steht in `docs/phases/` (α, β, γ: fertig + RESULT; nächste Stufe: δ). **Bei Konflikt gewinnen die Kernprinzipien unten.**

## Was GENESIS ist (in einem Satz)
Ein Mensch liefert ein Problem oder eine Idee; GENESIS recherchiert, verifiziert, synthetisiert, detailliert, simuliert und liefert eine umsetzbare Spezifikation — **ohne Halluzination**.

## Kernprinzipien (überschreiben alles andere)
1. **Kein faktischer Output ohne Quelle.** Jede Behauptung lebt im Fakten-Ledger mit Quelle, Confidence und Verifikations-Status. Code, der faktische Claims ohne Ledger-Eintrag erzeugt, ist ein Bug.
2. **Verifikation ist ein Gate, kein Vorschlag.** Eine Phase darf erst enden, wenn ihr Gate (siehe `docs/phases/`) bestanden ist. Gates sind im Code als harte Bedingungen implementiert.
3. **Cross-Model.** Der Verifikator (`skeptic`) nutzt ein anderes Modell als der Generator. Single-Model-Self-Check zählt nicht als Verifikation.
4. **"Ich weiß es nicht" ist ein gültiger, erwünschter Output.** Refusal/Abstention wird gemessen, nicht bestraft.
5. **Determinismus & Reproduzierbarkeit.** Jeder Lauf hat eine `run_id`, ist gecheckpointet und aus Ledger + Config exakt reproduzierbar.
6. **Stack-Agnostik.** Code gegen die Interfaces in `src/gen/core/interfaces.py`, nicht gegen ein konkretes Framework. Framework-spezifisches lebt hinter Adaptern.

## Arbeitskonventionen
- **Sprache:** Code/Kommentare Englisch; Doku Deutsch ist ok. Identifier Englisch.
- **Jede neue Funktion braucht:** Typ-Annotationen, Docstring (was/warum, nicht wie), Fehlerfälle dokumentiert, mindestens einen Test.
- **Jeder Agent** ist eine Klasse, die `Agent`-Protocol erfüllt (`core/interfaces.py`), mit: explizitem Input-Schema, Output-Schema, deklarierten Tools, deklarierten Fehlerzuständen.
- **Keine stillen Defaults bei faktischen Dingen.** Lieber Exception als geratener Wert.
- **Tests zuerst für Gates.** Ein Gate ohne Test existiert nicht.
- **Ultra-Workflow + 4 Linsen (ab dieser Session):** Nach **jeder** Arbeitseinheit (auch klein) wird das `4_LINSEN_PRINZIP.md` (inkl. erweiterter Selbstkontrolle mit L1–L4) angewendet. Abgleich gegen den aktuellen Abschnitt in `docs/GENESIS_PLATFORM_PLAN.md` (der Backlog der noch zu bauenden Teile: Grenzverschiebungs-Module, Fach-Pipelines, Wissensbasis, CAD/CAE als Kern, Lernmaschine etc.). Der `genesis-ultra-workflow` Skill aktiviert sich autonom bei Genesis-Kontext + PLATFORM_PLAN-Keywords. Agenten/Subagenten injizieren die erweiterte Selbstkontrolle.

## Definition of Done (pro Aufgabe)
- [ ] Interface erfüllt, Typen geprüft
- [ ] Tests grün (inkl. mindestens ein Negativtest: was passiert bei fehlender Quelle / Tool-Fehler / Widerspruch)
- [ ] Ledger-Einträge korrekt erzeugt (falls faktisch)
- [ ] Gate-Bedingung im Code geprüft (falls Phasen-relevant)
- [ ] Doku-Datei des Agenten/Moduls aktualisiert
- [ ] 4 Linsen (L1 Wahrheits-, L2 Drift-, L3 Vollständigkeits-/Naht-, L4 Realisierbarkeits-Linse) angewendet + Abgleich mit GENESIS_PLATFORM_PLAN.md-Abschnitt + erweiterte Selbstkontrolle dokumentiert (BUILD_LOG)

## Verzeichnis
```
docs/VISION.md            Vision, Stand der Technik, Risiken (das "Warum")
docs/ARCHITECTURE.md      Datenfluss, State, Gesamtbild (das "Was")
docs/DATA_MODEL.md        Ledger + Graph + DB-Schema, exakt
docs/PIPELINE.md          7 Phasen, Gates, Datenfluss
docs/phases/PHASE_ALPHA.md  Aktuelle Stufe: max. Detail, Akzeptanztests
docs/agents/*.md          Pro Agent: Prompt, I/O, Tools, Fehler, Tests
src/gen/core/             Interfaces, State, Config, Errors (framework-frei)
src/gen/agents/           Agentenimplementierungen
src/gen/ledger/           Fakten-Ledger
src/gen/verification/     Gates, Cross-Model-Judging
sql/                      DB-Schema (Postgres/pgvector)
tests/                    Tests, inkl. Gate-Akzeptanztests
```

## Aktueller Fokus
**Phase α + β + γ abgeschlossen + δ voll ausgebaut + Quality-Engine verdrahtet**
(881 Tests offline mit vollen Deps / 835+19 skipped ohne; α/β live bewiesen).
Live-Default-Verdrahtung (2026-06-12): Generator `qwen3.5:9b` + Verifier
`gemma4:12b` (beide lokal installiert; Fallback qwen2.5:14b + gemma4:latest).
γ: Idee → vollständige Spezifikation hinter GATE γ (Wächter C-1..C-18 inkl.
Cross-Claim-Konsistenz und GUM-Unsicherheit), 2 CAD-Exporte (OpenSCAD + build123d)
+ druckfertiges STL (OCCT-Kernel, Volumen-bewiesen).
δ: deterministische Physik-Engine (`docs/phases/PHASE_DELTA.md` §1–§57) — 27
Closed-Form-/FEM-Validatoren (Statik, Thermik, Modal, Knicken, Ermüdung, Bruch,
Torsion, Kontakt, Druck, Kriechen, Platte, Schraube, Thermospannung + 7
Druckbarkeits-Regeln + 4 Flug-Achsen: Rotor-Schwebe/Impulstheorie,
Akku-Flugzeit, Strom-Budget ESC/C-Rating, PD-Lageregelungs-Dämpfung + 3
Krypto-Achsen: Geburtstagsschranke/Nonce-Budget, NIST-SP-800-57-Schlüsselstärke,
GCM-Invocation-Limit — erste MathBrain-Erträge, §55) hinter
GATE δ-Physik mit Auto-Select aus measurand-getaggten Quantities; jede Achse
gegen geschlossene Formen/Research-Anker verifiziert. CSG-Vokabular kann
Rotation (beliebige Achse, alle Backends doku-verifiziert, §53).
Kalibrierung zusätzlich mit Split-Conformal-Quantilen (verteilungsfreie
Coverage-Garantie, §56). Ergebnisse DEUTSCH (Owner-Direktive 2026-06-12, §57):
Scholar-Claims, Approach-Namen, Spezifikations-Texte, Markdown-Bauhandbuch,
CLI-Renderer, Klärungsfragen (alle Measurands), Vollständigkeits-Warnungen,
Physik-Lücken, Druckbarkeits-Verdikt, Kosten-Roll-up UND die komplette
Demo-Welt (capstone/protocol/drive_shaft + scripted α/γ-Welten) sind deutsch;
Zitate bleiben wortlautgetreu in der Quellsprache (C-4 ist sprachneutral,
Zahlen byte-genau in Quell-Schreibweise); ids/units/Formeln/measurands/
Gate-Diagnostik englisch.
Druckbarkeit geometrisch: bridge_spans + first_layer_report (orientation.py),
STL-Slicebarkeits-Beweis (mesh_integrity.py, Euler–Poincaré + Divergenzsatz);
verdrahtet: pipeline.assess_printability → CLI `--mode print` + Web-UI-Tab
„Druckbarkeit", STL-Export mesh-integritäts-gegated;
Research-Write-up: docs/research/PRINT_DESIGN_FAILURES.md.
Quality-Engine: Eval-Harness (Leaks=0), Verify→Refine-Loop, proaktive Klärung,
Telemetrie, HITL-Ratifikation, Kalibrierung, Geometrie-/Constraint-/Grounding-
Integrität — komponiert zu einem ehrlichen Verdikt (`pipeline.assess_specification`,
CLI `--mode assess` + Footer im spec-Output).
Nächste ehrliche Schritte (Owner-gated, kein Live-Run bis „wirklich alles fertig"):
measurand-Emission durch den live-Architect, Refine-Loop am live-Conductor,
Gold-Set + kontrollierte gemessene Ollama-Läufe als Real-Use-Ready-Messung.
