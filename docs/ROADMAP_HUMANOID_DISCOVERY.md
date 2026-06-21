# ROADMAP — Humanoid (Ziel A) & Discovery jenseits Power-Law (Ziel B)

> **Grundlage:** direkte Code-Lesung auf Branch `feat/app-integration-phase0-2`
> (HEAD `2094827`, Stand 2026-06-20). Diese Roadmap ist auf die **tatsächlich
> gebauten Module und Seams** gegründet, nicht auf die Vision-Sprache in
> `VISION.md`/`README.md`. Jede Phase nennt das reale Modul, auf dem sie aufsetzt.
>
> **Leitprinzip (GENESIS-eigen, `CLAUDE.md`):** Proposer schlägt vor, ein
> deterministisches **Gate** entscheidet; kein faktischer Output ohne Quelle;
> Verifikation cross-model. Jede „Definition of Done" unten ist ein
> verifizierbares, getestetes, cross-model-geprüftes Gate — kein Vorschlag.

## Legende

- 🔧 **Engineering** — Umfang/Disziplin-Frage, Ergebnis planbar.
- 🔬 **Forschungs-Frontier** — unsicher, evtl. teuer, evtl. prinzipiell nicht „fertig".
- **DoD-Gate** — die harte, getestete Abnahmebedingung im GENESIS-Sinn.
- Aufwand-Skala: Tage · Wochen · Mannmonate (MM) · Mannjahre (MJ).

---

# ZIEL A — Humanoider Roboter Richtung Optimus-Klasse

## IST-Stand (belegt)

GENESIS liefert heute eine **gegatete Erstauslegung**: ~9 druckbare Teile aus
**CSG-Primitiven** (`export/openscad.py`, `export/build123d.py` auf OCCT, Vokabular
nur box/cylinder/sphere + boolean + fillet), BOM + Bauanleitung
(`competitive_humanoid.py`, `export/markdown.py`), und Closed-Form-Gates für
Tragwerk, Kinematik (`kinematics.py`: DH-FK, planare 2R-IK, statische Momente, ZMP),
Aktuation (`actuation.py`: Motor-Hüllkurve, Hydraulik) und Compute (`compute.py`).
Dynamik existiert nur als **validierter Einzel-DOF-RK4-Pendel-Integrator**
(`simulation/multibody.py`) plus **optionaler** PyBullet-fixed-base-Haltedrehmoment-
und URDF-Load-Beweis (`simulation/pybullet_sim.py`, `urdf_bridge.py`). **Nicht
gebaut** (per `out/.../MISSING.md`): Mehrkörper-Kontaktdynamik, gelernter
Ganzkörper-Regler/Gang, mechanische Detail-CAD.

## 🔑 Höchster-Hebel-Erststep

**Den `SimulatorBackend`-Seam (`simulation/backends.py`) von „ein Pendel" auf die
volle Humanoid-URDF erweitern.** Heute mappt der Seam genau eine `PendulumSpec` auf
eine Trajektorie; der MuJoCo-Adapter baut ein Einzelgelenk-MJCF. Erweitere ihn so,
dass er die bereits emittierte `urdf_bridge.humanoid_urdf` in MuJoCo (Apache-2.0)
lädt und **Vorwärts-/Inversdynamik + Massenmatrix der ganzen Kette** liefert — mit
demselben Honest-Skip-Vertrag (`SimulatorUnavailable`). Das ist die Grundlage, auf
der A1–A3 alle aufsetzen, und es nutzt einen **schon existierenden Seam**.

## Phasen

### A0 — Mehrkörper-Dynamik-Backend 🔧
- **Was:** MuJoCo/Pinocchio-Backend hinter `SimulatorBackend`, das die Humanoid-URDF
  lädt und Vorwärtsdynamik, Inversdynamik (RNEA) und Massenmatrix liefert; mit
  Energie-/Impulserhaltungs-Validierung im Stil von `multibody.py`.
- **Baut auf:** `simulation/backends.py`, `urdf_bridge.py`, `simulation/pybullet_sim.py`.
- **Aufwand:** 2–4 Wochen · **Abhängigkeit:** MuJoCo (Apache-2.0, opt-in).
- **DoD-Gate:** Backend reproduziert die Closed-Form-Haltedrehmomente
  (`kinematics.static_joint_torques`) eines mehrgliedrigen Arms maschinengenau **und**
  erhält Energie bei τ=0; getestet; sauberer Skip ohne MuJoCo; cross-model geprüft.

