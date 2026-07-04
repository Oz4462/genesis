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

- **Tour 6.3 — Transzendente Formen** (`transcendental.py`): Entdeckung von `y = C·f(α·π) + D` mit
  `f ∈ {exp, log, sin, tanh}` über eine **dimensionslose** π-Gruppe. Buckingham-π: eine transzendente
  Funktion ist die Taylor-Reihe einer reinen Zahl → das Argument MUSS dimensionslos sein, also wird die
  π-Gruppe aus dem **Nullraum** der Quell-Dimensionsmatrix gebildet (`A·p = 0`, gleiches Gitter wie die
  Power-Law-Suche, beide Orientierungen). `C` trägt die Ziel-Dimension (gefitteter Skalen-Parameter),
  der Fit ist **nichtlinear in α** → `scipy.optimize.curve_fit` mit fixen, deterministischen Startwerten.
  **Ehrliches Gate (das Kernstück):** der Rivale ist eine Power-Law DERSELBEN π-Familie `C·π^β + D`;
  `bestaetigt` nur wenn die beste Transzendente im Wesentlichen exakt ist (R² ≥ 0.999) UND die beste
  Power-of-a-group über ALLE Gruppen es NICHT ist → sonst `unentschieden` (eine Power-Law erklärt es
  gleich gut, kein Über-Claim) bzw. `widerlegt` (kein dimensionsloses Argument). **Live + 7 Tests grün:**
  Exp-Zerfall `x=10·exp(−t/τ)` → `bestaetigt` (R²=1.0, pow-Baseline 0.998); Schwingung `y=3·sin(2·t/τ)+5`
  → `bestaetigt` (pow-Baseline 0.66); Quadrat `y=7·(t/τ)²` → `unentschieden` (pow-Baseline 1.0 fängt den
  Über-Claim); Kepler → `widerlegt` (kein Nullraum bei (a,μ)).
