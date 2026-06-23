# Depth-Audit: `src/gen/frontier.py` (Phase χ — Frontier-Map)

**Verdikt: REAL.** Keine Quelländerung nötig — die Charakterisierungstests sind grün, ohne
dass `frontier.py` editiert wurde.

## Was das Modul behauptet
`build_frontier_map(state, *, confidence_threshold=0.7)` synthetisiert aus den bereits
gegateten Phasen-Outputs eines Laufs eine ehrliche Karte: **Known Regions** (Cluster von
VERIFIED-Claims, die im Report/Solution/Spec **tatsächlich genutzt** wurden und
`confidence ≥ threshold` erfüllen) und **Frontier Edges** (die echten, im Lauf
aufgetauchten Lücken + alle REFUTED/UNSUPPORTED-Claims). Rein, LLM-frei, deterministisch
(A5): gleiche `RunState` → gleiche `FrontierMap`.

## Befund: keine Fassade
Die Karte ist eine **reine Funktion des `RunState`**, keine Konstante:

- **Input wird konsumiert.** `run_id`/`topic` fließen aus `state.question`; jede Region-Label
  ist der echte (auf 80 Zeichen geclippte) Claim-Text; jede Edge ist in einer realen Lücke
  bzw. einer un-etablierten Claim-id verankert. Test
  `test_different_runs_yield_meaningfully_different_maps` beweist, dass zwei verschiedene
  Läufe **bedeutsam verschiedene** Karten erzeugen — eine gecannte Karte würde dasselbe
  liefern.
- **Kein erfundener Output.** `test_every_emitted_region_and_edge_traces_to_a_real_input_field`
  zeigt, dass jede Region/Edge auf ein konkretes `RunState`-Feld zurückführbar ist.
- **Echte β/γ-Kette.** `test_synthesis_genuinely_spans_all_three_gated_holders` belegt, dass
  Regionen aus Report + SolutionReport (grounding+tradeoffs) + Specification stammen, in
  First-Seen-Reihenfolge dedupliziert.
- **`used`-Gate ist real.** `test_dropping_the_report_drops_the_region`: ein VERIFIED-Claim
  wird nur dann „bekanntes Terrain", wenn eine gegatete Phase ihn benutzt — entferne den
  Report, verschwindet die Region.

## Negativ-/Fail-Loud-Pfad (dokumentiert, feuert exakt)
- `FrontierEdge.__post_init__` wirft `ValueError("... non-empty question and grounded_in ...")`
  bei leerem/whitespace-only `question`/`grounded_in` — der Guard, auf den der Builder baut
  (`test_frontieredge_guard_rejects_an_invented_blank_edge`).
- `build_frontier_map` **überspringt** leere Gap-Strings (`if not gap.strip(): continue`),
  damit es weder crasht noch eine Edge aus dem Nichts erfindet
  (`test_empty_gaps_are_skipped_so_no_invented_edge_is_built`). Der Skip ist genau das, was
  zwischen einem realen Lauf und der `ValueError` steht.
- Leerer Lauf → ehrlich leere Karte (Abstention), nicht fabrizierter Inhalt
  (`test_empty_run_is_honest_abstention_not_a_fabricated_map`).

## Property-based Invarianten (Hypothesis)
- `test_edge_count_equals_open_claims_when_unused`: ohne Report/Spec werden **genau** die
  REFUTED+UNSUPPORTED-Claims zu Edges; VERIFIED/UNVERIFIED nie.
- `test_edges_are_exactly_the_nonblank_gaps`: Report-Gaps → Edges genau dann, wenn nicht-blank
  — nie mehr, nie weniger, nie erfunden.

## 4 Linsen
- **L1 Wahrheit:** Headline-Anspruch hält gegen Cross-Check — Output ist faithful function des
  Inputs; jede Region/Edge ist quellenverankert (keine fabrizierte Gewissheit).
- **L2 Drift:** Kein stiller Default — leere Gaps werden gedroppt, leerer Lauf abstiniert;
  Metadaten (`run_id`/`topic`/`produced_by`) stammen ausschließlich aus dem State.
- **L3 Vollständigkeit/Naht:** Alle drei Halter (Report/Solution/Spec) und beide Edge-Quellen
  (Gaps + REFUTED/UNSUPPORTED) sind abgedeckt; Determinismus (A5) geprüft. Legacy-Test
  `tests/test_frontier.py` bleibt grün (24 passed) → keine Regression.
- **L4 Realisierbarkeit:** Reine stdlib-/`core.state`-Konstruktoren, keine neue Abhängigkeit,
  kein Netz/Subprozess; Tests deterministisch.

## Abgleich GENESIS_PLATFORM_PLAN
Phase χ (Frontier-Map, HORIZON §2C) ist als ehrliche Karte des Bekannten/Unbekannten
verlangt — `frontier.py` erfüllt das input-getrieben und gate-kompatibel. Offen bleibt
nichts in diesem Modul; GATE χ re-prüft die Karte (Defense-in-Depth) separat.

## Geänderte Dateien
- `tests/test_frontier_characterization.py` (neu) — 11 Tests, alle grün.
- `docs/audit/DEPTH_AUDIT_frontier.md` (dieses Dokument).
- `src/gen/frontier.py` — **unverändert** (REAL, „change nothing if correct").