### A1 — Geometrie-Fidelity: `GeometryNode` erweitern 🔧 (großer Umfang)
- **Was:** CSG-Vokabular über box/cyl/sphere hinaus — revolve, sweep-along-path, loft,
  **shell** (Wandstärke), lineare/radiale **Pattern**, Bohrbilder/Gewinde, durchgängig
  fillet/chamfer. Emitter in `export/build123d.py` (OCCT), `export/openscad.py`,
  `export/brep_stl.py`; `mesh_integrity.py`-Gate bleibt Pflicht.
- **Baut auf:** `core/state.GeometryNode`, `export/build123d.py`, `mesh_integrity.py`.
- **Aufwand:** 2–4 MM (jede Operation braucht Emitter in 2–3 Backends + Verifier + Tests).
- **DoD-Gate:** jede neue Operation gegen build123d/OCCT-Referenzvolumen verifiziert,
  watertight-STL bewiesen, deterministisch, cross-model.
- **Wirkung:** der optische Sprung weg von Klötzchen — Teile mit Lagersitzen, Wänden,
  Bohrbildern, Verrundungen. Engineering, aber der umfangreichste Posten.

### A2 — Aktuator-/Struktur-Tiefe + reale Lastfälle 🔧
- **Was:** Aktuator von „PEAK-Hüllkurve" zu Dauer+Thermik (I²R-Kopplung an `thermal.py`)
  und reflektierter Trägheit (J·α aus der A0-Massenmatrix); Getriebe (Harmonic Drive)
  als gegateter Katalog im Muster von `chip_selection.py`; Strukturteile gegen die
  echten Gelenkreaktionen/Sturzstöße aus A0 statt nur statischer Schwerkraft
  (`fem3d.py`, `contact.py` koppeln).
- **Baut auf:** `actuation.py`, `compute.py`, `fem3d.py`, `contact.py`, A0.
- **Aufwand:** 1–2 MM · **Abhängigkeit:** A0.
- **DoD-Gate:** jeder Aktuator/jedes Teil besteht ein Dauer+Spitzen+Thermik-Gate gegen
  die A0-Lastspektren; getestet; cross-model.

### A3 — Ganzkörper-Regelung & Gang 🔬 (Sim2Real-Frontier)
- **Was:** Gang/Balance/Manipulation als gelernter Regler (RL in MuJoCo/Isaac) **oder**
  modellbasiert (MPC/Whole-Body-Control). GENESIS bleibt ehrlich Verifizierer: es liefert
  das verifizierte URDF + Massenmodell (A0) als Plant und gatet Ergebnisse
  (ZMP/Drehmoment-Limits) — **trainiert aber nicht selbst deterministisch**.
- **Baut auf:** A0, `urdf_bridge.py`, `rl_env`-Muster (aus dem Discovery-Arm).
- **Aufwand:** 6–18 MM + GPU + Domänen-Expertise.
- **DoD-Gate:** in-sim stabiler Gang + **Sim2Real-Transfer auf Hardware** — letzteres ist
  die eigentliche Forschung und **nicht in der Closed-Form-Gate-Welt beweisbar**.
- **Risiko:** Sim2Real-Lücke ist genuin; kann scheitern oder sehr teuer werden.

### A4 — Hardware & Systemintegration 🔬 (außerhalb des Software-Kerns)
- Sensorik/Perzeption, Verkabelung/EMV, Akku-/BMS, dexterous Hände, Echtzeit-Stack,
  Sicherheits-Zertifizierung. Mannjahre + Werkstatt/Kapital. Nicht GENESIS' Kern.

## Ehrliche Grenze A

GENESIS ist konstruktiv ein **Auslegungs- und Verifikations-Tool**, kein Lernsystem und
kein Ersatz für Detail-CAD-Konstrukteure. „Wie Optimus" **optisch** = A1 (machbar, aber
großer Umfang). „Wie Optimus" **technisch** = A3 (gelernter Ganzkörper-Regler + Sim2Real)
— das liegt prinzipiell außerhalb der deterministischen Gate-Philosophie und ist das
eigentliche schwere, unsichere Problem. **Ehrlicher erreichbarer Zwischenstand (12–24
Monate fokussiert, ohne A4):** ein verifiziertes, mechanisch detailliertes,
mehrkörper-dynamisch geprüftes **Humanoid-Designpaket** (detaillierte CAD + URDF +
Lastfall-Beweise + Aktuator-Auslegung + ein in-Sim laufender Regler) zur Übergabe an ein
Hardware-Team — **nicht** ein fertiger, laufender Optimus-Konkurrent.

---

# ZIEL B — Discovery jenseits Power-Law/Π-Templates

## IST-Stand (belegt)

