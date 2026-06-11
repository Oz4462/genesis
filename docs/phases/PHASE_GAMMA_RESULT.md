# PHASE γ — RESULT (ehrlich)

> Was erfüllt ist, was nicht, und wo die Grenze der Sandbox liegt. Keine
> Schönfärberei (CLAUDE_CODE_AUFTRAG_001 §2, CONTRIBUTING „Ehrlichkeit"). Format
> wie `PHASE_ALPHA_RESULT.md` / `PHASE_BETA_RESULT.md`.

## Zusammenfassung

Phase γ (Spezifikation) steht und ist **als Code beweisbar korrekt**: Die
komplette γ-Pipeline (α-Recherche → β-`synthesizer` → `architect` →
`Specification` → GATE γ) ist verdrahtet und läuft offline deterministisch
end-to-end — inklusive parametrischer 3D-Geometrie (CSG), Stückliste,
Schritt-für-Schritt-Anleitung mit Prüfkriterien, numerisch geprüften
Constraints und Entscheidungsblatt. Die α- und β-Garantien bleiben
**unverändert** (alle bestehenden Tests grün, geteilte Soundness-Helfer
unangetastet).

```
pytest -q  ->  257 passed (0.79s, ohne LLM-Token, ohne Netzwerk)
```

(154 bestehende α+β-Tests unverändert + 103 γ: 18 Safe-Evaluator, 17
Dimensionsanalyse, 49 GATE-γ, 12 architect, 7 Akzeptanz/End-to-End.)

**Nachgehärtet (Recherche-getrieben, 2026-06-11):** Dimensionale Homogenität als
sechster Wächter — die in §10 zuvor offen markierte Einheiten-Algebra ist jetzt
gebaut (GATE γ C-15, `verification/units.py`). Siehe Abschnitt „Dimensionsanalyse"
unten.

Zentrale γ-Invariante, die die α/β-Kette fortsetzt — **die fünf Zwänge**
(PHASE_GAMMA.md §0): kein Wert ohne Verankerung (wörtlich im VERIFIED-Claim),
keine Rechnung ohne Code-Berechnung + unabhängige Nachrechnung, keine Referenz
ins Nichts, keine Wahl ohne deklarierte Begründung, kein Schritt ohne
Prüfkriterium. Jede dieser Halluzinationsklassen ist dreischichtig verhindert:
Konstruktor-Guards (`UngroundedValueError`, `InvalidDerivationError`,
`UndeclaredDecisionError`), Drop-/Compute-Schichten im `architect`
(inkl. GATE-γ-Self-Check) und das unabhängige GATE γ.

Sichtbar machen: `python -m gen --demo --mode spec` druckt offline die
vollständige, belegte Anleitung (Wandhalterungs-Demo, run_id `demo-bracket`).

## Akzeptanzkriterien (PHASE_GAMMA.md §6)

| # | Kriterium | Status | Beleg |
|---|---|---|---|
| G1 | Kein erfundener Wert | **ERFÜLLT** | GROUNDED ⇒ VERIFIED-Claim + Wert wörtlich im Claim-Text (digit-boundary-geprüft); `gate_gamma` C-1–C-4; `test_fabricated_value_not_in_claim_text_fails`, `test_class_B…` |
| G2 | Keine Rechen-Halluzination | **ERFÜLLT** | DERIVED-Werte berechnet Code (`architect` ignoriert LLM-Werte nachweislich), Gate rechnet unabhängig nach; `test_llm_arithmetic_is_ignored…`, `test_wrong_derived_value_fails_recompute`, Zyklen/Grammatik in `test_derivation.py` |
| G3 | Keine versteckte Entscheidung | **ERFÜLLT** | DECISION ohne Rationale strukturell unmöglich + Gate-Backstop C-7; `test_constructor_rejects_decision_without_rationale`, `test_hidden_decision_is_dropped` |
| G4 | Kein Drift | **ERFÜLLT** | C-8 prüft jede Referenz (Geometrie→Quantity, Step→BOM, Constraint→Quantity, BOM→Component, Duplikat-Ids); 10 Negativtests in `test_gate_gamma.py` |
| G5 | Strukturell ohne Rückfrage umsetzbar | **ERFÜLLT (strukturell)** | C-9–C-12 + C-15: Aktion+Check je Schritt, topologische Baubarkeit, exakte CSG-Param-Mengen, Einheitenpflicht **+ dimensionale Homogenität der Derivations**; `test_input_produced_only_later_fails`, `test_adding_incommensurable_units_in_derivation_fails` u. a. |
| G6 | Fallen werden abgefangen | **ERFÜLLT** | Klasse B (erfundener Wert + LLM-Arithmetik) und Klasse D (dangling/checklos/unbaubar) → nie als Inhalt behauptet; Abstention statt Teil-Spec; `test_class_B…`, `test_class_D…`, `test_structurally_defective_proposal_abstains…` |
| G7 | Abstention | **ERFÜLLT** | Klasse C: nichts Verifizierbares → leere Spec + benannte Lücke, Gate besteht; `test_class_C_abstention`, `test_no_grounded_approach_abstains` |
| G8 | α+β-Garantien erhalten | **ERFÜLLT** | geteilter `claim_soundness_failures` auf jedem referenzierten Claim; Anker-Approach wird im Gate erneut B-3-artig geprüft (C-14); 154 α/β-Tests unverändert grün |

**G1, G2 und G6 — die wichtigsten — bestehen.**

## Ergebnis je Problemklasse (PHASE_GAMMA.md §7)

| Klasse | Idee/Falle | Verhalten | Erwartet | OK |
|---|---|---|---|---|
| A baubar | Wandhalterung, Last+Schraube verifiziert | vollständige Spec: 9 Quantities (2 GROUNDED, 2 DERIVED, 5 DECISION), CSG-Differenzkörper, 4 BOM-Zeilen, 2 Schritte mit Checks, Constraint hält, Gate bestanden | complete | ✅ |
| B Falle | Wert 70 ohne Wortlaut-Beleg + LLM „rechnet" 999 vor | 70 gedroppt (nie behauptet); 24.0 = code-berechnet im Output | trap_caught | ✅ |
| C unbelegbar | spekulative Idee ohne Korroboration | leere Spec + ehrliche Lücke | abstain | ✅ |
| D unvollständig | Schritt ohne Check + dangling `uses` + nie erzeugter Input | **keine Teil-Spec**: Abstention, Defekte benannt (INCOMPLETE_STEP/DANGLING_REFERENCE/UNBUILDABLE_ORDER im Log) | abstain+named | ✅ |
| E dimensional | DERIVED addiert kg + mm; Fläche als Länge deklariert | beide Größen gedroppt (DIMENSION_MISMATCH), nie behauptet; legitime Derivations überleben + rechnen korrekt | trap_caught | ✅ |

## Methodik — und ihre ehrliche Grenze

Die Akzeptanzläufe nutzen pro Klasse eine **deterministische „scripted world"**
(gescriptete Modelle + konservierte Quellen) — exakt die Gate-first-Methodik
aus α/β. Geprüft werden die **System-Garantien**, nicht die reale LLM-Qualität.

### Dimensionsanalyse (C-15) — Recherche-getriebene Nachhärtung

Die zuvor in §10 als „spätere Härtung" benannte Einheiten-Algebra ist gebaut und
geprüft. `verification/units.py` modelliert Dimensionen als **abelsche Gruppe**
über den sieben SI-Basisdimensionen (Prefix-Parsing für mm/kg/kN/MPa…; unbekannte
Einheiten werden *opaque* statt geraten). GATE γ C-15 prüft jede DERIVED-Formel:
add/sub nur dimensionsgleich, */ kombiniert Exponenten, und die errechnete
Dimension muss zur deklarierten Einheit passen. Der `architect` droppt
dimensional inkonsistente Größen vorab; das Gate backstoppt unabhängig.

**Belege:** `test_units.py` (17, Homogenität/Parsing/Conversion), `test_gate_gamma.py`
(C-15-Fälle inkl. kg+mm-Falle, Fläche-als-Länge, korrekte Conversion, Happy-Path),
`test_architect.py` (Drop), `test_phase_gamma_acceptance.py::test_class_E…`.

**Theoriegrundlage (recherchiert, nicht erfunden):** dimensionale Homogenität
(Standard) + Kennedy, *Types for Units-of-Measure: Theory and Practice* (CEFP 2009,
LNCS 6299) — „dimensional consistency provides a first check on the correctness
of an equation." **Motivierender Fehlerfall:** Mars Climate Orbiter (NASA 1999,
pound-force·s vs newton·s).

