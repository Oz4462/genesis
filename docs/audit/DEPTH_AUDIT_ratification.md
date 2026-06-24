# Depth-Audit: `src/gen/ratification.py` (Human-in-the-Loop Sign-off-Gate)

**Verdikt: REAL** — keine Quell-Änderung nötig (`change nothing if correct`).

## Was geprüft wurde
`ratification.py` implementiert den No-Default-Approval-Vertrag (Research #5, Agent-SDK-Leitlinie
„never fake approval with hidden auto-allow"): aus einer `Specification` + Gate-Verdikten wird ein
PACKET blockierender Items abgeleitet, und „done" gilt **nur**, wenn ein **benannter** Mensch
jedes blockierende Item explizit signiert hat. Reine Funktionen, kein Modellaufruf, kein I/O.

Neuer Facade-Detektor: `tests/test_ratification_characterization.py` (14 Tests, inkl. 2
Hypothesis-Properties). Legacy `tests/test_ratification.py` bleibt unverändert grün (9 Tests).

## L1 — Wahrheits-Linse (ist der Output echt aus den Inputs abgeleitet?)
Bewiesen, dass **jeder** treibende Input konsumiert wird, nicht aus einer Konstante stammt:
- **Decisions:** +1 Decision → +1 blockierendes `decision`-Item; Summary trägt `title/choice/rationale`
  jener Decision (`test_packet_grows_when_a_decision_is_added`).
- **Gaps:** jede Gap-Zeichenkette wird ihr eigenes blockierendes Item, Summary == Gap-Text
  (`test_packet_grows_when_a_gap_is_added`).
- **Gate-Verdikte:** PASS → nicht-blockierende Evidenz, FAIL → blockierend; nur das Verdikt zu kippen
  kippt nur das `blocking`-Flag; die Abweichungs-Anzahl wird aus `result.failures` gelesen, nicht
  hartcodiert (`test_gate_verdict_drives_blocking_flag`).

## L2 — Drift-Linse (keine stillen Defaults / kein Auto-Approval)
Der Kern-Vertrag ist als Property gepinnt (200 Beispiele):
`is_ratified == (benannter Approver) ∧ (jede blockierende Ref explizit signiert)`
(`test_property_ratified_iff_named_approver_and_all_blocking_signed`). Zusätzlich Einzelfälle:
- leerer Sign-off ratifiziert nichts; anonymer Voll-Sign-off (`approver=""` oder `"   "`) ist NICHT done;
- ein einziges nicht-signiertes blockierendes Item blockiert „done" (keine Teil-Gutschrift);
- ein FAILED Gate muss mit-signiert werden; ein PASSED Gate nicht;
- leeres Packet ist NICHT vakuös done — ein benannter Mensch muss es trotzdem quittieren.
- `SignOff.__post_init__` friert ein übergebenes mutables Set zu `frozenset` ein → nachträgliches
  Mutieren kann keine Approvals nachschmuggeln (`test_signoff_coerces_mutable_set_...`).

## L3 — Vollständigkeits-/Naht-Linse
`ratification_packet` ist order-stabil + deterministisch (Decisions nach `id` sortiert, Gaps in
Reihenfolge, Gates sortiert); zwei unabhängige Builds sind byte-identisch
(`test_packet_is_order_stable_and_deterministic`, Property `..._pure_function_of_its_inputs`). Refs
sind namespaced (`decision:`/`gap:`/`gate:`) → kreuzen nie. `unratified_items` liefert **exakt** die
blockierenden, nicht-approbierten Refs und nie ein Nicht-Blocker-Item.

## L4 — Realisierbarkeits-Linse
Die Property nutzt nur deterministische Auswahl (rotierende Index-Slices, kein Wall-Clock/`random`),
also reproduzierbar. Alle Inputs über die echten Konstruktoren `Decision`/`Specification`/`GateResult`/
`GateFailure` — keine erfundenen Felder, nur deklarierte Deps (`hypothesis`).

## Abgleich GENESIS_PLATFORM_PLAN
Erfüllt die HITL-Ratifikations-Naht der Quality-Engine: Gate, kein Vorschlag (Kernprinzip 2);
Abstention/„Mensch entscheidet" (Kernprinzip 4); Determinismus (Kernprinzip 5).

## Ergebnis
Keine Defekte gefunden. **Quell-Datei unverändert.** Nur ein neuer Charakterisierungstest + dieses
Audit + BUILD_LOG-Eintrag. Volle Belege: `pytest tests/test_ratification_characterization.py`
(14 passed) und `tests/test_ratification.py` (9 passed).
