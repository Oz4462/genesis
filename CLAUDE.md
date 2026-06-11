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

## Definition of Done (pro Aufgabe)
- [ ] Interface erfüllt, Typen geprüft
- [ ] Tests grün (inkl. mindestens ein Negativtest: was passiert bei fehlender Quelle / Tool-Fehler / Widerspruch)
- [ ] Ledger-Einträge korrekt erzeugt (falls faktisch)
- [ ] Gate-Bedingung im Code geprüft (falls Phasen-relevant)
- [ ] Doku-Datei des Agenten/Moduls aktualisiert

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
**Phase α + β + γ abgeschlossen + δ erste Schicht** (311 Tests offline, α/β live bewiesen).
γ: Idee → vollständige Spezifikation hinter GATE γ (6 Wächter: Wert-Wortlaut,
Code-Arithmetik, Referenz, Entscheidung, Vollständigkeit, dimensionale Homogenität),
Ausdrucks-Constraints + Plausibilität, 2 CAD-Exporte (OpenSCAD + build123d).
δ: deterministische Geometrie-Validierung (GATE δ, AABB) — tote/leere Operationen,
ohne erfundenes Physik-Urteil (`docs/phases/PHASE_DELTA.md`).
Nächste ehrliche Schritte: γ/δ-Live-Beweis (`--mode spec` gegen Ollama, vom Owner
zurückgestellt), weitere δ-Schichten mit echten Modellen (Toleranz/FEM hinter Adaptern).
