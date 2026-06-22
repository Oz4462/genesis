# Depth-Audit: `src/gen/lernmaschine/engine.py` (T02)

**Verdikt: PARTIAL-FACADE → REAL (nach Fix).**

Headline-Claim (PLAN §3.8): „Die Lern- und Verbesserungsmaschine" führt einen
8-Schritt-Lernzyklus aus, leitet ein Delta aus der Idee ab, persistiert es in der
Wissensbasis und wendet das Gelernte auf Frontier/Realisierung an.

Charakterisierungstest: `tests/test_lernmaschine_characterization.py`
(neu, Legacy-Test `tests/test_lernmaschine.py` unangetastet — No-Churn-Regel).

---

## Was vor dem Audit echt war (REAL)

- **Genau 8 Schritte** werden konstruiert und mit echtem Inhalt (finding/action/
  evidence/quelle) befüllt. ✔ (`test_cycle_executes_exactly_eight_distinct_steps`)
- **Persistenz in den Store** (`store.save` bzw. `save_fragment`) ist ein echter
  Schreibvorgang inkl. `ProvenanceRecord`; der Eintrag liegt danach in-memory UND
  als JSON auf Platte. ✔ (`test_persisted_key_is_really_written_and_loadable`,
  `test_persist_writes_to_disk` — frischer Store liest den Eintrag zurück).
- **`quelle` zitiert Lern/§3.8.** ✔ (`test_quelle_cites_lern_and_paragraph`).

## Gefundene Facade-/Defekt-Stellen (jetzt gefixt, nur `engine.py`)

1. **`applied` war IMMER `False` (echter Logik-Bug).**
   `final_applied = (persisted is not None) and (len(steps) == 8)` wurde berechnet,
   **bevor** Schritt 8 an `steps` angehängt wurde → zu dem Zeitpunkt `len(steps) == 7`,
   das Gate konnte nie feuern. Der Kontrakt „Schritt 8: *Erst dann* gilt sie als Teil
   des Systems" war damit dauerhaft unerfüllbar — eine hohle Behauptung.
   **Fix:** Berechnung hinter das Anhängen von Schritt 8 verschoben. `applied` ist
   jetzt genau dann `True`, wenn 8 Schritte durchlaufen sind UND die Persistenz glückte.
   (`test_persisted_key_...` prüft `applied is True`; das Property
   `applied == (persisted_key is not None)` ist Invariante.)

2. **`apply_learning_to_frontier` konsumierte das Cycle-Delta nicht** — die
   angehängten Experimente leiteten sich nur aus den (konstanten) Schritt-`action`-
   Strings ab. Zwei verschiedene Ideen ⇒ identischer revidierter Experimentleiter
   = Konstant-Facade. **Fix:** ein zusätzliches, aus `final_delta` (Idee + Kernlücke)
   abgeleitetes Experiment, dessen Text sich mit dem Delta ändert.
   (`test_apply_to_frontier_changes_when_delta_changes`.)
   Nebenbei: dict-Eingaben für `front_map` wurden bei `closed_gaps_count` falsch über
   `getattr(... , "fehlende_faehigkeiten")` (immer `[]`) ausgewertet — auf
   dict/Dataclass-tolerante Extraktion umgestellt.

3. **`apply_learning_to_realization` spiegelte die Idee nicht** — das Delta war bis
   auf `lern_source` konstant. **Fix:** `idea_addressed` + `primary_gap` aus dem
   Cycle-Delta aufgenommen; gleiches Fragment + zwei Deltas ⇒ verschiedene Revision.
   (`test_apply_to_realization_changes_when_delta_changes`.)

4. **Keine Fail-loud-Guards** (Kernprinzip „keine stillen Defaults"). **Fix:**
   leere/whitespace-Idee bzw. `None` → `ValueError`; `cycle_result is None` in allen
   drei `apply_*`-Funktionen → `ValueError`.
   (`test_empty_idea_raises`, `test_none_source_raises`, `test_apply_with_none_cycle_raises`.)

5. **`final_delta` jetzt nachweislich idee-abgeleitet:** `improvement` wird an die Idee
   gebunden, `primary_gap` ergänzt; verschiedene Ideen ⇒ verschiedene Deltas.
   (`test_final_delta_is_derived_from_idea_input`.)

## Externe Restschuld (NICHT in `engine.py`, bewusst nicht gefixt)

Der Legacy-E2E-Test `test_e2e_full_chain_jetpack_with_lern_and_real_package` ruft
`gen.pipelines.integrator.build_full_mini_realization_package` direkt und schlägt fehl
mit `TypeError: Object of type RunState is not JSON serializable`
(`src/gen/pipelines/integrator.py:~350`, ein `json.dumps` über ein Manifest, das ein
nicht-serialisierbares `RunState`-Objekt enthält). Dieser Defekt liegt in **pipelines/
integrator**, nicht in der Lernmaschine, und ist außerhalb des T02-Dateiscopes
(`["engine.py", "test_lernmaschine_characterization.py", "DEPTH_AUDIT_lernmaschine.md"]`).

- Der Fehler bestand bereits vor diesem Audit (Baseline: `1 failed, 3 passed`).
- Im Lernzyklus selbst ist der Aufruf von `build_full_mini_realization_package`
  in `try/except` gekapselt → der Zyklus läuft robust durch, auch wenn der externe
  Packager-Pfad scheitert. Belegt durch `test_e2e_with_real_packager_collaborator`,
  das den echten Packager als vorbestehenden Collaborator übt und tolerant bleibt.
- **Empfohlene Folgeaufgabe (anderer Task/Scope):** in `integrator.py` das Manifest vor
  `json.dumps` von `RunState`-Referenzen befreien (oder einen `default=`-Encoder
  setzen). Bis dahin bleibt der Legacy-E2E-Test rot — unverändert, gemäß No-Churn-Regel.

## 4 Linsen

- **L1 (Wahrheit):** jede Behauptung im Result trägt `quelle`; Persistenz mit
  `ProvenanceRecord`. Leerer Input → Exception statt geratenem Delta.
- **L2 (Drift):** Input-Sensitivität jetzt erzwungen — Delta und beide `apply_*`-
  Outputs ändern sich nachweisbar mit der Idee.
- **L3 (Vollständigkeit/Naht):** Naht Lernmaschine → Wissensbasis-Store geschlossen
  und round-trip-getestet; Naht → Integrator als realer Collaborator geübt, externe
  Restschuld dokumentiert statt versteckt.
- **L4 (Realisierbarkeit):** Guards + Property-Test (`@given` über beliebige nicht-leere
  Ideen) decken Grenzfälle statt nur Happy-Path ab.