**Ehrliche Grenze von C-15:** Dimensionsanalyse fängt *Dimensions*-Fehler, nicht
*Magnitude*-Fehler innerhalb einer Dimension (ein cm→mm-Faktor `*100` statt `*10`
bleibt dimensional valide). Magnitude prüfen das Zahlen-Nachrechnen (C-6) und der
Wortlaut-Anker (C-4) — C-15 ist eine orthogonale, unabhängige Schicht.

**Was damit NICHT bewiesen ist (offen, ehrlich):**

- **Semantische „Ohne-Rückfrage"-Qualität realer Modelle.** G5 ist die
  strukturelle Approximation (Aktion+Check, Baubarkeit, Referenz-Vollständigkeit).
  Ob die Aktionstexte echter lokaler Modelle gut genug formuliert sind, misst
  erst der Live-Lauf (`--mode spec` gegen Ollama) — bewusst NICHT in dieser
  Session (User-Vorgabe: keine Ollama-Live-Runs).
- **Semantische Wert-Claim-Bindung über C-4 hinaus.** C-4 erzwingt den
  numerischen Wortlaut (inkl. Schutz vor Ziffern-Borgen: 5 matcht nie in „M15").
  Dass der Wert auch *semantisch* die richtige Größe im Claim ist (nicht eine
  andere Zahl im selben Satz), prüft offline niemand — das ist die Aufgabe
  eines Live-Wert-`skeptic`s (PHASE_GAMMA.md §10, benannt).
- **Kein CAD-Export.** Die CSG-Struktur ist auf OpenSCAD/build123d abbildbar
  (Quellen in PHASE_GAMMA.md §10), der Adapter ist Live-/δ-Arbeit.
- **Physik/Statik wird nicht simuliert** — das ist Phase δ. γ behauptet
  strukturelle + numerische Konsistenz, keine Tragfähigkeit.

**Über die Spezifikation hinaus gehärtet (dokumentierte Verschärfung):**
Duplikat-Ids in jedem Namensraum (Quantities, Components, BOM, Steps,
Decisions) gelten als Drift (`DANGLING_REFERENCE`) — ein doppeltes Id würde
Referenzen still verschatten.

## Phase γ: Fazit

Der γ-Anspruch — *eine Idee wird zu einer vollständigen, detaillierten,
umsetzbaren Spezifikation, in der kein Wert erfunden, keine Rechnung falsch,
keine Referenz gebrochen, keine Wahl versteckt und kein Schritt unprüfbar ist* —
ist als Code erbracht und getestet, auf dem bewiesenen α+β-Fundament und ohne
es zu schwächen. Der nächste ehrliche Schritt: derselbe Live-Beweis wie bei α
(lokale Ollama-Modelle, Generator ≠ Verifier-Familie) für die γ-Strecke, plus
CAD-Export-Adapter — danach Phase δ (Simulation).
