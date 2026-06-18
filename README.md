# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

**Ein Mensch liefert eine Idee. GENESIS recherchiert, verifiziert, berechnet und liefert eine umsetzbare, belegte Spezifikation — ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können: mit Quellen statt Behauptungen, mit nachgerechneter Physik statt geratener Zahlen, und mit ehrlichen Lücken statt erfundener Antworten.

```
1329 Tests offline bewiesen · deterministisch · läuft komplett lokal · kein Cloud-Zwang
```

---

## Inhalt

1. [Das Problem & die Antwort](#1--das-problem--die-antwort)
2. [Die Garantie](#2--die-garantie)
3. [Architektur: die Phasen α → β → γ → δ](#3--architektur-die-phasen-α--β--γ--δ)
4. [Die Gates](#4--die-gates)
5. [Die Physik-Engine (Phase δ)](#5--die-physik-engine-phase-δ)
6. [Die Quality-Engine](#6--die-quality-engine)
7. [Installation](#7--installation)
8. [Nutzung: CLI](#8--nutzung-cli)
9. [Nutzung: Web-UI](#9--nutzung-web-ui)
10. [Nutzung: Python-API](#10--nutzung-python-api)
11. [Live-Modus (lokale LLMs)](#11--live-modus-lokale-llms)
12. [Messung & Gold-Set](#12--messung--gold-set)
13. [Verifikations-Philosophie](#13--verifikations-philosophie)
14. [Projektstruktur](#14--projektstruktur)
15. [Status & ehrliche Grenzen](#15--status--ehrliche-grenzen)
16. [Dokumentation](#16--dokumentation)

---

## 1 · Das Problem & die Antwort

Sprachmodelle erfinden. Sie liefern überzeugende Preise, die kein Shop führt, Normen, die nicht existieren, und Festigkeitswerte, die niemand gemessen hat. Für Recherche ist das ärgerlich — für eine **Bauanleitung**, die jemand wirklich umsetzt, ist es gefährlich.

GENESIS dreht das Verhältnis um: **das Modell darf nur Struktur vorschlagen — niemals Fakten erschaffen.** Jeder faktische Wert muss wörtlich in einer verifizierten, unabhängig korroborierten Quelle stehen. Jede Rechnung führt Code aus, und ein unabhängiges Gate rechnet sie nach. Jede Designentscheidung ist als Entscheidung deklariert und vom Menschen ratifizierbar. Und wo nichts belegbar ist, sagt GENESIS das — **„Ich weiß es nicht" ist ein gültiger, erwünschter Output.**

Das ist keine Prompt-Bitte, sondern Struktur: ein `Claim` ohne Quelle kann im Datenmodell **nicht existieren** (erzwungen im Konstruktor, im Ledger und als Datenbank-Trigger — drei Schichten).

## 2 · Die Garantie

| Prinzip | Bedeutung | Durchsetzung |
|---|---|---|
| **Kein Fakt ohne Quelle** | Jede Behauptung lebt im Fakten-Ledger mit Quelle, Konfidenz, Status | Konstruktor + Ledger + DB-Trigger |
| **Wertzwang im Wortlaut** | Eine Zahl in der Spezifikation steht *wörtlich* in einem verifizierten Beleg | GATE γ C-4 |
| **Code rechnet, Gate rechnet nach** | Das LLM macht nie Mathematik; abgeleitete Werte berechnet Code, das Gate rechnet sie unabhängig nach | GATE γ C-6 |
| **Dimensionale Homogenität** | kg + mm oder eine als Länge deklarierte Fläche werden abgefangen (Einheiten als abelsche Gruppe) | GATE γ C-15 |
| **Cross-Claim-Konsistenz** | Zwei Größen mit demselben deklarierten `measurand` dürfen sich nicht widersprechen | GATE γ C-17 |
| **Unsicherheits-Propagation** | Messunsicherheiten propagieren nach GUM (JCGM 100) — und das Gate rechnet auch das nach | GATE γ C-18 |
| **Keine versteckte Entscheidung** | Jede Wahl trägt eine Begründung und erscheint auf dem ratifizierbaren Entscheidungsblatt | Konstruktor + GATE γ |
| **Cross-Model-Verifikation** | Der Verifizierer (skeptic) ist ein *anderes* Modell als der Generator; Selbst-Bestätigung zählt nicht | erzwungen vor jedem Call |
| **Ehrliche Abstention** | Was nicht belegbar ist, wird Lücke — nie ein teilweiser oder gedrifteter Plan | alle Gates + Agenten |
| **Determinismus** | Jeder Lauf hat eine `run_id`, ist gecheckpointet und exakt reproduzierbar | Runner + Config-Hash |

## 3 · Architektur: die Phasen α → β → γ → δ

```
Idee/Frage
   │
   ▼
 α  RECHERCHE      scout → scholar → skeptic → conductor
   │               Quellen finden → atomare Claims (Zitat wörtlich geprüft)
   │               → cross-model verifizieren → Report (jeder Satz ↦ Claim)
   ▼
 β  LÖSUNGSRAUM    synthesizer: real existierende Ansätze, jeder in
   │               verifizierten Claims verankert — nichts erfunden
   ▼
 γ  SPEZIFIKATION  architect: Größen (mit deklarierter Herkunft), parametrische
   │               3D-Geometrie (CSG), Stückliste, Schritte mit Prüfkriterium,
   │               numerisch geprüfte Constraints, Entscheidungsblatt
   ▼
 δ  VALIDIERUNG    deterministische, LLM-freie Physik- und Geometrie-Prüfung
   │               (Engine: siehe unten) + Quality-Verdikt + Ratifikation
   ▼
 belegte, geprüfte, ratifizierbare Spezifikation  (+ CAD-Export: OpenSCAD,
 build123d, STL — und ein vollständiges Markdown-Bauhandbuch)
```

Jeder Agent erfüllt ein framework-freies Protocol (`core/interfaces.py`); Framework-Spezifisches lebt hinter Adaptern. Der Zustand ist typisiert (`core/state.py`), der Ledger erzwingt Provenance, Checkpoints machen Läufe reproduzierbar.

> **Über α–δ hinaus:** Der **HORIZON-Bogen (φ → Ω)** erweitert die Kette um den *Funken* davor (φ/χ) und das *Bindegewebe* danach (δ⁺/γ⁺/ε/ζ/Ω), plus eine generelle Frontier-/Pipeline-/Simulations-Schicht für *jede* Idee — gebaut, je hinter einem eigenen Gate, getestet. Ehrliche Einordnung von Reife und offenen Punkten in [§15](#15--status--ehrliche-grenzen); der volle Bogen in `docs/HORIZON.md`.

## 4 · Die Gates

Eine Phase endet erst, wenn ihr Gate besteht. Gates sind **reine, deterministische Funktionen** — kein Modell-Urteil:

| Gate | Prüft | Beispiele harter Fehler |
|---|---|---|
| **α** | Report-Soundness | unbelegter Satz, widerlegter Claim als Fakt, tote Zitation |
| **β** | Lösungsraum | unverankerter Ansatz |
| **γ** (C-1…C-18) | Spezifikation | Wert nicht im Beleg-Wortlaut, gebrochene Ableitung, Dimensionsfehler, Cross-Claim-Widerspruch, falsche Unsicherheit |
| **δ** | Geometrie | tote Bool-Operation, leerer Schnitt, degenerierte Geometrie (AABB — beweisbar, keine False Positives) |
| **δ-Physik** | Engineering | `PHYSICS_CHECK_FAILED` (Marge nicht erfüllt), `PHYSICS_CHECK_ERROR` (unrechenbare Eingabe), `PHYSICS_UNKNOWN_VALIDATOR` — **nie ein stiller Pass** |
| **ERC** | Elektrik | schwebende Netze, zwei Treiber auf einem Netz, ungetriebene Last |
| **CODE** | Software | das Deliverable wird in einem isolierten Subprozess **ausgeführt**; rote Checks = FAIL |
| **PROTOCOL** | Energie/Mechanik | Messung ohne Kontrollgruppe oder mit zu wenigen Replikaten |

## 5 · Die Physik-Engine (Phase δ)

Eine deterministische, LLM-freie Engineering-Validierungs-Engine (`docs/phases/PHASE_DELTA.md`, §1–§57). **Jeder Validator ist gegen geschlossene Formen verifiziert** — exakt, wo es beweisbar ist (Maschinengenauigkeit), sonst als ehrliche Konvergenz oder konservative Schranke mit deklarierter Grenze.

**27 Validatoren hinter dem δ-Physik-Gate** (13 Physik + 7 Druckbarkeit + 4 Flug + 3 Krypto):

| Versagensmodus | Validator | Verifiziert gegen |
|---|---|---|
| Torsion (Welle) | `torsion` | τ=16T/πd³ ≡ T·r/J (Identität, exakt) |
| Knicken (Stabilität) | `buckling` | Euler π²EI/(KL)², 4 Lagerungen < 0,1 % |
| Ermüdung (zyklisch) | `fatigue` | Goodman/Soderberg/Gerber-Endpunkte, Basquin, Miner |
| Kerb-Ermüdung | `notch_fatigue` | Peterson q=1/(1+a/r), K_f-Grenzfälle |
| Bruchmechanik | `fracture` | Irwin K=Yσ√(πa), Paris-Integral vs. Numerik 3·10⁻¹¹ |
| Hertz-Kontakt | `contact` | p₀=1,5·p_mean exakt, Grenzfall Kugel-auf-Ebene |
| Druckbehälter | `pressure_vessel` | dünnwandig + Lamé (Randbedingungen exakt) |
| Kriechen (heiß) | `creep` | Larson-Miller-Inverse exakt, Norton (σ₂/σ₁)ⁿ |
| Übertemperatur | `overtemperature` | Fourier Q=kAΔT/L maschinengenau |
| Thermospannung | `thermal_mismatch` | −EαΔT exakt, Timoshenko-Bimetall |
| Resonanz | `resonance` | Eigenfrequenz-Abstand (Modalanalyse-gestützt) |
| Plattenbiegung | `plate_bending` | Kirchhoff-Kreisplatte (Timoshenko/Roark) |
| Schraubenvorspannung | `bolted_joint` | Shigley/VDI 2230, Separationslast exakt |
| Brücke zu lang (FDM) | `bridge_span` | 10-mm-Regel (Hydra/Xometry/FacFox) |
| Passung klemmt (FDM) | `fdm_fit_clearance` | Prozess-Floor 0,2/0,1 mm |
| Pin zu dünn (FDM) | `pin_diameter` | ≥ 3 mm, Fillet-Empfehlung < 5 mm |
| Gewinde zu klein (FDM) | `thread_size` | ≥ M5, sonst Insert/Tap |
| Freie Wand zu dünn (FDM) | `unsupported_wall` | ≥ 1,0 mm (strenger als 0,8-Regel) |
| Prägung zu fein (FDM) | `emboss_detail` | 0,9 mm Emboss / 0,5 mm Engrave |
| Quer-Schicht-Last (FDM) | `layer_adhesion` | > 55 % Z-Festigkeitsverlust → 0,45 × Nennwert |
| Hebt nicht ab (Drohne) | `rotor_hover` | Impulstheorie (Leishman), T·v_i ≡ T^1.5/√(2ρA) Identität, T/W ≥ 2 |
| Flugzeit zu kurz | `battery_endurance` | Energiebudget, 80-%-LiPo-Regel, 24-min-Anker exakt |
| ESC/Akku-Brownout | `current_budget` | I = P/V vs. ESC-Limit UND C·Ah (kleinere Marge) |
| Lageregelung wackelt | `attitude_pd` | ζ = Kd/(2√(Kp·I)), Ogata-Band 0,4–0,8, ζ=0,7 exakt |
| Nonce-Kollision (Krypto) | `birthday_bound` | Geburtstagsschranke p ≈ q²/2^(n+1), NIST-Budget 2⁻³² (SP 800-38D) |
| Schlüssel zu schwach | `key_security` | NIST SP 800-57 Teil 1, Tab. 2 — sym/ECC/RSA-Äquivalenz exakt gepinnt |
| GCM-Budget gesprengt | `gcm_invocation_budget` | SP 800-38D: ≤ 2³² Invocations pro Schlüssel bei Zufalls-IV |

**Druckbarkeit — die Fehler, die erst auf dem Druckbett sichtbar werden** (Research-Write-up: `docs/research/PRINT_DESIGN_FAILURES.md`): zusätzlich zu den 7 Quantity-Validatoren prüft `orientation.bridge_spans` Brücken geometrisch über das echte BREP (verankert-vs-frei klassifizierte Deckenränder; Taschendecke brückt über die kurze Seite, Cantilever bleibt unbridgebar), `orientation.first_layer_report` fängt Erste-Lage-Versagen (keine Bett-Kontaktfläche, Elephant-Foot-Risiko + 0,3-mm-Fasen-Empfehlung; Warping bekommt Evidenz statt erfundenem Schwellwert), und `mesh_integrity.stl_integrity_check` beweist die Slicebarkeit des exportierten STL exakt (wasserdicht + konsistent gewickelt über gerichtete Kanten, Euler–Poincaré χ = 2−2g — der Capstone-Halter kommt als Genus 1 heraus, das Loch topologisch bewiesen —, Divergenzsatz-Volumen > 0 gegen inside-out-Meshes). Alles in den Lauf-Pfad verdrahtet: `pipeline.assess_printability` liefert ein ehrliches Gesamt-Verdikt (Kernel fehlt / keine Geometrie = explizites Nicht-Urteil, nie ein stiller Pass), erreichbar als CLI `--mode print` und als Web-UI-Tab „Druckbarkeit"; der STL-Export emittiert das Mesh erst nach bestandenem Integritäts-Beweis.

**Dahinter rechnet echte FEM** (reines numpy, optional gmsh/cadquery): 3-D-Kontinuum mit linearen **und quadratischen** Tetraedern (T10 trifft die Biegefrequenz auf 0,2 %), berechnete Loch-Spannungskonzentration (trifft Howlands Kt≈3,14), Thermik stationär **und transient**, Modalanalyse (exakt 6 Starrkörpermoden), Monte-Carlo-Unsicherheit (JCGM 101), SPICE-artige Schaltungsanalyse (DC/AC/nichtlinear/transient), exakte BREP-Geometrie (OpenCASCADE) und orientierungsabhängiges FDM-DFM.

**Auto-Select:** Die Spezifikation wählt ihre Checks selbst. Größen tragen deklarierte `measurand`-Tags (`shaft.torque`, `material.shear_strength`, …); ein Rezept-Katalog löst daraus die passenden Checks auf — **einheiten-korrekt konvertiert** (150 N·m → 150000 N·mm), und eine indizierte-aber-unrechenbare Prüfung wird **Lücke**, nie still verworfen und nie mit falscher Einheit gefüttert.

## 6 · Die Quality-Engine

Um die Gates herum sitzt eine verdrahtete Produktions-Schicht — komponiert zu **einem ehrlichen Gesamt-Verdikt** (`pipeline.assess_specification`), das eine Lücke nie als Pass maskiert:

| Baustein | Was es tut |
|---|---|
| **Eval-Harness** (`evaluation.py`) | Die Garantie als gemessene Zahl: kuratierte solide + manipulierte Fälle über **beide** Gates; die nicht verhandelbare Metrik ist **Leaks = 0** |
| **Verify→Refine-Loop** (`refinement.py`) | Gate-Fehler → gezielte Korrektur-Direktiven → begrenzte Re-Generierung (max. 5 Runden); meldet ehrlich `stuck`/`exhausted` — **nie Fake-Erfolg** |
| **Proaktive Klärung** (`clarification.py`) | Erkennt Unterspezifikation und stellt die wertvollsten Rückfragen zuerst (EVPI-priorisiert); Antworten werden deklarierte Entscheidungen; fragt nie nach nicht vorhandener Physik |
| **Ratifikation** (`ratification.py`) | Die KI schlägt vor, der Mensch entscheidet: jede Entscheidung, jede Lücke und jedes gescheiterte Gate blockiert „fertig", bis sie explizit abgezeichnet ist — **kein Auto-Approval** |
| **Kalibrierung** (`calibration.py`) | Akzeptanz-Schwellen per Messung (Precision@Threshold), ECE, Konsistenz-Konfidenz, Conformal-Quantile (Split-Conformal, verteilungsfreie Coverage-Garantie ≥ 1−α) — und ehrliches `None`, wenn die Daten die Schwelle nicht hergeben |
| **Telemetrie** (`telemetry.py`) | OTel-förmiger Prozess-Trace (Gates, Verdikte, Runden, Zeiten) — auditierbar, deterministisch testbar |
| **Geometrie-Verifikation** (`geometry_verification.py`) | Der gebaute CAD-Körper wird gegen die analytisch implizierte Geometrie kreuzgeprüft (Volumen + Maße exakt) |
| **Constraint-Konsistenz** (`constraint_consistency.py`) | Findet strukturell widersprüchliche Anforderungen (a≥b ∧ a<b) **wertunabhängig**, ohne Solver |
| **Grounding-Integrität** (`grounding_integrity.py`) | Verifikations-Quellen müssen von Original-Quellen **disjunkt** sein (keine zirkuläre Selbst-Bestätigung); jeder Report-Satz ↦ realer, nicht-widerlegter Claim |

Das Gesamt-Verdikt unterscheidet ehrlich: `physics_verified` · `needs_clarification` · `physics_incomplete` (Lücke ≠ Pass) · `physics_failed` · `no_physics_indicated` (nichts geprüft ≠ Freifahrtschein) · `inconsistent_constraints`.

## 6½ · Universe Explorer (`discovery/`) — ehrliche Formel-Entdeckung

Der **Erkundungs-Arm**: ein Mensch (oder ein Vorschlags-Modell) gibt eine Idee + Daten ein, und die Engine **entdeckt die zugrunde liegende Formel** — nicht durch LLM-Raterei, sondern durch die Dimensions-Algebra. Der Buckingham-π-Trick (das AI-Feynman-Prinzip) fixiert die Exponenten allein aus den Einheiten; der Fit findet nur noch den dimensionslosen Koeffizienten. Jeder Kandidat läuft durch dieselben Gates wie alles in GENESIS und endet mit einem ehrlichen Verdikt: **bestätigt / widerlegt / unentschieden** — nie einer erfundenen Entdeckung.

| Baustein | Was es tut | Status |
|---|---|---|
| **Engine** (`discovery/engine.py`) | Dimensionale symbolische Regression + `discover_new_formulas`-Loop; pro Kandidat Dimensions-Gate, Nachrechnung (C-6), Fit-Gate (von der δ-Asymmetrie verschärft), Unsicherheit | `[GEBAUT]` |
| **Discovery Graph** (`discovery/graph.py`) | Versioniertes Langzeitgedächtnis (Anhang-C-Schema), per Dimensions-Fingerprint dedupliziert → verhindert doppelte Neu-Entdeckung | `[GEBAUT]` |
| **Tournament** (`discovery/tournament.py`) | Populations-Evolution im Null-Raum der Dimensions-Constraints; schlägt Single-Shot bei freien π-Gruppen messbar | `[GEBAUT]` |
| **Benchmark + Red-Team** (`discovery/benchmark.py`) | Rediscovery bekannter Gesetze aus Daten; falsche Ideen werden verworfen | `[GEBAUT]` |
| **Mehr-Term** (`discovery/multiterm.py`) | Additive Gesetze `y = Σ Cᵢ·termᵢ (+ Intercept)`; jeder Term dimensional gültig (`A·p=b`), Parsimonie + Pruning gegen Overfit | `[GEBAUT]` |
| **Transzendent** (`discovery/transcendental.py`) | `y = C·f(α·π) + D`, `f ∈ {exp,log,sin,tanh}` über dimensionslose π-Gruppe (Nullraum `A·p=0`); Gate verlangt, dass die Transzendente die Power-Law derselben Gruppe schlägt | `[GEBAUT]` |
| **Active Resolution** (`discovery/active_resolution.py`) | Der aktive Zug nach `unentschieden`: berechnet die **diskriminierende Messung**, die zwei gleich-gut-passende Rivalen trennt (begrenzte Divergenz-Region, Spread-Punkte, ehrliches „keine Unterscheidungskraft"-Gate) → passiver Verifizierer wird aktives Instrument | `[GEBAUT]` |
| **Komposition** (`discovery/composition.py`) | „Gilt die naive Superposition — und wenn nicht, was ist die kleinste Korrektur?": dimensionale SR auf das **signierte** Residuum `y − y_base`; Gate `residual_explained≥0.9` ∧ `ΔR²>1e-3` ∧ Leave-One-Out → keine Korrektur aus Rauschen | `[GEBAUT]` |

**Gemessener Beweis:** `rediscovery_benchmark()` = **100 % Rediscovery, 100 % Red-Team-Catch**. Kepler kommt als `T = 6.28319 · a^(3/2) · μ^(-1/2)` heraus (C/2π = 1.0, R² = 1.0); ideales Gasgesetz und Newton-Gravitation ebenso; dimensional unmögliche und „verlockend-aber-falsche" Ideen werden korrekt nicht bestätigt.

```python
from gen.discovery import Variable, Constant, DiscoveryProblem, discover
# Kepler aus Daten: T (Umlaufzeit) aus a (Bahnradius) + mu = G*M
result, graph = discover(DiscoveryProblem(
    idea="Wie haengt die Umlaufzeit von der Bahngroesse ab?",
    target=Variable("T", "s", umlaufzeiten),
    inputs=(Variable("a", "m", bahnradien),),
    constants=(Constant("mu", 1.327e20, "m^3/s^2"),)))
print(result.validated[0].candidate.expression)  # T = 6.28319 * a^3/2 * mu^-1/2
```

**Komplett gebaut (Phase 2–5, der ganze Mehr-Wochen-Plan):** Deep-Controller (`controller.py` — Budget/Tiefe-Stufen/Checkpoint-Resume), Physics-Surrogat-Vorfilter (`surrogate.py` — rankt/prunt, bestätigt nie), **Grok-Symbiose** (`symbiosis.py` — `grok-build` schlägt Hypothesen vor, GENESIS gated jede; live bewiesen), **Reality-Fork-Simulator** (`reality_fork.py` — counterfactual Welten via Gauss-Gesetz in D Dimensionen), **Cosmic Insight** (`cosmic_insight.py` — Cross-Domain-Analogien, Newton ~ Coulomb), **Assumption Annihilator** (`assumption_annihilator.py` — Konstante→Variable, höchstes δ), **First-Principles-Modus** (`first_principles.py` — Beweis-Bäume, jeder Schritt gate-belegt), **Out-of-Sample-Validierung** (`validation.py` — gegen p-hacking), **Universe Simulator Bridge** (`universe_bridge.py` — simulate → discover → gate, externe HPC-Engines als deklarierte Naht). Plus **Frontier 6.1 — Mehr-Term-Entdeckung** (`multiterm.py`): additive Gesetze `y = Σ Cᵢ·termᵢ (+ Intercept)`, jeder Term dimensional gültig (`A·p=b`), Parsimonie via greedy forward selection + Pruning gegen Overfit, **plus ehrliche Out-of-Sample-Validierung** (`multiterm_out_of_sample_validate` — fittet auf Train, scort unverändert auf Held-out; fängt Overfit UND Over-Pruning). Live: Kinematik `s = ½·a·t² + v0·t` → exakt 2 Terme (R²=1), Held-out R²=1.0; Rauschen → Held-out R²=−0.73 (`generalises=False`); Kepler bleibt 1 Term (kein Padding). Und **Frontier 6.3 — transzendente Formen** (`transcendental.py`): `y = C·f(α·π)+D` mit `f ∈ {exp,log,sin,tanh}` über eine dimensionslose π-Gruppe (Nullraum `A·p=0`, nichtlinearer `scipy`-Fit); das Gate verlangt, dass die Transzendente die Power-Law derselben π-Familie schlägt. Live: Exp-Zerfall `x=10·exp(−t/τ)` → `bestaetigt`, Schwingung `3·sin(2·t/τ)+5` → `bestaetigt`, ein Quadrat `(t/τ)²` → `unentschieden` (kein Über-Claim), Kepler → `widerlegt` (kein dimensionsloses Argument). Und **Frontier 6.4 — Active Resolution of Uncertainty** (`active_resolution.py`, mit grok-build erarbeitet): der aktive Zug nach `unentschieden`. `propose_resolution` berechnet deterministisch + LLM-frei die diskriminierende Messung, die zwei gleich-gut-passende Rivalen trennt (begrenzte Divergenz-Region `f≤3`, Spread-Punkte gegen den Shape, ehrliches `discriminating=False` statt Extrapolations-Artefakt). Akzeptanztest = **Flip**: Schmalband-`unentschieden` → augmentieren am Spec → `bestaetigt`. Und **Frontier 6.5 — Minimal-Correction bei Komposition** (`composition.py`): „gilt die naive Superposition gequellter Gesetze?". `discover_correction(problem, baseline)` fährt dimensionale SR auf das **signierte** Residuum `y − y_base` (Vorzeichen in den lstsq-Koeffizienten, Term dimensional konsistent) — `korrektur_noetig` nur wenn `residual_explained≥0.9` ∧ `ΔR²>1e-3` ∧ **Leave-One-Out** überlebt. Live: Kopplung `y = x + ½·k·x²` (baseline `x`) → findet exakt `0.5·x²·k` (R²=1); Rauschen → `vollstaendig` (keine erfundene Korrektur). 100 Discovery-Tests grün; jede Tour grok-build-drift-geprüft.

**Ehrliche Grenze (Forschungs-Frontier, keine offene Bauphase mehr):** Die Engine deckt die **Power-Law/π-Gruppen-Familie** (Kepler, Gas, Newton, Coulomb, Pendel), **additive Summen mehrerer dimensional-gültiger Terme** (Frontier 6.1/6.2, mit Out-of-Sample-Validierung) **und transzendente Formen einer dimensionslosen Gruppe** (Frontier 6.3). Produkte/Kompositionen von Transzendenten und eine volle GP/symbolische Suche jenseits dieser Familie bleiben die nächste echte Forschungsgrenze (`docs/discovery/STATUS.md`).

## 7 · Installation

Voraussetzung: **Python ≥ 3.11**. Alles läuft lokal; nichts verlässt deinen Rechner.

```bash
git clone <repo> && cd genesis
pip install -e .            # Kern (numpy) + Kommandos `genesis` und `genesis-web`
pip install -e .[web]       # + lokale Web-UI (FastAPI/uvicorn)
pip install -e .[cad]       # + exakter CAD-Kernel (cadquery/OCP) und FEM-Mesher (gmsh)
pip install -e .[postgres]  # + persistenter Fakten-Ledger (asyncpg; In-Memory ist Default)
pip install -e .[full]      # alles inkl. Dev-Tools (pytest, ruff, httpx)
```

Ohne die optionalen Pakete bleibt alles funktionsfähig — die betreffenden Features/Tests **skippen ehrlich**, statt zu raten.

```bash
python -m pytest tests/ -q          # 1185 passed, 9 skipped — ohne LLM-Token, ohne Netz
```

## 8 · Nutzung: CLI

Alle folgenden Modi sind **deterministisch und offline** (kein Internet, kein LLM):

```bash
genesis --mode capstone               # komplette Spezifikation durch ALLE Gates (LED-Regalhalter)
genesis --mode capstone --format md   #   … als vollständiges Markdown-Bauhandbuch
genesis --demo                        # α-Demo: verifizierter Fakten-Report
genesis --demo --mode spec            # γ-Demo: Bauanleitung + Quality-Verdikt-Footer
genesis --demo --mode spec --format scad    # Geometrie als OpenSCAD-Quelltext
genesis --demo --mode spec --format b123d   # … als build123d-Python
genesis --demo --mode spec --format stl     # … als druckfertiges STL (Booleans via OCCT-Kernel,
                                            #    emittiert erst nach bestandenem Mesh-Integritäts-Beweis)
genesis --mode assess                 # das ehrliche Quality-Verdikt über die Demo-Specs
genesis --mode print                  # das Druckbarkeits-Verdikt (Mesh + Brücken + erste Lage)
genesis --mode eval                   # die Anti-Halluzinations-Garantie als Metrik (Leaks = 0)
genesis --mode protocol               # Energie-Domäne: reproduzierbares Mechanik-Speicher-Protokoll (keine Biologie)
genesis-web                           # lokale Web-UI auf http://127.0.0.1:8077
```

(Vor `pip install -e .` geht alles auch direkt aus dem Repo: `PYTHONPATH=src python -m gen …` bzw. `python -m gen.web`.)

Live-Modi (Claude/Grok-CLI **oder** lokales Ollama, siehe [§11](#11--live-modus-lokale-llms)):

```bash
genesis "Wie funktioniert ein Wälzlager?"          # Live-α: Frage → belegter Report
genesis --mode solution "Drehmoment begrenzen"     # Live-β: Problem → verankerter Lösungsraum
genesis --mode spec "Wandhalter für 5-kg-Kamera"   # Live-γ: Idee → belegte Spezifikation
```

## 9 · Nutzung: Web-UI

```bash
genesis-web        # → http://127.0.0.1:8077  (bindet nur an localhost)
```

Die Oberfläche ist für **Laien** gebaut und macht die Ehrlichkeit sichtbar statt sie zu glätten:

| Tab | Inhalt |
|---|---|
| **Übersicht** | Was GENESIS garantiert, Farb-Legende, Live-Status |
| **α · Fakten-Report** | Jeder Satz klickbar → Beleg-Zitat + Quellen-Links |
| **γ · Bauanleitung** | Größen mit Herkunfts-Badges (belegt · berechnet · Entscheidung), Stückliste, Schritte mit Prüfkriterium, Lücken prominent in Gelb |
| **Capstone** | Die komplette Spezifikation mit allen Gate-Badges |
| **Physik-Verdikt** | Auto-gewählte Checks mit gerechneten Sicherheitsfaktoren; „keine Physik deklariert" erscheint grau als *nichts geprüft* — nie als Pass |
| **Klärungs-Dialog** | GENESIS fragt, du antwortest, das Verdikt wird neu berechnet — der Gelb→Grün-Flow live |
| **Garantie-Metrik** | Das Eval-Harness mit **Leaks = 0** als Haupt-KPI |
| **Sign-off** | Ratifikation als Checkliste: nichts gilt ohne deine expliziten Häkchen |
| **Eigene Frage** | Der Live-Pfad — solange das Owner-Gate zu ist, antwortet GENESIS mit einer ehrlichen Ablehnung statt einer erfundenen Antwort |

Farbcode: **grün** = unabhängig verifiziert / Marge erfüllt · **gelb** = ehrliche Lücke / offene Entscheidung · **rot** = Prüfung gescheitert · **grau** = nicht geprüft.

## 10 · Nutzung: Python-API

```python
import gen

# Live-Pipelines (Ollama nötig): α / β / γ
report = await gen.run("Frage …", deps, config=cfg)
spec   = await gen.run_specification("Idee …", deps, config=cfg)

# Quality-Verdikt über eine Spezifikation (offline, deterministisch)
from gen.demo import drive_shaft_spec
verdikt = gen.assess_specification(drive_shaft_spec())
print(verdikt.overall)                  # "physics_verified"

# Die Physik-Validatoren auch direkt als verifizierte Rechenbibliothek:
from gen.torsion import shaft_torsion_check
shaft_torsion_check(torque=150000, diameter=25, length=600,
                    shear_modulus_g=80000, shear_strength=260)
# -> {"max_shear": 48.9, "safety_factor": 5.32, "ok": True, ...}

from gen.buckling import buckling_check
from gen.fatigue import goodman_check
from gen.pressure_vessel import pressure_vessel_check
# ... alle 13, jede gegen geschlossene Formen getestet
```

`import gen` lädt bewusst **kein** numpy (PEP-562-Lazy-Export) — wer nur die α/β/γ-Pipelines nutzt, bleibt dependency-leicht.

## 11 · Live-Modus (lokale LLMs)

Der Live-Pfad ist **cross-model per Konstruktion** — Generator und Verifizierer sind verschiedene Modellfamilien — und keylos auf zwei Wegen. Quellen liefern drei Backends: keyloses Wikipedia, Semantic Scholar (akademische Tiefe) und ein **formel-bewusstes Backend** (`gen.tools.formula_backend`), das bei Formel-/Gesetz-/Konstanten-Fragen autoritative Quellen liefert — NIST **CODATA 2022** (`gen.tools.codata`), **DLMF**-Spezialfunktionen (`gen.tools.dlmf`) und Wikidata-Gesetze (`gen.tools.wikidata`), gebündelt über eine inhalts-adressierte `FormulaRegistry`. Jede so gewonnene Konstante/Formel wird zu einem **gequellten `UNVERIFIED`-Claim** (downstream gegated, nie als Fakt gesetzt).

**Default — Abo-OAuth über die CLIs** (kein API-Key, nutzt bestehende Max-Abos): Generator `claude-opus-4-8` über `claude -p`, Verifizierer `grok-composer-2.5-fast` über `grok -p`. Die Adapter shellen die installierten CLIs, die `make_llm`-Factory routet familien-gebunden; beide live PONG-verifiziert. Konfiguriert in `config.py` (`Models.generator`/`.verifier`).

**Alternative — vollständig lokales Ollama** (offline, deterministisch, kein Cloud-Kontakt):

```bash
ollama pull qwen3.5:9b      # Generator (scout/scholar)
ollama pull gemma4:12b      # Verifizierer (skeptic) — MUSS eine andere Modellfamilie sein
```

Die Ollama-Modellwahl (verifiziert 2026-06-12 für 11-GB-GPUs): `qwen3.5:9b` (6,6 GB, 256K Kontext) + `gemma4:12b` (7,6 GB, 256K) — jedes passt **allein** mit Reserve in den VRAM, nie mehr als ein Modell gleichzeitig geladen. Modelle/Backends wechseln: `--generator`/`--verifier` (CLI) bzw. `GENESIS_GENERATOR`/`GENESIS_VERIFIER` (Web-UI).

Gleiche Modellfamilie für Generator und Verifizierer? GENESIS **bricht ab, bevor irgendein Call passiert** — Cross-Model ist Pflicht, nicht Vorschlag. Mit `--checkpoint-dir runs` entsteht pro Lauf ein reproduzierbarer Audit-Checkpoint.

In der Web-UI ist der Live-Pfad zusätzlich **hart gegated**: erst `GENESIS_ALLOW_LIVE=1` öffnet ihn — bis dahin liefert „Eigene Frage" eine ehrliche Ablehnung mit Begründung, niemals eine erfundene Offline-Antwort.

**Status:** α/β sind live gegen echte Modelle bewiesen (inkl. eines Laufs, in dem der Wortlaut-Wächter eine echte Modell-Paraphrase abfing). Der erste gemessene Live-γ-Lauf ist bewusst aufgeschoben, bis die Messlatte definiert ist — siehe nächster Abschnitt.

## 12 · Messung & Gold-Set

„Produktionsreif" ist bei GENESIS **eine Messung, keine Behauptung.** Dafür existieren zwei Ebenen:

**Offline (läuft heute):** `genesis --mode eval` misst die deterministische Diskriminierung beider Gates über kuratierte solide + manipulierte Spezifikationen. Ergebnis: 10/10 korrekt, **Leaks = 0** (kein Halluzinations-Typ rutscht durch), 0 Fehlalarme.

**Live (vorbereitet, owner-gated):** `goldset/v1.json` — 24 kuratierte Fälle in drei Klassen:
- **Fakten** (10): bekannt belegbare Antworten; die erwarteten Tokens müssen erscheinen,
- **Fallen** (7): plausibel klingend, aber nicht verlässlich belegbar — Abstention oder belegte Antwort ist korrekt, eine selbstbewusste unbelegte Zahl ist die Halluzination,
- **Nonsense** (7): nicht existente Entitäten (erfundenes Polymer, erfundene Norm, erfundenes Theorem) — **die einzig richtige Antwort ist Enthaltung.**

Der Scorer (`gen/goldset.py`) berechnet Fakten-Genauigkeit, **Abstention-Recall** und Fallen-Resistenz, führt eine `hallucinations`-Liste, deren Leerheit die nicht verhandelbare Messlatte ist — und **verweigert** die Bewertung unvollständiger Läufe.

## 13 · Verifikations-Philosophie

- **Exakt, wo beweisbar:** uniforme Spannung, Fourier-Leitung, Starrkörpermoden, Lamé-Randbedingungen, Volumen — auf Maschinengenauigkeit gepinnt. Sonst: ehrliche Konvergenz (mit gemessener Rate) oder konservative Schranke, immer mit deklarierter Grenze.
- **Zwei unabhängige Methoden:** FEM gegen geschlossene Form, BREP gegen analytisches Volumen, MNA gegen Ohm — Übereinstimmung als Schutz gegen Fehler in einer von beiden.
- **Tests mit Zähnen:** Jeder Wächter hat Negativtests (der manipulierte Fall **muss** scheitern). Das Eval-Harness aggregiert das zu Leaks = 0.
- **Real-World-Verifikation:** Die Web-UI wurde nicht nur unit-getestet, sondern im echten Browser bedient (Playwright): Klärungs-Dialog Gelb→Grün, Sign-off-Verweigerung, Live-Ablehnungskarte.
- **1185 Tests grün, 9 ehrlich übersprungen** (optionale Deps wie build123d/Postgres/gmsh fehlen → `importorskip`, nie geraten) — alle ohne LLM-Token und ohne Netz. Lint-Baseline: `ruff check .` = sauber.

## 14 · Projektstruktur

```
src/gen/
  core/                state.py (Claim/Quantity/Spec …), interfaces.py, errors.py, …
  agents/              scout, scholar, skeptic, conductor, synthesizer, architect, forge (HORIZON φ)
  ledger/              In-Memory- + Postgres-Fakten-Ledger (Quellenzwang)
  tools/, llm/         ehrliches Fetch/Search, LLM-Boundary (Ollama + ScriptedLLM)
  verification/        gates.py (α/β/γ/δ/ERC/CODE/PROTOCOL), derivation, units,
                       geometry (AABB), cross_model
  export/              OpenSCAD · build123d · STL · Markdown-Bauhandbuch
  fem.py fem3d.py fem3d_quadratic.py plate_hole.py bracket_fem.py
                       FEM: Balken, 3-D-Tets (linear/quadratisch), Loch-Kt, Halter
  torsion.py buckling.py fatigue.py notch_fatigue.py fracture.py contact.py
  pressure_vessel.py creep.py plate_bending.py bolted_joint.py thermal.py
  thermal_stress.py modal.py printability.py flight.py security.py
                       die 27 Validatoren (+ Modal-/Thermik-FEM dahinter)
  mesh_integrity.py    STL-Slicebarkeits-Beweis (wasserdicht, Euler, Orientierung)
  physics_validation.py   GATE δ-Physik (Registry, nie ein stiller Pass)
  physics_selection.py    Auto-Select: measurand-Tags → Checks + Lücken
  pipeline.py             das eine ehrliche Gesamt-Verdikt
  evaluation.py refinement.py clarification.py ratification.py calibration.py
  telemetry.py geometry_verification.py constraint_consistency.py
  grounding_integrity.py goldset.py
                       die Quality-Engine
  dfm.py orientation.py tolerance.py uncertainty.py montecarlo.py circuit.py
  brep.py software.py costing.py completeness.py
                       weitere δ/ε-Schichten (DFM, Toleranz, GUM/MC, SPICE, BREP, CODE)
  web/                 lokale Web-UI (FastAPI + statisches Frontend)
  config.py runner.py cli.py demo.py
goldset/v1.json        das kuratierte Mess-Set für die Live-Läufe
sql/001_ledger.sql     Quellenzwang als DB-Constraint
docs/                  VISION, ARCHITECTURE, DATA_MODEL, PIPELINE, phases/ (α–δ inkl.
                       PHASE_DELTA.md §1–§57), research/, agents/
tests/                 1185 Tests inkl. Gate-Akzeptanz, Physik-Engine, Quality-Engine,
                       Web-API & 4 Frageklassen
```

## 15 · Status & ehrliche Grenzen

**Fertig und bewiesen (offline):** die komplette α/β/γ/δ-Kette mit allen Gates, die Physik-Engine (27 Validatoren + FEM, inkl. Rotation im CSG-Vokabular, der Flug-Achsen und der NIST-verankerten Krypto-Achse), die Druckbarkeits-Schicht (bis in CLI, Web-UI und den gegateten STL-Export verdrahtet), die Quality-Engine (inkl. Conformal-Prediction-Schwellen mit verteilungsfreier Garantie), deutsche Ergebnisse auf jeder menschenlesbaren Oberfläche (Claims, Bauanleitung, Spezifikations-Texte, CLI-Renderer, Klärungsfragen, Warnungen, Druck-Verdikt und die komplette Demo-Welt — Zitate bleiben wortlautgetreu in der Quellsprache), CLI, Web-UI (Idee→Ergebnis-Flow für Laien), Packaging, Gold-Set-Vertrag — 1185 Tests, deterministisch, reproduzierbar.

**HORIZON (φ → Ω) — über die fertige Idee hinaus, je gegated + getestet:** Die α–δ-Kette härtet eine *fertige* Idee; HORIZON ergänzt den Anfang und das Ende im Leben einer Idee (`docs/HORIZON.md`). Jede Phase trägt ein eigenes deterministisches Gate:
- **φ · Der Funke** (`agents/forge.py` + `gate_phi`): geerdete Divergenz — ein roher `Spark` wird in verankerte `Possibility`-Objekte geöffnet, jede an einen VERIFIED-Claim/realen Mechanismus gekoppelt; eine erfundene Möglichkeit verlässt das Gate nicht, und der Raum wird immer als „geerdete Stichprobe, nicht der ganze Raum" deklariert (der konzeptionell härteste Knoten — Divergenz hat kein natürliches Gate, also ist *Verankerung* das Gate).
- **χ · Die Frontkarte** (`gate_chi`): belegte Karte des Bekannten + ehrliche Kante des Unbekannten.
- **δ⁺ · Realitäts-Beweis** (`reality.py`, `gate_delta_plus`): GENESIS entwirft das Falsifikations-Experiment und liest die *echte Messung* — ein Claim geht von „berechnet" auf „empirisch korroboriert" oder ehrlich „widerlegt" (mit Dimensions-Wächter gegen die Mars-Climate-Orbiter-Klasse).
- **δ⁺ · Deckungs-Beweis** (`coverage.py`, `gate_delta_plus_coverage`): welche Versagensmodi geprüft wurden und welche indizierten Modi *unprüfbar* bleiben — als Zertifikat, nie als stiller Pass.
- **γ⁺ · Inverses Design** (`inverse_design.py`, `gate_gamma_plus`): Ziel → validierte **Pareto-Front** statt einer Spec (δ-Engine als Fitness-Orakel; nicht-dominiert, Objektive aus den Specs nachgerechnet).
- **ε · Nähte** (`seams.py`, `gate_epsilon`): verifizierte Kopplung zwischen Domänen (elektrisch→thermisch→mechanisch→Firmware→Kosten) als typisierte, deterministisch nachgerechnete Relationen — dort, wo lokal ehrliche Domänen an der Schnittstelle sterben.
- **ζ · Bindegewebe** (`memory_fabric.py`, `gate_zeta`): conformal-gegatetes Audit über dem geteilten Gedächtnis (`VerifiedFactsLibrary`) — was in den Speicher kam, was wiederverwendet wurde.
- **Ω · Exoskelett** (`omega.py`, `gate_omega`): der Vollständigkeits-Vertrag über alle Phasen — jede Phasen-Vollendung hat eine Gate-Quittung, kein „fertig" versteckt eine gescheiterte Quittung; Lücken/Kanten/Entscheidungen werden zu Lernnotizen.

**Die Frontier-Schicht (gebaut + getestet, bewusst research-stage):** GENESIS ist als *generelle* Erfindungsmaschine für jede Idee gedacht (Mechanik, Bio, Software, Energie, Chemie, soziale Systeme …), nicht auf eine Domäne spezialisiert. Über HORIZON hinaus existieren, jeweils vom Test-Lauf abgedeckt: **LUMENCRUCIBLE** (`grenzverschiebung/lumencrucible.py`) — `process_dream(roher_traum)` → erster falsifizierbarer „Hammer" (kleinster Teststand-Schritt) + Omega-Zertifikat + Claim + verifizierbarer Self-Improvement-Append; die **Grenzverschiebungs-Module** (Entwicklungs-Front, Capability-Gap-Analyzer, Experiment-Designer, Teststand-Architekt, Safety-Ladder, Breakthrough-Watch …), die **BreakthroughBridge** (`extensions/`, „das Unmögliche wird möglich"), **11 Fach-Pipelines** (`pipelines/`: Architekt, Ingenieur, Physiker, Techniker, Elektriker, Designer, Fertigung, Software, Regulatorik, Wirtschaft, Integrator), eine **Simulations-Schicht** (`simulation/`: strukturell/modal/buckling/fatigue + Falsifikations-Kopplung zu δ⁺), eine **Elektronik-Schicht** (`electronics.py`: MNA-Schaltungssim + Netlist + Harness + Co-Sim Leistung→Thermik), eine **8-Schritt-Lernmaschine** (`lernmaschine/`) und eine **Wissensbasis** (`wissensbasis/`). Alles deterministisch/offline. **Ehrliche Reife-Grenze:** „gebaut + gegated + getestet" heißt hier *nicht* „produktionsvalidiert" — die reale Validierung (gemessene Live-Läufe, live Wissensbasis-Connectors, externe CAD/EDA-Adapter) ist bewusst aufgeschoben (siehe unten). Was diese Schicht heute schon ehrlich macht statt erfindet, ist über die Gates und die Tests gedeckt; was sie *nicht* kann, steht in `docs/DOC_CODE_DRIFT.md`.

**Live bewiesen:** α (Fakten-Report) und β gegen echte lokale Modelle, inklusive empirischer Bestätigung, dass der Wortlaut-Wächter echte Modell-Paraphrasen abfängt.

**Bewusst offen (owner-gated, wartet auf den gemessenen Erstlauf):**
- der Gold-Set-Lauf gegen Ollama (der Scorer steht bereit),
- die Live-γ-Erstvalidierung (Idee → Spec gegen ein echtes Modell),
- ob ein echtes Modell die `measurand`-Tags zuverlässig deklariert (der Vertrag ist gebaut und scripted bewiesen),
- der Live-Verify→Refine-Loop und Verifizierer-Multi-Sampling,
- **live Wissensbasis-Connectors** (Paper-/Patent-/Lieferanten-Discovery — `wissensbasis/` existiert offline, die Live-Connectors sind aufgeschoben),
- **externe CAD/EDA-Adapter** (FreeCAD/KiCad/PRINTFORGE — intern existieren deterministische Äquivalente: regelbasiertes Place/Route/DRC + build123d-CAD; echte Vendor-Adapter sind bewusste externe Nähte),
- der **vollständige Plattform-Demo-Pfad** (E2E über alle Schichten) und einige Plattform-Kappen (Readiness-/Resource-Ladder, Teacher-Mode, Community-Evidence-Store, Proof-Package-Generator).

**Prinzipielle Grenzen (deklariert, nicht versteckt):** Die Physik-Validatoren sind lineare Ingenieursmodelle mit dokumentierten Annahmen — ein bestandener Check ist *notwendig, nicht hinreichend* für ein sicheres reales Produkt. GENESIS spezifiziert und prüft; bauen, messen und verantworten muss weiterhin ein Mensch — genau dafür existiert der Sign-off.

## 16 · Dokumentation

| Dokument | Inhalt |
|---|---|
| `docs/VISION.md` | Warum es GENESIS gibt; Stand der Technik; Risiken |
| `docs/ARCHITECTURE.md` | Datenfluss, State, Gesamtbild |
| `docs/DATA_MODEL.md` | Ledger + Graph + DB-Schema, exakt |
| `docs/PIPELINE.md` | Die Phasen und ihre Gates |
| `docs/phases/PHASE_ALPHA…DELTA(.RESULT).md` | Max. Detail pro Phase; RESULT-Dateien sind ehrliche, historische Abnahme-Snapshots |
| `docs/phases/PHASE_DELTA.md` (§1–§57) | Jede Validierungs-Schicht: was sie fängt, wogegen sie verifiziert ist, was ihre ehrliche Grenze ist, Quelle |
| `docs/HORIZON.md` | HORIZON (φ–Ω): die Gate-/Builder-Erweiterungsschicht über γ/δ (φ/χ-Gates + `reality`/`seams`/`memory_fabric`/`omega`/`inverse_design`/`coverage`/`proof_kernels`) |
| `docs/research/PRINT_DESIGN_FAILURES.md` | 16 Klassen von 3D-Druck-Designfehlern: gebaut vs. Evidenz vs. ehrliche Lücke, mit Quellen |
| `docs/agents/*.md` | Pro Agent: Verantwortung, I/O, Werkzeuge, Fehlerzustände |
| `CLAUDE.md` / `CONTRIBUTING.md` | Arbeitskonventionen; ein Commit = ein selbstkontrollierter Schritt |

---

*GENESIS behandelt seine eigene Dokumentation nach demselben Prinzip wie seine Outputs: Zahlen sind gemessen, nicht hochgerechnet; Grenzen sind deklariert, nicht versteckt; und was noch nicht bewiesen ist, steht unter „offen" — nicht unter „fertig".*
