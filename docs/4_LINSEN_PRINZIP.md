# 4 LINSEN PRINZIP — Nachkontrolle nach jeder Arbeit (Ultra-Workflow)

> **Zweck:** Nach jeder Arbeitseinheit (Code, Prompt-Änderung, Doc, Integration, Designentscheidung, Agent-Impl, Subtask — egal wie klein) **immer** die 4 Linsen anwenden, um Drift und Halluzination *beim Bauen von Genesis selbst* zu verhindern.
> Dies ist die harte Ergänzung zum bestehenden Selbstkontrolle-Ritual (§0.2 / §0.3 in `docs/CLAUDE_CODE_AUFTRAG_001.md`).
> 
> **Direkter Bezug:** Alles, was hier umgesetzt wird, dient der Erfüllung der noch offenen Teile in `docs/GENESIS_PLATFORM_PLAN.md` (Moonshot-Pipeline, Grenzverschiebungs-Module, Fach-Pipelines, Wissensbasis, CAD/CAE/Fertigung als Kernfähigkeit, Lern- und Verbesserungsmaschine, 8 Plattform-Schichten inkl. fehlender Front φ/χ und späterer Feedback-Loops). Jede Linse prüft explizit den Abgleich zur PLATFORM_PLAN-Spezifikation für das aktuelle Item.
> 
> **Autonom:** Der zugehörige `genesis-ultra-workflow` Skill (siehe SKILL.md) erkennt Genesis-Kontext (Pfad + Keywords wie phase/gate/ledger/skeptic/physik/cad/moonshot/Grenzverschiebung/experiment_designer/development_front_mapper etc.) und aktiviert sich selbst + lädt relevanten Kontext (CLAUDE.md + aktive Phase + WORK_QUEUE + letzten BUILD_LOG + **exakten PLATFORM_PLAN-Abschnitt**).

---

## Die 4 Linsen (immer in dieser Reihenfolge anwenden + dokumentieren)

### L1 — Wahrheits-Linse (Truth / Provenance Lens)
**Ziel:** Keine faktische Aussage, Entscheidung oder Claim ohne klare, abrufbare Quelle oder explizite Markierung als Hypothese/Lücke/Entscheidung.

**Kriterien (Abgleich mit PLATFORM_PLAN + bestehenden Regeln):**
- Jede neue Behauptung lebt im Ledger (oder analoger Attribution mit Quelle + Abruf + Status).
- Kein "klingt plausibel" — im Zweifel `UNSUPPORTED` (wie beim `skeptic`).
- Widersprüche zu bestehendem Wissen, Goldset, Phase-Doc oder dem aktuellen PLATFORM_PLAN-Abschnitt werden explizit aufgelöst oder als Lücke markiert.
- Cross-Check: Wird eine unabhängige Quelle (oder Cross-Model-ähnliche Prüfung) herangezogen?

**Typische Fragen:**
- "Wo steht das in der PLATFORM_PLAN.md für dieses Modul/Pipeline?"
- "Hat diese Designentscheidung/ dieser Messwert/ diese Formel eine Quelle oder ist sie als Entscheidung markiert?"
- "Widerspricht das einem existierenden Claim/Ledger-Eintrag?"

**Dokumentation in BUILD_LOG:** Kurzer Absatz "L1: [Status] — [Beleg/Quelle oder Lücke]".

### L2 — Drift- & Grounding-Linse (Anti-Drift / Halluzination Lens)
**Ziel:** Kein Detail ist seit dem letzten relevanten Checkpoint, Goldset, vorherigen Artefakt oder BUILD_LOG-Eintrag "erfunden", gerutscht oder ungenau geworden.