Heute: zuverlässige **Rediscovery** von Power-Law/Π-Gesetzen (`discovery/engine.py`,
`discovery/benchmark.py` — live 6/6) und **eine** skalare 2.-Ordnung-ODE via SINDy
(`discovery/sindy.py`) aus den eigenen sauberen Simulatordaten. Echte **Maschinen-Beweise
nur für polynomiale/rationale Identitäten** (`proof_kernels.Z3IdentityKernel`,
`discovery/proof_loop.py`); Transzendentes bleibt „Kandidat", Lean/Coq ist ein Stub.
Erweiterungen `multiterm.py`/`transcendental.py`/`composition.py` + Hygiene-Gate
(`srbench_hygiene.py`) sind getestet, aber **template-gebunden**.

## 🔑 Höchster-Hebel-Erststep

**Eine echte symbolische Such-Engine (PySR / genetische Programmierung) hinter den
vorhandenen Proposer-Seam hängen.** `discovery/symbiosis.py` (`GrokProposer`) und
`discovery/tree_search.py` zeigen das Muster bereits: ein externer Proposer liefert
Kandidaten, die GENESIS-Gates entscheiden. Ein GP/PySR-Proposer durchbricht die
Power-Law-Familie **sofort**, ohne die Verifikations-Disziplin aufzugeben — jeder
Kandidat läuft weiter durch dimensional-check, `gate_c6`-recompute, `srbench_hygiene`
und `proof_loop`.

## Phasen

### B0 — Echte symbolische Regression als Proposer 🔧 (höchster Hebel)
- **Was:** PySR/gplearn-Adapter hinter dem Proposer-Seam (analog `GrokProposer`); liefert
  **beliebige Ausdrucksbäume** statt nur Power-Laws; jeder Kandidat durch
  dimensional + `gate_c6`-recompute + `srbench_hygiene` + `uncertainty`.
- **Baut auf:** `discovery/symbiosis.py`, `discovery/tree_search.py`, `discovery/engine.py`-Gates,
  `discovery/srbench_hygiene.py`, `discovery/feynman.py` (Benchmark).
- **Aufwand:** 3–6 Wochen · **Abhängigkeit:** PySR (opt-in, MIT/Apache).
- **DoD-Gate:** auf dem **Feynman-SRDB-Benchmark** schlägt der GP-Proposer die reine
  Power-Law-Engine bei den Nicht-Power-Law-Gleichungen messbar, **ohne** die Red-Team-/
  Hygiene-Catch-Rate zu senken; deterministisch (Seed); cross-model.

### B1 — Höherdimensionale & gekoppelte ODE/PDE-Systeme 🔧→🔬
- **Was:** SINDy von einer skalaren ODE auf **gekoppelte Systeme** (mehrere Zustände) +
  Weak-form (WSINDy) gegen Rauschen + erste PDE-Identifikation; weiterhin gespeist aus
  **verifizierten** Simulator-Trajektorien.
- **Baut auf:** `discovery/sindy.py`, `discovery/universe_bridge.py`, `simulation/backends.py`.
- **Aufwand:** 1–2 MM.
- **DoD-Gate:** Rediscovery eines gekoppelten Systems (z. B. Doppelpendel/Lotka-Volterra)
  aus Simulatordaten + Hygiene-Gate + Out-of-Sample-Validierung (`discovery/validation.py`).
- Überwiegend Engineering; Rauschrobustheit an echten Daten ist Frontier-Rand.

### B2 — Transzendente Beweise: Lean-Kernel anbinden 🔧 (mit Frontier-Tiefe)
- **Was:** den `LeanKernelStub` (`proof_kernels.py`) durch eine echte **Lean/Coq-Brücke**
  ersetzen (oder z3 um nichtlineare Taktiken erweitern), damit transzendente Identitäten
  von „Kandidat" zu „Satz" werden können. Das `ProofKernel`-Protokoll ist fertig.
- **Baut auf:** `proof_kernels.py`, `discovery/proof_loop.py`.
- **Aufwand:** 2–4 MM für die Brücke. Das automatische **Finden** transzendenter Beweise
  bleibt offen.
- **DoD-Gate:** mindestens eine nicht-polynomiale Identität end-to-end „Satz" + refutierte
  Gegenprobe mit Gegenbeispiel; cross-model.
- **Trennung:** Brücke = Engineering; automatische Beweissuche = 🔬 Frontier.

### B3 — Aktive Experiment-/Messplanung (Discovery-RL) 🔬
- **Was:** `discovery/rl_env.py` + `reward.py` + `active_resolution.py`/`active_search.py`
  zu einer Schleife schließen, die selbst entscheidet, **welche** Messung/Simulation als
  Nächstes den Hypothesenraum maximal trennt — der „verbessern"-Hebel über reine
  `composition` hinaus.
