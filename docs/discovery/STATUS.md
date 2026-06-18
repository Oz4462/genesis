# Universe Explorer — Bau-Status

> Lebende Status-Karte des Mehr-Wochen-Baus aus `GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md`.
> Tags: `[GEBAUT]` = Code + Tests existieren · `[DESIGN]` = geplant · `[HYPOTHESE]` = forschungsoffen.
> Harte Invariante: **kein Trading/ASYA/MT5/Forex** irgendwo; deterministisch + offline; jede
> faktische Behauptung gegated; δ-Asymmetrie auf die eigenen Claims. Grok-Cross-Model-Drift-Check
> (Model `grok-build`) nach jeder Tour; Commit lokal (kein Push).

## Phasen-Überblick

| Phase | Inhalt | Status |
|---|---|---|
| **1 — Kern-Loop** | dimensionale Regression, `discover_new_formulas`, Discovery Graph, Tournament, Rediscovery-Benchmark | `[GEBAUT]` (`65a7262`) |
| **0 — Setup** | Grok-Drift-Harness (`scripts/grok_review.sh`), README-Sektion, Trading-Scrub (Code ZERO), Status-Docs | `[GEBAUT]` |
| **2 — Deep Controller + Surrogat** | `controller.py` (Budget/Tiefe/Checkpoint), `surrogate.py` (Vorfilter, bestätigt nie) | `[GEBAUT]` (`10aa897`, `904092c`) |
| **3 — Grok-Symbiose + Reality Fork** | `symbiosis.py` (Grok=Breite, GENESIS=Verifikation), `reality_fork.py` (counterfactual Welten) | `[GEBAUT]` (`ca8c83c`, `3c76c35`) |
| **4 — Radikal-Features + Live-Test** | `cosmic_insight.py`, `assumption_annihilator.py`, `first_principles.py`, `validation.py` (Out-of-Sample) | `[GEBAUT]` (`40c3acf`,`fa4f284`,`6cfcb31`,`adaa2ca`) |
| **5 — Universe Bridge** | `universe_bridge.py` (Adapter zu externen Simulatoren, bewusst zuletzt) | `[GEBAUT]` (`79b6a39`) |

## Phase 1 — gemessene Evidenz

- `rediscovery_benchmark()` = **100 % Rediscovery / 100 % Red-Team-Catch (5/5)**.
- Kepler: `T = 6.28319 · a^(3/2) · μ^(-1/2)` (C/2π = 1.0, R² = 1.0); ideales Gasgesetz + Newton ebenso.
- Red-Team: dimensional unmöglich → `widerlegt`; verstecktes additives Glied → `unentschieden` (nicht falsch bestätigt).
- 20 Tests grün; volle Offline-Suite 1233 passed / 0 failed / 19 skipped.
- **Cross-Model-Drift-Check (grok-build):** alle 5 Kern-Claims von `engine.py` unabhängig als korrekt
  bestätigt — „Keine mathematische oder dokumentarische Überhöhung."

## Phase 2 — gemessene Evidenz

- **Controller** (`controller.py`, Tour 2.1): Budget + Tiefe-Stufen (fast/medium/max) +
  Checkpoint/Resume. DoD bewiesen: `test_resume_equals_uninterrupted_run` — ein mitten-pausierter
  + fortgesetzter Lauf liefert den identischen Graph + Budget wie ein ununterbrochener
  (pro-Problem-Seed = base_seed+index → positions-unabhängig). 5 Tests grün.
- **Surrogat** (`surrogate.py`, Tour 2.2): Sub-Sample-R²-Vorfilter, der rankt/prunt, aber **nie
  bestätigt** — nur das Gate entscheidet. Bewiesen: ein dimensional unmöglicher Kandidat mit
  Surrogat-Score > 0.99 wird vom Gate trotzdem `widerlegt`. 5 Tests grün.
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" auf alle Controller- und Surrogat-Claims;
  fing einen Namens-Überclaim (`skipped_over_budget` → `deferred_to_resume`), selbst verifiziert + gefixt.
- Volle Offline-Suite nach Phase 2: **1243 passed / 0 failed / 19 skipped**.

## Phase 3 — gemessene Evidenz

- **Symbiose** (`symbiosis.py`, Tour 3.1): Grok = Breite (schlägt Exponenten-Hypothesen vor),
  GENESIS = Verifikation (jeder Vorschlag via `judge_candidate` gegated; Fallback ohne Grok).
  **Live-Beweis (echter grok-build):** Grok schlug {a:1.5,μ:-0.5} (korrekt) + 2 falsche vor →
  GENESIS gated: korrekt `bestätigt`, beide falsch `widerlegt` → validiert `T=6.28319·a^(3/2)·μ^(-1/2)`.
  Groks falsche Vorschläge wurden KEINE Entdeckung. 5 Tests grün.