**Kriterien:**
- Diff vs. vorherigem Stand + explizite Prüfung der Änderung gegen reale Mechanismen/Quellen/Tests.
- Nutzung existierender Genesis-Tools wo anwendbar: `drift_monitor`, `grounding_integrity`, Geometry/Mesh-Verifikation (bei CAD/Physik-Artefakten), Constraint-Checks, Units/Derivation.
- "Was hat sich geändert? Ist die Änderung an die PLATFORM_PLAN-Spezifikation (z.B. Experimentleiter, Grenztyp-Taxonomie, Gate-Bedingungen) gebunden?"
- Keine stillen Annahmen oder "das war schon so".

**Typische Fragen:**
- "Entspricht der neue Code/Die neue Doku noch exakt dem, was in PLATFORM_PLAN.md für `development_front_mapper` / die Physiker-Pipeline / die Wissensbasis-Provenance beschrieben ist?"
- "Wurden bestehende Validatoren/Gates (δ-Physik, Printability, Mesh-Integrity etc.) durch die Änderung beeinträchtigt (auch implizit)?"

**Dokumentation in BUILD_LOG:** "L2: [Status] — Grounding-Check gegen [vorheriger Stand / Goldset / PLATFORM_PLAN §X] bestanden / Risiko: ..."

### L3 — Vollständigkeits- & Naht-Linse (Completeness & Seams Lens)
**Ziel:** Alle Interfaces, Failure-Modes, offenen Punkte, Kontext und Nähte zu anderen Modulen/Pipelines sind adressiert. Lücken sind sichtbar.

**Kriterien (stark an PLATFORM_PLAN + bestehende Gates angelehnt):**
- Deckt die in der PLATFORM_PLAN beschriebenen **Tasks, Outputs und Gates** für das aktuelle Item (z.B. für ein Grenzverschiebungs-Modul: Experimentleiter, Grenztyp-Typisierung, Abbruchkriterien; für eine Fach-Pipeline: alle aufgelisteten Aufgaben + das exakte Gate; für die Lernmaschine: alle 8 Schritte + Beweis vor Aufnahme).
- Seams zu Nachbar-Modulen (z.B. zwischen Moonshot und Fach-Pipelines, zwischen CAD und Fertigungs-Pipeline, zwischen Wissensbasis und Validatoren) sind dokumentiert.
- Offene Entscheidungspunkte, fehlende Technologien/Messungen, Risiken und nächste Experimente sind explizit (nie als "geht schon" versteckt).
- Deckt DoD / Phase-Akzeptanzkriterien + die in PLATFORM_PLAN spezifizierten Outputs ab?

**Typische Fragen:**
- "Fehlt ein Failure-Mode / eine Naht / ein Gate-Schritt, der in der PLATFORM_PLAN für genau dieses Modul aufgelistet ist?"
- "Sind alle in der Experimentleiter oder im Gate der Fach-Pipeline genannten Elemente adressiert?"

**Dokumentation in BUILD_LOG:** "L3: [Status] — Vollständigkeit vs. PLATFORM_PLAN §X.Y + Seams zu [Nachbar] geprüft. Offene Lücken: ..."

### L4 — Realisierbarkeits- & Verifizierbarkeits-Linse (Realizability / Fidelity Lens)
**Ziel:** Die Änderung ist testbar, bestehende Gates/Validatoren bleiben (oder werden besser) erfüllbar, Fidelity zu CAD/Physik/Export/Realität bleibt erhalten, und der Schritt ist ehrlich dokumentiert.

**Kriterien:**
- Tests erweitert/aktualisiert (inkl. mindestens eines Negativ-/Fehler-/Grenzfalls). "Tests zuerst für Gates" (bestehende Regel) gilt weiter.
- Bestehende Gates/Validatoren (δ-Physik + Auto-Select, Geometry, Constraint, Printability, Mesh-Integrity, Units, Derivation, Consensus, Trustcore, etc.) würden weiterhin oder besser bestehen. Keine Regression in Fidelity (CAD-Roundtrip, Volumen/Maß-Genauigkeit, Export-Artefakte, physikalische Korrektheit).
- BUILD_LOG-Eintrag + volle Selbstkontrolle 0.2 ist vollständig & ehrlich (mit 4-Linsen-Status).
- Artefakte (Specs, Reports, STL, Protokolle, neue Module) sind konsistent mit Claims **und** mit der exakten PLATFORM_PLAN-Beschreibung für das Item (z.B. "TechnologyPrototypeSpec" oder "SafetyStagePlan" oder "LearningDelta" werden wie beschrieben erzeugt).
- Wo das PLATFORM_PLAN-Item ein Gate oder einen Validator beschreibt: das neue Gate/der Validator verhält sich wie spezifiziert und ist selbst getestet.