- **Baut auf:** `discovery/rl_env.py`, `discovery/reward.py`, `discovery/active_resolution.py`,
  `discovery/controller.py`.
- **Aufwand:** 2–4 MM.
- **DoD-Gate:** die aktive Schleife rediscovered ein Gesetz mit **messbar weniger Daten**
  als passives Sampling; deterministisch reproduzierbar; cross-model.

### B4 — Echtes „neues" Naturgesetz 🔬 (genuine Frontier, evtl. unlösbar)
- Eine Entdeckung, die **nicht** aus den Trainingsdaten/dem Generator stammt, an echten
  experimentellen Daten, peer-relevant. Offene Wissenschaft — kein Plan garantiert sie.
  GENESIS' realistischer Beitrag: ein disziplinierter Generator-+-Verifizierer, der
  Hypothesen ehrlich gated. Die Entdeckung selbst bleibt unsicher.

## Ehrliche Grenze B

Der **Verifikations-Kern** (dimensional, z3-polynomial, Hygiene, Out-of-Sample) ist echt
und übertragbar; begrenzt ist heute die **Entdeckungs-Breite** (Templates). B0/B1 heben das
real an. Aber: maschinelles Beweisen transzendenter/neuer Sätze (B2-Auto) und echte neue
Physik (B4) sind genuine Forschung — möglicherweise jahrelang oder prinzipiell nicht
„fertig". **Ehrlicher erreichbarer Zwischenstand (6–12 Monate):** ein allgemeiner
symbolischer Entdecker (beliebige Ausdrücke + gekoppelte ODEs) hinter denselben Gates, auf
Feynman-SRDB konkurrenzfähig, der transzendente Identitäten wenigstens als hochpräzise
„Kandidaten" liefert — **nicht** ein Automat, der neue Naturgesetze beweist.

---

# Reihenfolge-Empfehlung (Querschnitt)

1. **B0 zuerst** — billigster, klarster Gewinn (Wochen, reines Engineering, hoher Hebel,
   nutzt einen fertigen Seam). Durchbricht sofort die Power-Law-Grenze.
2. **A0 als A-Fundament** — ohne echte Mehrkörperdynamik ist alles Weitere bei Ziel A blockiert.
3. **A1** als größter Einzelposten für den optischen Sprung; **A2** koppelt Lastfälle.
4. Frontier (A3, B2-Auto, B3, B4) bewusst nachgelagert und als unsicher markiert.

# Übersicht

| Phase | Inhalt | Typ | Aufwand | DoD-Kern |
|---|---|---|---|---|
| A0 | Mehrkörper-Backend (MuJoCo) | 🔧 | 2–4 Wo | reproduziert Closed-Form-Momente + Energieerhaltung |
| A1 | GeometryNode-Vokabular erweitern | 🔧 | 2–4 MM | jede Op gegen OCCT-Volumen + watertight-STL |
| A2 | Aktuator/Struktur-Tiefe + Lastfälle | 🔧 | 1–2 MM | Dauer+Spitzen+Thermik-Gate gegen A0-Lasten |
| A3 | Ganzkörper-Regler / Gang | 🔬 | 6–18 MM | in-sim Gang + Sim2Real (Frontier) |
| A4 | Hardware/Integration | 🔬 | MJ | außerhalb Software-Kern |
| B0 | GP/PySR-Proposer hinter Gate | 🔧 | 3–6 Wo | schlägt Power-Law auf Feynman-SRDB, Hygiene hält |
| B1 | gekoppelte ODE/PDE-SINDy | 🔧→🔬 | 1–2 MM | Rediscovery gekoppeltes System + OOS |
| B2 | Lean-Kernel für transzendente Beweise | 🔧/🔬 | 2–4 MM | ≥1 nicht-poly. Identität „Satz" |
| B3 | aktive Experimentplanung | 🔬 | 2–4 MM | Gesetz mit weniger Daten als passiv |
| B4 | echtes neues Gesetz | 🔬 | offen | nicht garantierbar |

---

## Ein-Satz-Fazit

Beide Ziele sind aus dem heutigen Code **anschlussfähig** — die billigen, hohen Hebel sind
**B0** (GP-Proposer hinter den Gates) und **A0** (Mehrkörper-Seam ausbauen); der Rest ist
ehrliches Engineering (A1/A2/B1/B2-Brücke) bis genuine Forschung (A3-Sim2Real, B2-Auto,
B3, B4), und „wie Optimus" als laufendes Gesamtsystem bzw. „neue Physik beweisen" bleiben
außerhalb dessen, was GENESIS' Gate-Philosophie allein leisten kann.