- **Reality Fork** (`reality_fork.py`, Tour 3.2): Gauss-Dimensions-Fork (r^-(D-1); 3D=r^-2 real,
  4D=r^-3 + Ehrenfest-Notiz) + Konstanten-Fork; jede Fork als counterfactual markiert, nie ein
  Real-Verdikt. 5 Tests grün.
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" auf alle Symbiose- + Reality-Fork-Claims;
  Grok verifizierte die Gauss/Orbital-Physik unabhängig; fand eine Doc-Überziehung (3D-Basis) → gefixt.
- Volle Offline-Suite nach Phase 3: **1253 passed / 0 failed / 19 skipped**.

## Phase 4 — gemessene Evidenz

- **Cosmic Insight** (`cosmic_insight.py`, Tour 4.1): Struktur-Signatur (Exponenten-Multiset) findet
  Cross-Domain-Analogien über den Graph — Newton-Gravitation ~ Coulomb (beide (-2,1,1,1)); proposiert
  nur, bestätigt nie; Kepler-Shape matcht Newton nicht (kein falscher Bridge). 5 Tests.
- **Assumption Annihilator** (`assumption_annihilator.py`, Tour 4.2): Konstante→Variable + Law Rebuilder;
  **δ-Asymmetrie nicht optional** (δ=0.8 → grosse Beweis-Schranke), marginale Verbesserung wird nie als
  Entdeckung akzeptiert (Guardrail gegen Halluzination). 4 Tests.
- **First-Principles** (`first_principles.py`, Tour 4.3): Ableitung aus Axiomen, jeder Schritt durch
  gate_c6 (`verification.derivation`) nachgerechnet → Beweis-Baum; manipulierter Schritt gefangen;
  bounded Ableitungs-Suche. 6 Tests.
- **Out-of-Sample** (`validation.py`, Tour 4.4): Train/Held-out-Split, Gesetz auf Train gefittet + ohne
  Refit auf Held-out gescort → echtes Gesetz generalisiert, Rauschen nicht (anti-p-hacking, kein Leak).
  Pendulum (T=2π·L^½·g^−½) zum Benchmark ergänzt. 4 Tests.
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" auf alle Phase-4-Claims; Grok verifizierte
  Physik (Gauss/Orbital) + Statistik (kein OOS-Leak) selbst; fixte 1 Prosa-Überclaim (δ-Wording).
- Volle Offline-Suite nach Phase 4: **1272 passed / 0 failed / 19 skipped**.

## Phase 5 — gemessene Evidenz (FINALE PHASE)

- **Universe Bridge** (`universe_bridge.py`, Tour 5.1): Adapter, der eine Simulation via
  `SimulatorBackend`-Protokoll läuft und das Ergebnis **zurück durch die Gates** bringt
  (simulate → discover → gate). Das `InProcessReferenceBackend` (echte numpy-Physik: Zwei-Körper-Orbit,
  Harmonischer Oszillator) beweist das Interface + ist Offline-Default → **keine versteckte externe
  Abhängigkeit**; ein echtes HPC-Backend ist ein Drop-in. `should_offload` = Sweep-Größen-Policy.
  Beweis: aus simuliertem Orbit wird Kepler rediscovered + bestätigt (C≈2π). 6 Tests grün.
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" (keine Bypass-Pfade, keine versteckte Dep);
  Anregung „Protokoll explizit machen" → `typing.Protocol SimulatorBackend` ergänzt.
- Volle Offline-Suite nach Phase 5: **1278 passed / 0 failed / 19 skipped**.

## Frontier 6 — über die Power-Law-Familie hinaus (Forschungs-Frontier, kein Phasen-Plan)