**Typische Fragen:**
- "Würde `pipeline.assess_specification` / das δ-Physik-Gate / die Printability-Prüfung nach dieser Änderung immer noch ehrlich (keine versteckten Gaps als Pass) funktionieren?"
- "Ist der neue Code für [Grenzverschiebungs-Modul] so strukturiert, dass er die in PLATFORM_PLAN geforderten Outputs (z.B. `DevelopmentFrontMap`, `ExperimentPlan`) mit Provenance und Gate erzeugen kann?"

**Dokumentation in BUILD_LOG:** "L4: [Status] — Fidelity/Gate-Kompatibilität + Testbarkeit geprüft. Tests grün: ... Offene Punkte: ..."

**Gesamt nach 4 Linsen:** Nur bei allen 4 "bestanden" (mit Belegen) + Original-Selbstkontrolle 0.2/0.3 fortfahren. Bei "nein" oder Risiko: **stoppen, beheben, neu prüfen**.

---

## Integration mit bestehendem Ritual (Selbstkontrolle §0.2 + §0.3)

Die 4 Linsen **ersetzen nicht** die bestehende Checkliste — sie **ergänzen** sie hart.

**Erweiterte Selbstkontrolle (kopierbar in jeden BUILD_LOG-Eintrag):**

```
### Selbstkontrolle (§0.2 + 4 Linsen)
- [ ] Interface erfüllt, Typen geprüft
- [ ] Tests grün (inkl. mindestens ein Negativtest)
- [ ] Ledger-Einträge korrekt erzeugt (falls faktisch) / Attribution vorhanden
- [ ] Gate-Bedingung im Code geprüft (falls Phasen-relevant) + Abgleich zu PLATFORM_PLAN
- [ ] Doku-Datei des Agenten/Moduls aktualisiert + Verweis auf PLATFORM_PLAN-Abschnitt
- [ ] BUILD_LOG-Eintrag geschrieben (inkl. 4 Linsen + Link zum Vision-Item)?
- [ ] L1 (Wahrheits-Linse) bestanden + Beleg
- [ ] L2 (Drift-Linse) bestanden + Grounding-Check
- [ ] L3 (Vollständigkeits-/Naht-Linse) bestanden + Seams + PLATFORM_PLAN-Outputs
- [ ] L4 (Realisierbarkeits-Linse) bestanden + Fidelity + Testbarkeit
- [ ] Halluzinationsprüfung bei Agenten/Subagenten (§0.3) durchgeführt (wenn anwendbar)
- [ ] Kein Pfad für erfundenen Wert/Quelle/Detail?
- [ ] Fehler laut statt still?
- [ ] Offene Punkte ehrlich dokumentiert (inkl. fehlende Teile aus PLATFORM_PLAN)?
```

**Für Agenten & Subagenten (automatisch injiziert durch Ultra-Workflow):**
Nach Erledigung der Sub-Aufgabe: Führe die obige erweiterte Selbstkontrolle (0.2 + 4 Linsen mit PLATFORM_PLAN-Abgleich) als **Selbst-Report** aus und liefere sie mit Belegen, bevor Control zurückgegeben wird. Kein Fake-Erfolg. Keine Abweichung von der PLATFORM_PLAN-Spezifikation ohne explizite Markierung als Lücke/Entscheidung.

---

## Beispiele (kurz)