- **Cross-Model-Drift-Check (grok-build):** 0 Math-/Dimensions-/Logik-Fehler; bestätigte Nullraum=dimensionslos
  (Buckingham) und das Gate unabhängig. Fand 3 Präzisions-Befunde — stale „beat-by-margin"- + „same-group"-Prosa
  (→ auf die Threshold-Regel / „beste Power-of-a-group über alle Gruppen" umgestellt) und einen zu schwachen
  Quadrat-Test mit falscher Docstring (`!= bestaetigt` → jetzt `== unentschieden` + `powerlaw_r2 ≈ 1.0` gepinnt).

- **Tour 6.4 — Active Resolution of Uncertainty** (`active_resolution.py`, in der Q&A-Runde mit
  grok-build als stärkster einzigartiger Hebel priorisiert): der **aktive nächste Zug nach
  `unentschieden`**. Wenn der Discovery-Arm zwei dimensional-gültige Rivalen findet, die gleich gut
  passen (transzendent vs. Power-of-a-group), berechnet `propose_resolution` deterministisch +
  LLM-frei + ohne Hardware die **Messung, die den Gleichstand bricht**: `discover_rivals` liefert
  beide gefitteten Formen, `evaluate_rival` wertet sie auf neuen Daten aus (kein Refit), und der
  Operator findet im **hart begrenzten** Bereich `[lo/f, hi·f]` (f≤3) die Region maximaler Divergenz
  und gibt einen `DecisionSpec` zurück: welcher Input, welcher Bereich, ein **Spread** von Messpunkten
  (nicht der Einzel-Peak — den biegt ein 3-Parameter-Rivale hin; der Spread zwingt die SHAPE), die
  erwartete Signatur jedes Rivalen, das Verdikt-Kriterium. **Ehrliches Gate:** `discriminating` nur
  wenn Spitzen-Divergenz ≥ `min_discrimination` (5) Rausch-Böden — sonst ehrlich „keine
  Unterscheidungskraft, mehr Daten im beobachteten Regime" statt eines erfundenen Extrapolations-
  Experiments. **Live + 7 Tests grün (DER Akzeptanztest = Flip):** Schmalband-Exp-Zerfall →
  `unentschieden` (exp R²=1.0, pow R²=0.99997) → `propose_resolution` (discriminating, ratio≈315,
  Spread [0.33…9.0]) → mit wahren Daten augmentieren → re-judge **flippt zu `bestaetigt`** (pow-R²
  fällt auf 0.996 < Bar). Negativ: f=1.02 → `discriminating=False` (ratio≈1.6). Macht GENESIS vom
  **passiven Verifizierer zum aktiven Instrument** — optimal-experimental-design-im-Geist auf
  symbolische dimensionale Gesetze, gegated gegen Extrapolations-Artefakte.
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" (Math + Implementierung + Claims + 6/7 Tests
  unabhängig verifiziert; Spread-statt-Cluster-Argument „mathematisch sauber" bestätigt). Fand 3
  Mini-Präzisionen — „diverge MOST/point" (singular) → „Spread"-Wording präzisiert, „optimal
  experimental design" → „im Geist, kein formales Fisher-Design" entschärft, `None`-Rivale → klarer
  `ValueError` statt `AttributeError` (+Test). Selbst nachkontrolliert + gefixt.

- **Tour 6.5 — Minimal-Correction bei Komposition** (`composition.py`, die ZWEITE komplementäre
  Fähigkeit aus der grok-Q&A-Runde): „**Gilt die naive Superposition gequellter Gesetze — und wenn
  nicht, was ist die kleinste Korrektur?**". `discover_correction(problem, baseline_prediction)` bildet
  das Residuum `r = y − y_base` und fährt dimensionale SR **nur auf r**. Kernpunkt: r ist
  **vorzeichenbehaftet**, ein Power-Law-Term ein positives Monom → Fit `r ≈ Σ Cᵢ·termᵢ` mit dem
  Vorzeichen in den linearen lstsq-Koeffizienten, jeder Term dimensional konsistent mit r (= Ziel-Dim,
  via `A·p=b`; Reuse der `multiterm`-Internas). **Ehrliches Gate (δ-Asymmetrie, eine Korrektur ist ein
  CLAIM):** `korrektur_noetig` nur wenn `residual_explained ≥ 0.9` UND `corrected−baseline > 1e-3` UND
  die Korrektur **Leave-One-Out überlebt** (`loo_r2 ≥ 0.5` — strukturiertes Rauschen, das die
  In-Sample-Bar streift, kollabiert out-of-fold) — sonst `vollstaendig` (KEINE Korrektur behauptet,
  *innerhalb* der additiven Monom-Basis). **Live + 7 Tests grün:** Kopplung `y = x + ½·k·x²`,
  baseline `x` → findet **exakt `Korrektur = 0.5·x²·k`** (baseline-R²=0.16 → corrected-R²=1.0,
  residual_explained=1.0, LOO-R²>0.99); baseline==y → `vollstaendig`; Rauschen → `vollstaendig`
  (residual_explained=0.21 < 0.9). `relative_correction` = RMS-Anteil → „Superposition gilt bis ~X %".
- **Cross-Model-Drift-Check (grok-build):** „KEIN DRIFT" (signierter Residuen-Fit + Gate „mathematisch
  solide", dokumentierte Grenze „ehrlich und nicht übertrieben"). Empfehlung „OOS rein + Verdikt-Semantik
  schärfen" → umgesetzt: **Leave-One-Out als dritte Gate-Bedingung** ergänzt (+Test) und Docstring
  präzisiert (`vollstaendig` = „keine Korrektur in der additiven Basis", NICHT „physikalisch vollständig").