- **Tour 6.1 — Mehr-Term-Entdeckung** (`multiterm.py`): additive Gesetze
  `y = Σ Cᵢ·termᵢ (+ Intercept)`. JEDER Term ist dimensional konsistent — jeder enumerierte
  Power-Law-Term erfüllt dieselbe Dimensionsgleichung `A·p=b` wie das Ziel (Gitter max_abs_exp=2.0,
  step=0.5, trifft Keplers ½-Exponenten UND kinematische Ganzzahlen); der optionale Intercept trägt
  die Ziel-Dimension per Konstruktion. **Parsimonie** gegen Overfit: greedy forward selection
  (OMP-Stil), Term nur bei R²-Gewinn > `improvement_threshold`; plus Pruning numerisch
  vernachlässigbarer Terme nach dem exakten linearen Least-Squares-Fit. Gemessen (9 Tests grün):
  Kinematik `s = v0·t + ½·a·t²` → **exakt 2 Terme** (Koeff. 1.0 / 0.5, R²≈1, der greedy-gewählte
  „Blend"-Term wird gepruned); freier Fall `v = 40 + g·t` → Intercept + g·t-Term; Kepler bleibt
  **1 Term** (Parsimonie verwirft den Intercept korrekt); `improvement_threshold` ist ein echtes
  Gate (0.99 → 1 Term, 1e-6 → 2); non-positive Magnituden → `ValueError`.
- **Cross-Model-Drift-Check (grok-build):** keine Math-/Dimensions-/Logik-Fehler; bestätigte den
  `A·p=b`-Filter, die lineare lstsq und die Gitter-Erreichbarkeit der ½-Exponenten unabhängig. Fand
  drei ehrliche **Wording**-Überziehungen (Fallback-Kommentar „best" statt „first"; Pruning als
  „Artefakt" statt „über die gesampelten Daten vernachlässigbar"; „JEDER Term erfüllt A·p=b" muss
  den Intercept ausnehmen) → alle drei selbst verifiziert + im Docstring präzisiert; zusätzlich eine
  echte Kante gehärtet (leerer Pool → klarer `ValueError` statt `IndexError`).
- **Tour 6.2 — Out-of-Sample-Validierung für Mehr-Term (Rest-Risiko-Auflösung)** (`multiterm.py`):
  ein additives Gesetz hat mehr Freiheitsgrade und ist nicht mehr allein am In-Sample-R² zu trauen.
  `multiterm_out_of_sample_validate` fittet das Gesetz (Term-Struktur + Pruning + Koeffizienten) NUR
  auf einem Train-Split und scort es **unverändert** auf dem Held-out (kein Refit, kein Leak — wie
  der Einzel-Gesetz-Validator); `evaluate_multiterm_law` ist die Vorhersage-Primitive. Der Held-out-R²
  fängt **beide** Fehlermodi: Overfit (spurious Terme → Test-R² kollabiert) UND Over-Pruning (echter
  Term fälschlich entfernt → Pruned-Gesetz unterfittet). **Live + 5 Tests grün:** echtes Gesetz
  (Kinematik, train auf 6 Punkten) → Held-out R²=1.0000, gap=0, `generalises=True`, 2 Terme; Rauschen
  → Held-out R²=−0.73, `generalises=False`; erzwungenes Over-Pruning (`prune_rel_tol=0.9`) lässt den
  Held-out-R² messbar fallen (ein gedroppter echter Term bleibt nicht verborgen).
- **Cross-Model-Drift-Check (grok-build):** 0 Korrektheits-Fehler; verifizierte unabhängig, dass
  No-Refit/No-Leak hart erzwungen ist (discover NUR auf Train, evaluate nutzt nur Train-Koeffizienten,
  Held-out nie gefittet). Fand 2 Präzisions-Befunde — veraltete Doc-Referenz auf
  `validation.out_of_sample_validate` (→ auf die neue Funktion umgestellt) und „beide Modi"-Claim ohne
  Over-Pruning-Test (→ expliziten `test_oos_validation_detects_over_pruning` ergänzt, Claim jetzt belegt).

## GESAMTSTAND — alle 5 Phasen + alle Features `[GEBAUT]` + Frontier 6.1 + 6.2

Der gesamte Mehr-Wochen-Plan aus `GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md` ist gebaut, getestet,
grok-build-drift-geprüft und committet (lokal, kein Push). **79 Discovery-Tests** über 15 Module;
`rediscovery_benchmark()` 100 %/100 % (6 Fälle); ZERO Trading-Terme. Mit Frontier 6.1+6.2 sind nun auch
**Summen mehrerer dimensional-gültiger Terme** abgedeckt — inkl. ehrlicher Out-of-Sample-Validierung.
Ehrliche verbleibende Grenze (keine Phase,
sondern Forschungs-Frontier): transzendente Formen (sin/exp/log einer dimensionslosen Gruppe) und
volle GP/symbolische Suche jenseits der Power-Law/π-Gruppen-Familie.

## Drift-Kontroll-Protokoll (jede Tour)

1. Bauen (TDD, an bestehende Gates angedockt).
2. Narrow-Tests → volle Suite grün.
3. `bash scripts/grok_review.sh` (Model `grok-build`) auf eine Claims-Summary des neuen Moduls;
   Grok-Befunde selbst nachkontrollieren (Grok = Vorschlag, nie Wahrheit).
4. Commit lokal + BUILD_LOG-Eintrag.
5. Am Phasenende: README + Docs + Memory aktualisieren.