**Aus realem BUILD_LOG-Stil (Ledger-Aufgabe) erweitert auf Ultra:**
- Nach der Impl: L1 (Quellenzwang in 3 Schichten nachgewiesen), L2 (kein neuer Claim-Pfad ohne Source, Grounding gegen bestehende Gate-Tests), L3 (Seams zu Cross-Model + Phase-Gates dokumentiert, Abgleich zu PLATFORM_PLAN-Wissensbasis-Provenance), L4 (Tests 11/11 inkl. Negativ, InMemory als Referenz für Postgres, Fidelity zur LedgerStore-Interface + PLATFORM_PLAN-Anforderung an Provenance).

**Hypothetisch für neues Grenzverschiebungs-Modul `development_front_mapper` (erster Stein):**
- L1: Jede Grenze im `DevelopmentFrontMap` hat Quelle oder ist als `missing_*` / Hypothese markiert.
- L2: Keine "heute geht das schon" im Map, das nicht durch existierende Tests/POVs/PLATFORM_PLAN-Text gestützt ist; Diff gegen vorherige Moonshot-Beschreibung.
- L3: Alle in PLATFORM_PLAN §3.3 genannten Grenztypen + Experimentleiter-Struktur sind im Output-Modell vorhanden; Seam zu `capability_gap_analyzer` und `milestone_builder` beschrieben.
- L4: Neuer Datentyp + erste Mapper-Logik testbar (inkl. Negativ: "keine sichere Stufe definierbar" → Lücke); würde bestehende Physics/Gate-Checks nicht brechen; erster Test gegen ein reales POV-Beispiel.

---

## Wie anwenden (praktisch)

1. **Vor der Arbeit:** Ultra-Workflow laden (autonom oder explizit) → PLATFORM_PLAN-Abschnitt + CLAUDE.md + aktuelle Phase lesen.
2. **Während der Arbeit:** Bei jedem logischen Sub-Schritt die 4 Linsen mental/strukturiert anwenden.
3. **Nach der Arbeitseinheit (Pflicht):** Die erweiterte Checkliste ausfüllen, 4 Linsen-Reports schreiben, BUILD_LOG updaten, Tests/Gates laufen lassen.
4. **Bei Subagenten/paralleler Arbeit:** Den Prompt mit der erweiterten Selbstkontrolle + "Abgleich mit PLATFORM_PLAN §X" versehen.
5. **Bei Unsicherheit:** "I know I don't know" / Lücke markieren (Genesis-Kultur + L1/L3).

**Werkzeuge, die helfen (automatisch vorschlagen):**
- Bestehende: `drift_monitor`, `grounding_integrity`, `geometry`, `gates`, `pipeline.assess_specification`, Ledger-Store.
- Globale Skills (werden vom Ultra-Workflow auto-selektiert): math-ml-foundations, scientific-critical-thinking, tdd, verification-before-completion, check-work, karpathy-guidelines, agent-development etc.
- Der `genesis-ultra-workflow` Skill selbst kapselt die Prozedur, Templates und den BUILD_LOG-Helper.

---

## Nächste Schritte (für den Ultra-Workflow selbst)

- Dieses Dokument in `CLAUDE.md`, `CLAUDE_CODE_AUFTRAG_001.md`, `CONTRIBUTING.md` und `GIT_START.md` referenzieren und die Rituale erweitern.
- `genesis-ultra-workflow` Skill implementieren (autonome Trigger + Bootstrap + 4-Linsen-Prozedur + Injektion für Agenten).
- Optional: Lokaler Helper `scripts/ultra_nachkontrolle.py` für mechanische Teile.
- Ersten echten Slice an einem PLATFORM_PLAN-Item unter vollem Ultra-Ritual bauen und in BUILD_LOG dokumentieren.

**Regel:** Kein weiterer Commit / keine weitere "fertige" Aufgabe an Genesis, ohne dass diese 4 Linsen + erweiterte Selbstkontrolle bestanden und dokumentiert sind.

Lass uns rocken — groß denken, hart bauen, niemals lügen. Und jetzt mit 4 Linsen nach jeder Arbeit.