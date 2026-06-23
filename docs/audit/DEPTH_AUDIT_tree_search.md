# Depth-Audit: `src/gen/discovery/tree_search.py`

**Verdikt: REAL.** Keine Fassade. `best_first_search` ist eine echte, gate-getriebene Best-First-Suche;
`directed_search` findet aus einem absichtlich FALSCHEN Exponenten-Start ein gate-bestätigtes Gesetz,
ausschließlich von `judge_candidate` (dem deterministischen Gate) bewertet. Es war **keine** Quell-Korrektur
nötig — der einzige Eingriff ist eine Docstring-Klärung der `max_depth`-Semantik (Wachstums-Grenze, der
Randknoten wird noch besucht). Tie-Break-Garantie (monotoner Zähler) ebenfalls dokumentiert.

## Headline-Claim & Beweis
Behauptung: *Best-First-Expansion wird rein vom deterministischen Gate-Score getrieben — ein Knoten kann
sich nicht selbst befördern; dedup nach `key`; begrenzt durch `max_nodes`/`max_depth`; Ties nach
Einfügereihenfolge; `directed_search` läuft vom falschen Start zu einem gate-bestätigten Gesetz.*

Neue Datei `tests/test_tree_search_characterization.py` (17 Tests, alle grün; Legacy `test_tree_search.py`
unverändert grün) belegt jeden Teil mit beobachtbarem Verhalten, das bei einer Fassade FEHLSCHLAGEN würde:

- **Best-First-Reihenfolge** (`test_expansion_order_is_strictly_best_first`): Aufzeichnung der `expand`-Aufrufe
  zeigt streng absteigende Gate-Qualität `[5,4,3,2,1]` — kein verstecktes BFS/DFS.
- **Tie-Break nach Einfügereihenfolge** (`test_ties_break_by_insertion_order`): gleichqualitative Wurzeln
  kommen FIFO heraus (`[a,b,c,d]`).
- **Dedup nach `key`** (`test_dedup_by_key_expands_each_key_once`, `test_custom_key_collapses_distinct_states`):
  ein zyklisch/duplizierendes `expand` terminiert; ein `key` kollabiert verschiedene Zustände auf eine Expansion.
- **`max_nodes`-Grenze** (`test_max_nodes_caps_expansions`): exakt `max_nodes` Expansionen in unendlichem Raum.
- **`max_depth`-Grenze** (`test_max_depth_bounds_the_tree`): kein Knoten tiefer als `max_depth` wird erzeugt.
- **Gate als alleiniges Orakel** (`test_passed_comes_only_from_score_not_quality`): ein höherqualitativer,
  aber NICHT bestandener Knoten verliert gegen den vom Gate als `passed` markierten — rohe Qualität kann das
  Gate nicht umgehen.
- **Ehrliche Abstention** (`test_best_falls_back_to_highest_quality_when_nothing_passes`,
  `..._does_not_fabricate_a_pass_on_an_impossible_target`): ohne bestandenen Knoten ist `best.passed=False`
  und `passing=()` — kein erfundener Erfolg, auch nicht bei dimensional unmöglichem Ziel.
- **`directed_search`** (`..._recovers_a_confirmed_law_from_a_wrong_start`): Start `{a:1.0, mu:-0.5}` →
  bestätigtes Kepler `a=3/2, mu=-1/2`; jeder als `passing` gemeldete Knoten trägt wirklich das Gate-Verdikt.
- **Negativ** (`test_max_nodes_below_one_raises` für 0/-1/-5; `..._directed_search_propagates_the_max_nodes_guard`):
  `max_nodes < 1` → `ValueError`, auch durch `directed_search` hindurch.
- **Determinismus** (zwei Tests): identisches Ergebnis über zwei Läufe (Primitiv + `directed_search`).
- **Property-based** (`test_property_best_first_order_bound_and_dedup`, Hypothesis, 200 Beispiele): für jede
  Wurzel-Multimenge und jedes `max_nodes` gilt absteigende Qualität, `nodes_expanded ≤ max_nodes` und
  `nodes_expanded == min(unique_roots, max_nodes)` (Dedup) — der Invarianten-Beleg über den Beispielen hinaus.

## 4 Linsen
- **L1 Wahrheit:** Der Score `passed` stammt einzig aus `score(state)` bzw. `judge_candidate`; ein Knoten
  kann sich nicht selbst befördern. `directed_search` rekonstruiert reale Kepler-Exponenten aus falschem Start
  — keine Halluzination, sondern dimensional + Fit-gegatete Entdeckung.
- **L2 Drift:** Tie-Break ist deterministisch über einen monotonen Einfügezähler; `SearchNode` wird nie selbst
  verglichen (Zähler ist eindeutig). Determinismus über zwei Läufe bewiesen. Keine versteckte Nichtdeterminismus-Quelle.
- **L3 Vollständigkeit/Naht:** Naht zu `engine.py` (`candidate_from_exponents`/`judge_candidate`) sauber; die
  Rescue-Naht `discover_new_formulas(refine_with_search=True)` ruft `directed_search` nur, wenn der Single-Shot-SR
  nichts bestätigte, und kann nur ADD-en — keine Verdikt-Überschreibung. Legacy-Test bleibt grün (keine Regression).
- **L4 Realisierbarkeit:** Offline, numpy-frei für das Primitiv, stdlib-`heapq`. Grenzen (`max_nodes`/`max_depth`,
  Exponenten-Clip ±4 in `_expand`) verhindern unbeschränkten Lauf/Fit-Overflow. `max_nodes < 1` scheitert laut
  statt still — entspricht „keine stillen Defaults bei faktischen Dingen".

## Abgleich GENESIS_PLATFORM_PLAN / Kernprinzipien
Erfüllt Prinzip 2 (Verifikation als Gate, nicht Vorschlag): das Gate ist das alleinige Knoten-Orakel, exakt der
Punkt der AI-Scientist-v2-Adaption, der GENESIS ehrlich macht. Erfüllt Prinzip 5 (Determinismus/Reproduzierbarkeit).
Offene Grenze (außerhalb dieses Moduls): die Exponenten-Nachbarschaft ist ±`step`-Gitter — eine GP-/kontinuierliche
Suche bleibt im Backlog (Frontier), unverändert von diesem Audit.