- **Tour 6.6 — Multiplikative Kopplungen** (`multiplicative.py`, 2026-07-04): Produktformen
  `y = C·π1^a·f(α·π2 [+φ])` — Potenz EINER dimensionslosen π-Gruppe mal transzendente Modulation
  einer anderen (beide aus dem Nullraum `A·p = 0`, geordnete Paare inkl. π1==π2; `C` trägt allein
  die Ziel-Dimension). **Zwei Fit-Pfade:** (1) LOG-PFAD nur wo er sound ist — für `f=exp` UND
  strikt positives Ziel ist `log y = log C + a·log π1 + α·π2` EXAKT linear (deterministische
  lstsq, seedet zusätzlich den direkten Fit); bei irgendeinem y≤0 wird der Pfad VERWEIGERT
  (übersprungen, NIE ein stilles `abs()`) und (2) direkter `curve_fit` mit fixen Startwerten
  (vorzeichenfrei in y) läuft immer. Gefittete EXPONENTEN sind auf ±8 begrenzt
  (`MAX_FIT_EXPONENT`: jenseits davon ist eine Potenz keine Kandidaten-Physik mehr, sondern eine
  numerische Stufen-Imitation, deren Extrapolation überläuft — live beobachtet, NaN im
  Divergenz-Suchlauf; Hybrid: schnelles LM, gebundenes TRF nur bei degenerierter Lösung).
  **Ehrliches Gate wie 6.3:** Rivale = reine Power-Law `C·π1^p·π2^q + D` über DIESELBEN Paare
  (MIT Offset, den die Produktform nicht bekommt — der Rivale ist mindestens so flexibel, Bias
  Richtung `unentschieden`, nie Richtung Über-Claim); `bestaetigt` nur wenn Produktform R²≥0.999
  UND Rivale <0.999. **Gemessen (16 Tests grün):** Wien-Form `u = 2·x³·e^(−x)` (x=t/τ) →
  `bestaetigt` exakt: a_eff=3.0, α_eff=−1.0, C=2.0 (R²=1.0000000, pow-Rivale 0.5009), Log-Pfad
  aktiv; negatives Ziel `−2·x³·e^(−x)` → Log-Pfad verweigert, direkter Pfad findet C=−2 exakt;
  reine Potenz `y=4·x²` → `unentschieden` (beide 1.0 — kein Produkt-Über-Claim); Rauschen →
  `widerlegt` (R²=0.17); Kepler (a,μ) → `widerlegt` („kein dimensionsloses Argument").
  **OOS (6.2-Naht):** `product_out_of_sample_validate` — Wien train→test R²=1.0000/1.0000,
  `generalises=True`; Rauschen test-R²=−0.31, `generalises=False`. **Flip (6.4-Naht, DER
  Akzeptanztest):** Schmalband-Wien t∈[2.0,2.4] → `unentschieden` (exp 1.0, pow2 0.99997) →
  `discover_product_rivals` + `propose_resolution` (dispatcht jetzt auch `ProductRival`;
  discriminating, ratio≈11042× Rausch-Boden, Spread [0.667…7.2]) → wahre Daten am Spread →
  re-judge **flippt zu `bestaetigt`** (pow2 kollabiert auf 0.43). ZWEITE Fähigkeit:
  `discover_multiplicative_correction(problem, y_base)` — multiplikatives Residuum als
  **RATIO** `r = y/y_base` (dimensionslos), Division nur wo `|y_base| > ε·max|y_base|` überall
  (sonst harter ValueError „Gate-Verweigerung" — an einer Baseline-Nullstelle ist das Ratio ein
  Divisions-Artefakt; kein stilles Maskieren), Modulations-Bibliothek = 6.3-Formen + Phase im
  sin (cos = sin(·+π/2)), Occam-Wächter: ist die Power-Modulation `C·π^β+D` im Wesentlichen
  exakt, gewinnt sie IMMER über jede Transzendente; konstantes Ratio = Reskalierung, NIE ein
  π-Kopplungs-Claim. **Dieselben strengen 6.5-Gates:** `ratio_explained ≥ 0.9` ∧ `ΔR² > 1e-3` ∧
  Leave-One-Out `≥ 0.5`. **Gemessen:** gedämpfte Schwingung `x = 4·e^(−0.3t)·cos(2t)`, Baseline
  `4·e^(−0.3t)` (UNGLEICHMÄSSIGES Sampling — auf äquidistantem Gitter ist eine Sinus-Modulation
  nur bis Aliasing identifizierbar, dokumentierte Daten-Grenze) → findet **exakt
  `sin(1.0·(t·ω) + 1.5707963…)` = `cos(ωt)`** (C=1.000000000, φ=π/2 auf 1e-10, D≈0,
  ratio_explained=1.0, corrected R²=1.0, LOO=1.0) → `korrektur_noetig`; baseline==y →
  `vollstaendig` (konstante Reskalierung); Rausch-Ratio → `vollstaendig` (ratio_expl=0.54,
  LOO=0.09 — beide Gates greifen); Potenz-Modulation `(t/τ)²` → Form **pow** behauptet, nie
  transzendent verkleidet. Negativtests: Baseline-Nullstelle → ValueError; Längen-Mismatch →
  ValueError; non-positive Quellen → ValueError.
- **Cross-Model-Drift-Check (grok-build): NACHZUHOLEN** — Grok-CLI am 2026-07-04 nicht
  erreichbar (gleicher Outage-Präzedenzfall wie Deep-Review 7–9 im WORK_QUEUE-Ledger). Die
  Tour-6.6-Claims (Buckingham-π-Paare, Log-Pfad-Soundness, Exponenten-Schranke, Rivalen-Gate,
  Ratio-Gates, Aliasing-Grenze) sind für den nachgeholten Review als Claims-Summary in diesem
  Absatz fixiert.

- **Tour 6.7 — Blinde Zwei-Transzendenten-Produkte** (`blind_product.py`, 2026-07-04): die in
  6.6 explizit offen gelassene Grenze — `y = C·f(α·π1)·g(β·π2 [+φ])` OHNE deklarierte Baseline
  (6.6 fand die gedämpfte Schwingung nur als Ratio-Korrektur zur gegebenen Hüllkurve). Beide
  Argumente sind π-Gruppen aus dem Nullraum `A·p = 0`; `C` trägt allein die Ziel-Dimension; die
  Fit-Maschinerie ist 6.6-Reuse (`ProductForm`, deterministische Starts, Hybrid-LM/TRF; die
  blinden Formen tragen KEINEN gefitteten Potenz-Exponenten — die ±8-Schranke von 6.6 greift
  nur bei den Rivalen, geerbt über die wiederverwendeten Fitter). **Identifizierbarkeits-Wächter
  (der Design-Kern):** (a) `exp·exp` ist aus der Paar-Bibliothek AUSGESCHLOSSEN —
  `exp(u)·exp(v) = exp(u+v)` ist strukturell EIN Exponential (auf gleichem Argument nur α+β
  identifizierbar, ein Parameter-Grat, kein Gesetz); (b) Produktformeln/flache Faktoren
  (sin·cos-Identitäten, α≈0-exp, gesättigtes tanh) kollabieren über die Occam-Leiter — der
  Ein-Transzendenten-Rivale ist die 6.6-Modulations-Bibliothek MIT Phase + Offset, alles was
  EINE Transzendente darstellt, macht ihn exakt → `unentschieden` mit benanntem
  `occam_winner`, nie ein 6.7-Über-Claim; (c) Vorzeichen/Phase kanonisiert (`−cos = cos(·+π)`,
  `sin(−βx+φ) = sin(βx+π−φ)`, tanh-Vorzeichen in C): C>0 wo eine Phase das Vorzeichen tragen
  kann, Frequenzen >0, Phasen in [0,2π) — genau EINE Parametrisierung pro Gesetz. **Ehrliches
  Gate (6.6-Pflichten, verschärft):** DREI Rivalen über dieselben Gruppen/Paare — Power-Law MIT
  Offset `C·π1^p·π2^q+D` (mindestens so flexibel, Bias Richtung `unentschieden`),
  Ein-Transzendenten-Familie (Phase+Offset), 6.6-Produktform-mit-Power — UND eine
  OOS-Bestätigung: der Sieger wird auf einem deterministischen Train-Split nachgefittet und
  muss auf den Held-out-Punkten ≥ `DEFAULT_GENERALISES_R2` (0.99) übertragen, sonst bleibt es
  `unentschieden`. **Gemessen (9 Tests grün, unregelmäßiges Sampling gegen Aliasing wie 6.6):**
  gedämpfte Schwingung `x = 4·e^(−0.3t)·cos(2t)` BLIND wiederentdeckt als exp_sin-Paar mit
  **C=4.0, α=−0.3, β=2.0, φ=π/2 je auf <1e-6** (R²=1.0000000000; Rivalen pow2 0.411 / einzel
  0.772 / produkt_potenz 0.964 — alle unter der Bar; OOS-Confirm 1.000) → `bestaetigt`;
  negiertes Ziel → kanonisch C=+4, φ=3π/2 (Wächter c); `5·e^(−0.3t)·e^(−0.4t)` →
  `unentschieden`, `occam_winner=einzel_transzendent` (Wächter a: EIN Exponential, kein
  Doppel-Claim); reines `3·cos(2t)` → `unentschieden`, Kollaps auf die Ein-Transzendenten-Form
  (Wächter b); Rauschen → `widerlegt` (R²=0.21); Kepler → `widerlegt` („kein dimensionsloses
  Argument"). **OOS (6.2-Naht):** train→test R²=1.0000/1.0000, gap<1e-6. **Flip (6.4-Naht):**
  Schmalband t∈[0.8,2.0] → `unentschieden` (blind 1.0, stärkster einfacher Rivale = 6.6-sin
  0.99999) → `discover_blind_rivals` übergibt den STÄRKSTEN einfacheren evaluierbaren Rivalen,
  `propose_resolution` dispatcht jetzt auch `BlindRival` (ratio≈1343× Rausch-Boden, Spread
  [0.267…6.0]) → wahre Daten am Spread → **flippt zu `bestaetigt`** mit exakten Parametern,
  alle Rivalen kollabieren (pow2 0.48, einzel 0.85, produkt_potenz 0.97).
- **Cross-Model-Drift-Check (grok-build): NACHZUHOLEN** — Grok-CLI am 2026-07-04 weiterhin
  nicht erreichbar (gleicher Outage-Präzedenzfall wie 6.6). Die Tour-6.7-Claims
  (exp·exp-Degeneration = Parameter-Grat, Occam-Leiter über drei Rivalen-Familien,
  Sinus-Identitäten der Kanonisierung, OOS-Confirm-Gate, Aliasing-Grenze) sind für den
  nachgeholten Review als Claims-Summary in diesem Absatz fixiert.

- **Tour 6.8 — Additive π-Argumente in EINER Transzendenten** (`additive_argument.py`,
  2026-07-04): die in 6.7 explizit offen gelassene Grenze (A) — `y = C·f(α·π1 + β·π2) + D`,
  EIN Transzendent mit additiver Zwei-π-Kombination als Argument (physikalisch: Arrhenius mit
  zwei Beiträgen in einem Exponenten). Beide π-Gruppen aus dem Nullraum `A·p = 0`; `C` trägt
  allein die Ziel-Dimension; Fit-Maschinerie 6.6/6.7-Reuse (`ProductForm`, deterministische
  Starts, Hybrid-LM/TRF); für `f=exp` bei strikt positivem Ziel EXAKTER Log-Linear-SEED
  `log y = log C + α·π1 + β·π2` (nur Seed, nie Verdikt — mit Offset D ist der Log-Pfad unsound;
  y≤0 verweigert den Seed, kein stilles `abs()`). **Identifizierbarkeits-Wächter (Design-Kern):**
  (a) KANONISCHE HEIMAT von `exp·exp`: `exp(α·π1+β·π2) = exp(α·π1)·exp(β·π2)` ist GENAU das
  Paar, das 6.7 aus seiner Bibliothek ausschloss — 6.8 ist seine eine Darstellung; das
  entdeckte exp-Gesetz benennt die Produkt-Äquivalenz in `product_equivalent` (nur bei
  vernachlässigbarem D — mit Offset gilt die Identität nicht), und 6.7 erhebt auf denselben
  Daten NIE einen rivalisierenden Zwei-Transzendenten-Claim (getestet) — kein Doppel-Claim;
  (b) AFFINE-RIDGE-Paare übersprungen (`AFFINE_RIDGE_TOL=1e-8`): ist π2 (numerisch) affin in π1
  (punktweise proportionale Gruppen aus gleich-unit-Konstanten, π1==π2, Konstanten-Gruppen),
  hat `α·π1+β·π2` weniger identifizierbare Richtungen als Parameter — das affine Analogon des
  exp·exp-Grats; bewusst eng (Float-Rauschen-Skala): ein schmales, aber echt gekrümmtes Band
  triggert NICHT (das behandelt die Occam-Leiter); (c) β=0 kollabiert auf 6.3 über die Leiter
  (`einzel_transzendent` wird exakt → `unentschieden`, nie ein Zwei-Gruppen-Über-Claim);
  (d) Kanonisierung (`sin(−u+φ)=sin(u+(π−φ))`, `−sin(u)=sin(u+π)`, tanh-Vorzeichen in C;
  führender Koeffizient α>0, C>0 wo eine Phase das Vorzeichen trägt, Phasen in [0,2π); Paar-
  Ordnung durch Enumeration i<j fixiert — keine getauschte Duplikat-Parametrisierung). `log` als
  f bewusst ABWESEND (Positivität eines SIGNIERTEN gefitteten Arguments nicht vorab beweisbar).
  **Ehrliches Gate (6.7-Pflichten, um eine Sprosse verlängert):** VIER Rivalen über dieselben
  Gruppen/Paare — pow2 MIT Offset ≻ Ein-Transzendente (Phase+Offset) ≻ 6.6-Produktform ≻
  6.7-Blind-Paar — UND OOS-Confirm (Train-Refit muss ≥0.99 auf Held-out übertragen, sonst
  `unentschieden`). **Gemessen (12 Tests grün):** Arrhenius-artig `k = 2·exp(−θ/T − 0.5·P/p0)`
  (T, P variieren; θ, p0 Konstanten; WEITES zweiseitiges Regime θ/T∈[0.33,4], P/p0∈[0.1,5]) →
  `bestaetigt` exakt: **C=2, α=−1, β=−0.5, D≈5e-10 je <1e-6** (R²=1.0; Rivalen pow2 0.922 /
  einzel 0.928 / produkt_potenz 0.984 / blind 0.997; OOS-Confirm 1.0; `product_equivalent`
  benannt) — auf ENGEM Band (θ/T≈0.8–1.2, beim Bauen gemessen) imitieren tanh/sin das
  Exponential >0.999 → ehrlich `unentschieden`, Regime-Weite ist die 6.4-Lektion zur
  Design-Zeit; Chirp `3·sin(1.5x + 0.8√x + 0.4)` (x=t/τ) → `bestaetigt` exakt (C=3, α=1.5,
  β=0.8, φ=0.4 je <1e-6; Rivalen 0.270/0.997/0.997/0.999 — keine Familie folgt global einer
  driftenden Frequenz; OOS 1.0); negierter Chirp kanonisch C=+3, α>0, φ∈[0,2π); **δ-Asymmetrie
  in Reinform:** Ein-Input-Zweiskalen-Exponential `3·exp(−1.2x+2√x)` wird in-family EXAKT
  gefittet (R²=1.0) und trotzdem NICHT behauptet — ein 6.7-exp·sin-Paar imitiert die
  Ein-Buckel-Form ≥0.999 → `unentschieden` mit `occam_winner=blind_produkt` (Test pinnt genau
  das); β=0 (`2·exp(−0.8x)`) → Kollaps `einzel_transzendent`; Ridge (τ1, τ2 gleiche Unit,
  Daten = EIN Exponential) → Kollaps, kein Grat-Claim; Rauschen → `widerlegt`; Kepler →
  `widerlegt` („kein dimensionsloses Argument"). **OOS (6.2-Naht):** train→test R²=1.0/1.0,
  gap<1e-6. **Flip (6.4-Naht):** Chirp-Schmalband t∈[0.8,2.0] (< eine Periode) →
  `unentschieden` (stärkster einfacher Rivale 0.999998) → `propose_resolution` dispatcht jetzt
  auch `AdditiveArgumentRival` → wahre Daten am Spread → **flippt zu `bestaetigt`** mit exakten
  Koeffizienten, einzel/blind kollabieren (<0.999). **(B) echte Komposition
  `y = C·f(β·g(α·π)) + D` nach Analyse ABGELEHNT (Ehrlichkeit vor Feature-Zahl),** drei
  konkrete Gründe im Modul-Docstring fixiert: (1) DATENABHÄNGIGER Parameter-Grat — wo g nur im
  linearen Regime angeregt ist, ist nur `α·β·g′(0)` identifizierbar (der exp·exp-Grat, aber
  nicht strukturell einmalig ausschließbar, sondern bandabhängig; bräuchte einen Pro-Fit-Beweis
  der inneren Nichtlinearität); (2) KOLLAPS-AMBIGUITÄT — wo f nur linear angeregt ist, IST die
  Komposition die 6.3-Einzelform; zwischen (1) und (2) endet fast jedes endliche Band
  `unentschieden`, kein ehrlich gewinnbarer Fall ohne präzise platzierte 6.4-Messung;
  (3) KEINE ALLGEMEINE KANONISIERUNG — `exp(−k·sin²θ) = e^(−k/2)·exp((k/2)·cos 2θ)`: dieselbe
  Klasse hat mehrere exakte In-Familie-Darstellungen, und anders als bei 6.7(c) existiert keine
  endliche Identitäten-Liste für gemischte f∘g — „genau eine Parametrisierung pro Gesetz" ist
  nicht garantierbar. Bleibt deklarierte offene Grenze.
- **Cross-Model-Drift-Check (grok-build): NACHZUHOLEN** — Grok-CLI am 2026-07-04 weiterhin
  nicht erreichbar (gleicher Outage-Präzedenzfall wie 6.6/6.7). Die Tour-6.8-Claims
  (exp-additiv = kanonische exp·exp-Heimat, Affine-Ridge-Wächter, Vier-Rivalen-Occam-Leiter,
  OOS-Confirm, Regime-Weite-Ehrlichkeit, (B)-Ablehnung mit drei Gründen) sind für den
  nachgeholten Review als Claims-Summary in diesem Absatz fixiert.

## GESAMTSTAND — alle 5 Phasen + alle Features `[GEBAUT]` + Frontier 6.1–6.8

Der gesamte Mehr-Wochen-Plan aus `GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md` ist gebaut, getestet,
grok-build-drift-geprüft (6.6 + 6.7 + 6.8: nachzuholen, s. o.) und committet (lokal, kein Push).
**181 Discovery-Testfunktionen** über 38 Module (nachgezählt 2026-07-04 nach 6.8,
`grep -c '^def test_' tests/test_discovery_*.py`);
`rediscovery_benchmark()` 100 %/100 % (6 Fälle); ZERO Trading-Terme. Mit Frontier 6.1–6.8 sind nun
**Summen mehrerer dimensional-gültiger Terme** (inkl. OOS), **transzendente Formen**, die **Active
Resolution of Uncertainty**, **Minimal-Correction bei Komposition** (Residuen-SR auf gequellte
Gesetze, signed lstsq + strenges Gate `residual_explained≥0.9` ∧ `ΔR²>1e-3` ∧ Leave-One-Out),
**multiplikative Kopplungen** (Produktformen `C·π1^a·f(α·π2)` + Ratio-Korrektur `y ≈ y_base·m(π)`
unter denselben Gates), **blinde Zwei-Transzendenten-Produkte** (`C·f(α·π1)·g(β·π2)` ohne
Baseline, Identifizierbarkeits-Wächter + Occam-Leiter + OOS-Confirm) UND **additive π-Argumente
in einer Transzendenten** (`C·f(α·π1+β·π2)+D`, kanonische exp·exp-Heimat, Vier-Rivalen-Leiter +
OOS-Confirm) abgedeckt.
Volle Offline-Suite **2059 passed / 0 failed / 43 skipped** (gemessen 2026-07-04, nach 6.8).
Ehrliche verbleibende Grenze: Kompositionen von Transzendenten ineinander (`f(g(·))` — in Tour
6.8 analysiert und mit drei konkreten Gründen ABGELEHNT statt unehrlich gebaut, s. o.) und die
volle GP-Suche über offene Formräume.

## Drift-Kontroll-Protokoll (jede Tour)

1. Bauen (TDD, an bestehende Gates angedockt).
2. Narrow-Tests → volle Suite grün.
3. `bash scripts/grok_review.sh` (Model `grok-build`) auf eine Claims-Summary des neuen Moduls;
   Grok-Befunde selbst nachkontrollieren (Grok = Vorschlag, nie Wahrheit).
4. Commit lokal + BUILD_LOG-Eintrag.
5. Am Phasenende: README + Docs + Memory aktualisieren.
