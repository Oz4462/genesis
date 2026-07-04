# Humanoid Energie & Thermik (Teilprojekt 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Batterie-Laufzeit und Motor-Überhitzung werden für beide Genesis-Humanoiden zu geprüften, gate-relevanten Physik-Checks — ohne neuen Validator-Code.

**Architecture:** Derived Quantities mit Formeln bilden die Leistungskette (Gelenk-Mechanikleistung → Lokomotionsleistung → Gesamtleistung); zwei neue `CheckRecipe`s verdrahten die existierenden Validatoren `battery_endurance` (flight.py:141) und `overtemperature` (thermal.py:119) über Robot-Measurands. Negativ-Tests beweisen, dass die Checks scharf sind.

**Tech Stack:** Python 3, uv (`uv run --extra dev python -m pytest`), dataclasses, Genesis-Interna: `CheckRecipe` (physics_selection.py:48), `_gm/_dm/_der/_claim` (demo.py), `assess_specification` (pipeline.py).

## Global Constraints

- Arbeitsverzeichnis: Worktree `/home/genesis/.claude/worktrees/claude-orchestrator` (NIE im Haupt-Checkout `/home/genesis` editieren — dort arbeitet Grok).
- Testkommando immer: `cd /home/genesis/.claude/worktrees/claude-orchestrator && PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest <pfad> -p no:cacheprovider -q`
- Kein neuer Validator, kein Fork von `battery_endurance_check`/`overtemperature_check`.
- Alle neuen Quantities brauchen `measurand=` (sonst feuert kein Recipe) und Grounding/Rationale (Genesis-Ehrlichkeit).
- Einheiten exakt wie angegeben: `Wh`, `min`, `W`, `W/mm/K`, `mm^2`, `mm`, `K` (verifiziert am Unit-Parser; `W/(m*K)` parst NICHT).
- Deutsch für Quantity-Namen/Rationales (Repo-Stil), Code-Kommentare knapp.

---

### Task 0: Worktree auf aktuellen main-Stand bringen

**Files:** keine Edits — nur git.

**Interfaces:**
- Produces: Worktree-Branch `worktree-claude-orchestrator` enthält Groks Commits bis mindestens `47f065f` (und, falls vorhanden, seine Seam-Migration für die 5 Demo-Specs).

- [ ] **Step 1: Merge main**

```bash
cd /home/genesis/.claude/worktrees/claude-orchestrator
git fetch . # noop, main ist lokal
git merge main -m "merge: main (Grok multi-physics + seam fixes) in Worktree"
```
Expected: Merge ohne Konflikte (Worktree hat bisher nur docs/.harness).

- [ ] **Step 2: Baseline-Testlauf der Humanoiden-Suite**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_competitive_humanoid.py -p no:cacheprovider -q
```
Expected: PASS, wenn Groks Seam-Migration committet ist. Falls `seams_failed`-FAILs: STOPP — in `/tmp/genesis-bridge/grok_status.md` prüfen, ob die Migration noch läuft; erst weitermachen, wenn main sie enthält (erneut Task 0).

- [ ] **Step 3: Commit nicht nötig** (Merge-Commit reicht).

---

### Task 1: Config-Felder + Energie-Quantities + Claims

**Files:**
- Modify: `src/gen/competitive_humanoid.py` (HumanoidConfig ~Zeile 60-98; quantities-Liste nach `q_ctrl_period` ~Zeile 322; `_humanoid_claims` ~Zeile 499; PRINTED_HUMANOID ~Zeile 537; FLAGSHIP_HUMANOID ~Zeile 571)
- Test: `tests/test_humanoid_energy.py` (neu)

**Interfaces:**
- Consumes: `_gm(qid, name, value, unit, grounding, measurand)`, `_dm(qid, name, value, unit, rationale, measurand)`, `_der(qid, name, value, unit, formula, inputs)` aus `gen.demo`; vorhandene Quantities `q_jt` (N*m), `q_js` (rad/s), `q_eff` (1), `q_chip_pbudget` (W).
- Produces: Quantities `q_batt_cap` (measurand `battery.capacity`, Wh), `q_loco_duty` (`robot.locomotion_duty`, 1), `q_n_drive` (`robot.n_drive_motors`, 1), `q_p_mech_joint` (`robot.joint_mech_power`, W), `q_p_loco` (`robot.locomotion_power`, W), `q_p_total` (`robot.total_power`, W), `q_endurance_req` (`robot.required_endurance`, min); Config-Felder `battery_capacity_wh`, `required_endurance_min`, `locomotion_duty`, `n_drive_motors` (float).

- [ ] **Step 1: Failing Test schreiben** — `tests/test_humanoid_energy.py`:

```python
"""Teilprojekt 1 (Energie & Thermik): Laufzeit- und Motor-Thermik-Checks der Humanoiden."""
from gen.competitive_humanoid import FLAGSHIP_HUMANOID, PRINTED_HUMANOID, build_humanoid


def _quantity(spec, qid):
    m = {q.id: q for q in spec.quantities}
    assert qid in m, f"{qid} fehlt in Spec {spec.run_id}"
    return m[qid]


def test_energy_quantities_present_and_consistent():
    for cfg in (PRINTED_HUMANOID, FLAGSHIP_HUMANOID):
        spec = build_humanoid(cfg)
        cap = _quantity(spec, "q_batt_cap")
        assert cap.unit == "Wh" and cap.value == cfg.battery_capacity_wh
        assert cap.measurand == "battery.capacity"
        req = _quantity(spec, "q_endurance_req")
        assert req.unit == "min" and req.value == cfg.required_endurance_min
        # Leistungskette: Werte konsistent mit den Formeln
        p_mech = _quantity(spec, "q_p_mech_joint")
        assert abs(p_mech.value - cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty) < 1e-9
        p_loco = _quantity(spec, "q_p_loco")
        assert abs(p_loco.value - cfg.n_drive_motors * p_mech.value / cfg.efficiency) < 1e-9
        p_total = _quantity(spec, "q_p_total")
        assert abs(p_total.value - (p_loco.value + cfg.compute_power_budget_w)) < 1e-9
        # Formeln sind DERIVED (Gate rechnet nach), Kapazität ist GROUNDED
        assert p_total.derivation is not None and cap.grounding
```

- [ ] **Step 2: Test läuft rot**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_humanoid_energy.py -p no:cacheprovider -q
```
Expected: FAIL (`battery_capacity_wh` existiert nicht / `q_batt_cap fehlt`).

- [ ] **Step 3: Implementieren**

3a. `HumanoidConfig` — nach `battery_name: str` einfügen:

```python
    # --- Energie & Laufzeit (Teilprojekt 1) ---
    battery_capacity_wh: float = 0.0       # nutzbare Nennkapazität des BOM-Packs
    required_endurance_min: float = 0.0    # geforderte Dauerbetriebszeit
    locomotion_duty: float = 0.0           # RMS-Duty der Antriebe über den Gangzyklus
    n_drive_motors: float = 0.0            # gleichzeitig arbeitende Antriebsmotoren
```
(Defaults 0.0 nur, falls HumanoidConfig bereits Felder mit Defaults hat — sonst OHNE Defaults einfügen, vor `prices`.)

3b. In der `quantities`-Liste nach `q_ctrl_period` einfügen:

```python
        # --- Energie & Laufzeit (Teilprojekt 1): Akku trägt Antrieb + Compute ---
        _gm("q_batt_cap", "nutzbare Akkukapazität", cfg.battery_capacity_wh, "Wh",
            ["c_battery_capacity"], "battery.capacity"),
        _dm("q_loco_duty", "Antriebs-RMS-Duty im Gangzyklus", cfg.locomotion_duty, "1",
            "RMS-Anteil des Spitzenmoments über den Gangzyklus", "robot.locomotion_duty"),
        _dm("q_n_drive", "gleichzeitig arbeitende Antriebe", cfg.n_drive_motors, "1",
            "Hüfte/Knie/Knöchel beider Beine im Wechselgang", "robot.n_drive_motors"),
        _der("q_p_mech_joint", "mechanische Gelenkleistung (RMS)",
             cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty, "W",
             "q_jt * q_js * q_loco_duty", ("q_jt", "q_js", "q_loco_duty")),
        _der("q_p_loco", "Lokomotionsleistung elektrisch",
             cfg.n_drive_motors * cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty / cfg.efficiency,
             "W", "q_n_drive * q_p_mech_joint / q_eff", ("q_n_drive", "q_p_mech_joint", "q_eff")),
        _der("q_p_total", "Gesamt-Dauerleistung (Antrieb + Compute)",
             cfg.n_drive_motors * cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty / cfg.efficiency
             + cfg.compute_power_budget_w,
             "W", "q_p_loco + q_chip_pbudget", ("q_p_loco", "q_chip_pbudget")),
        _dm("q_endurance_req", "geforderte Dauerbetriebszeit", cfg.required_endurance_min, "min",
            "Wettbewerbsanker 2026 (Unitree H2 ~2-4 h)", "robot.required_endurance"),
```
mit Measurand-Tagging von `q_p_total` — WICHTIG: `_der` hat keinen measurand-Parameter. Prüfen: `grep -n "def _der" src/gen/demo.py`. Falls kein measurand-Support: `_der(...)` erzeugt `Quantity(...)`; dann stattdessen direkt `Quantity(id=..., origin=ValueOrigin.DERIVED, derivation=Derivation(...), measurand="robot.total_power")` konstruieren oder einen lokalen Helper `_derm` im Modul ergänzen:

```python
def _derm(qid, name, value, unit, formula, inputs, measurand):
    q = _der(qid, name, value, unit, formula, inputs)
    return replace(q, measurand=measurand)  # from dataclasses import replace
```
(`q_p_mech_joint` braucht KEINEN measurand — er ist nur Formel-Zwischenschritt; `q_p_total` braucht `robot.total_power`.)

3c. In `_humanoid_claims` ergänzen:

```python
        _claim("c_battery_capacity",
               f"Der Akkupack liefert nutzbare {cfg.battery_capacity_wh:.0f} Wh."),
        _claim("c_endurance_requirement",
               f"Dauerbetrieb von {cfg.required_endurance_min:.0f} min ist gefordert "
               "(2026-Wettbewerb: Unitree H2 läuft 2-4 h)."),
```

3d. Config-Werte: PRINTED_HUMANOID: `battery_capacity_wh=2100.0, required_endurance_min=120.0, locomotion_duty=0.35, n_drive_motors=8.0`; FLAGSHIP_HUMANOID: `battery_capacity_wh=2600.0, required_endurance_min=180.0, locomotion_duty=0.4, n_drive_motors=8.0`.

- [ ] **Step 4: Test grün**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_humanoid_energy.py -p no:cacheprovider -q
```
Expected: 1 passed. Zusätzlich Regressionscheck:
```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_competitive_humanoid.py -p no:cacheprovider -q
```
Expected: PASS (Zahl wie Task-0-Baseline).

- [ ] **Step 5: Commit**

```bash
git add src/gen/competitive_humanoid.py tests/test_humanoid_energy.py
git commit -m "feat(humanoid): Energie-Quantities + Leistungskette (battery.capacity, robot.total_power)"
```

---

### Task 2: Recipe "robot battery endurance" + Negativ-Test

**Files:**
- Modify: `src/gen/physics_selection.py` (RECIPES-Liste, im robot/humanoid-Block nach dem "joint swing torque"-Recipe)
- Test: `tests/test_humanoid_energy.py` (erweitern)

**Interfaces:**
- Consumes: Measurands aus Task 1; Validator-Key `"battery_endurance"` (physics_validation.py:165); `assess_specification` aus `gen.pipeline`; `dataclasses.replace` für Config-Varianten.
- Produces: PhysicsCheck `robot battery endurance` feuert für beide Humanoiden.

- [ ] **Step 1: Failing Tests ergänzen** — an `tests/test_humanoid_energy.py` anhängen:

```python
from dataclasses import replace

from gen.pipeline import assess_specification


def _check_names(assessment):
    return {c.name for c in assessment.physics_checks}


def test_battery_endurance_check_fires_and_passes():
    for cfg in (PRINTED_HUMANOID, FLAGSHIP_HUMANOID):
        a = assess_specification(build_humanoid(cfg))
        assert "robot battery endurance" in _check_names(a)
        assert a.overall == "physics_verified", a.overall


def test_undersized_battery_fails_endurance():
    tiny = replace(PRINTED_HUMANOID, run_id="printed_tiny_batt", battery_capacity_wh=200.0)
    a = assess_specification(build_humanoid(tiny))
    assert a.overall != "physics_verified"
    failed = {f.check for f in a.physics_gate.failures} if a.physics_gate.failures else set()
    assert any("battery" in name for name in failed), failed
```
(Vor dem Zuschnitt prüfen: `GateFailure`-Feldname für den Check — `grep -n "class GateFailure" -A 8 src/gen/core/interfaces.py`; Attribut ggf. `check`/`code`/`detail` anpassen, Assertion auf das Feld, das den Check-Namen trägt.)

- [ ] **Step 2: Tests rot**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_humanoid_energy.py -p no:cacheprovider -q
```
Expected: `test_battery_endurance_check_fires_and_passes` FAIL (Check fehlt).

- [ ] **Step 3: Recipe einfügen** — `src/gen/physics_selection.py`, im humanoid-Block:

```python
    # ---- robot energy: der Akku muss Antrieb + Compute über die geforderte Zeit tragen ----
    CheckRecipe(
        name="robot battery endurance", validator="battery_endurance",
        trigger="robot.required_endurance",
        inputs={
            "capacity_wh": ("battery.capacity", "Wh"),
            "hover_power_w": ("robot.total_power", "W"),
            "required_endurance_min": ("robot.required_endurance", "min"),
        },
    ),
```

- [ ] **Step 4: Tests grün**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_humanoid_energy.py tests/test_competitive_humanoid.py -p no:cacheprovider -q
```
Expected: alle PASS. Rechenprobe printed: 2100 Wh · 0.8(default usable) / P_total — prüfen, dass P_total plausibel (<800 W) und endurance > 120 min; sonst Config-Duty/η nachjustieren UND im Claim begründen.

- [ ] **Step 5: Commit**

```bash
git add src/gen/physics_selection.py tests/test_humanoid_energy.py
git commit -m "feat(humanoid): battery_endurance-Check via robot-Measurands (Recipe, Negativ-Test)"
```

---

### Task 3: Motor-Thermik — Quantities + Overtemperature-Recipe + Tests

**Files:**
- Modify: `src/gen/competitive_humanoid.py` (Config + quantities + claims + beide Configs), `src/gen/physics_selection.py` (RECIPES)
- Test: `tests/test_humanoid_energy.py` (erweitern)

**Interfaces:**
- Consumes: `overtemperature_check(power, conductivity, area, length, *, ambient, max_service_temp)` — thermal.py:119; Einheiten-Konvention: k in W/(mm·K), Längen mm (thermal.py:24). Recipe-Inputs werden als kwargs übergeben (`fn(**check.inputs)`, physics_validation.py:226) — keyword-only ist damit erreichbar.
- Produces: Check `drive motor overtemperature (conduction bound)` feuert und besteht; Miniatur-Wärmepfad führt zu Gate-Fail.

- [ ] **Step 1: Failing Tests ergänzen**

```python
def test_motor_overtemperature_check_fires_and_passes():
    for cfg in (PRINTED_HUMANOID, FLAGSHIP_HUMANOID):
        a = assess_specification(build_humanoid(cfg))
        assert "drive motor overtemperature (conduction bound)" in _check_names(a)
        assert a.overall == "physics_verified", a.overall


def test_bad_heat_path_fails_overtemperature():
    hot = replace(PRINTED_HUMANOID, run_id="printed_hot_motor",
                  motor_housing_area_m2=1e-6, motor_housing_length_m=0.5)
    a = assess_specification(build_humanoid(hot))
    assert a.overall != "physics_verified"
```

- [ ] **Step 2: Tests rot** (Kommando wie oben). Expected: AttributeError/`q fehlt`.

- [ ] **Step 3: Implementieren**

3a. Config-Felder (nach den Task-1-Feldern):

```python
    motor_housing_conductivity_w_mk: float = 0.0  # Wärmepfad Wicklung→Gehäuse, W/(m*K)
    motor_housing_area_m2: float = 0.0            # Leitquerschnitt, m^2
    motor_housing_length_m: float = 0.0           # Pfadlänge, m
    motor_max_winding_temp_k: float = 0.0         # Isolationsklasse (F = 428 K)
    ambient_temp_k: float = 0.0                   # Auslegungs-Umgebung
```

3b. Quantities (nach `q_endurance_req`):

```python
        # --- Motor-Thermik: Verlustleistung je Antrieb gegen Wicklungsgrenze ---
        _der("q_p_motor_loss", "Verlustleistung je Antrieb",
             cfg.joint_torque_nm * cfg.joint_speed_rad_s * cfg.locomotion_duty * (1.0 - cfg.efficiency) / cfg.efficiency,
             "W", "q_p_mech_joint * (1.0 - q_eff) / q_eff", ("q_p_mech_joint", "q_eff")),
        _gm("q_motor_k", "Wärmeleitpfad Wicklung→Gehäuse", cfg.motor_housing_conductivity_w_mk,
            "W/m/K", ["c_motor_thermal"], "motor.housing_conductivity"),
        _dm("q_motor_area", "Leitquerschnitt", cfg.motor_housing_area_m2, "m^2",
            "Statorumfang x Gehäusewand", "motor.housing_area"),
        _dm("q_motor_len", "Leitpfadlänge", cfg.motor_housing_length_m, "m",
            "Wicklung→Außenfläche", "motor.housing_length"),
        _gm("q_motor_tmax", "max. Wicklungstemperatur", cfg.motor_max_winding_temp_k, "K",
            ["c_motor_thermal"], "motor.max_winding_temp"),
        _dm("q_ambient", "Auslegungs-Umgebungstemperatur", cfg.ambient_temp_k, "K",
            "Innenraum 25 °C", "robot.ambient_temp"),
```
`q_p_motor_loss` braucht measurand `motor.loss_power` — wie in Task 1 via `_derm` (oder direkter Quantity-Konstruktion).

3c. Claim:

```python
        _claim("c_motor_thermal",
               "Die Antriebe nutzen Klasse-F-Isolation (155 °C) mit Alu-Gehäusepfad "
               "zur Wärmeabfuhr; der konduktive Worst-Case bleibt unter der Grenze."),
```

3d. Config-Werte beide Humanoiden: `motor_housing_conductivity_w_mk=170.0` (Alu-Druckguss), `motor_housing_area_m2=0.0015`, `motor_housing_length_m=0.02`, `motor_max_winding_temp_k=428.0`, `ambient_temp_k=298.0`.
Plausibilitätsrechnung printed (τ=45 N*m? — exakten cfg-Wert nehmen): ΔT = P_loss·L/(k·A); mit P_loss≈q_jt·q_js·duty·(1-η)/η. Werte einsetzen, ΔT muss < 130 K bleiben; sonst area/length anpassen (physisch begründbar halten!).

3e. Recipe:

```python
    CheckRecipe(
        name="drive motor overtemperature (conduction bound)", validator="overtemperature",
        trigger="motor.loss_power",
        inputs={
            "power": ("motor.loss_power", "W"),
            "conductivity": ("motor.housing_conductivity", "W/mm/K"),
            "area": ("motor.housing_area", "mm^2"),
            "length": ("motor.housing_length", "mm"),
            "ambient": ("robot.ambient_temp", "K"),
            "max_service_temp": ("motor.max_winding_temp", "K"),
        },
    ),
```
(Konvertierung: Quantity in W/m/K → Recipe fordert W/mm/K, Faktor 0.001; m² → mm² Faktor 1e6; m → mm Faktor 1000 — macht `_resolve` automatisch. Damit rechnet der Validator konsistent in mm-Einheiten, thermal.py:24.)

- [ ] **Step 4: Tests grün** — beide neuen Tests + Humanoiden-Suite + `tests/test_phase_epsilon.py` (Seam-Regression: neue Quantities dürfen keine neuen Pflicht-Paare erzeugen; THERMAL/ELEC waren schon präsent).

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/test_humanoid_energy.py tests/test_competitive_humanoid.py tests/test_phase_epsilon.py -p no:cacheprovider -q
```
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gen/competitive_humanoid.py src/gen/physics_selection.py tests/test_humanoid_energy.py
git commit -m "feat(humanoid): Motor-Overtemperature-Check (Konduktions-Schranke) via Recipe"
```

---

### Task 4: Benchmark-Erweiterung + volle Suite + Abschluss

**Files:**
- Modify: `tests/test_competitive_humanoid.py` (Benchmark-Test, ~Zeile 77)
- Modify: `docs/BUILD_LOG.md` (Eintrag ans Ende)

**Interfaces:**
- Consumes: Check-Resultate via `run_physics_checks`/Assessment; Benchmark-Stil des bestehenden Tests (`test_flagship_beats_the_2026_benchmark`).

- [ ] **Step 1: Failing Benchmark-Erweiterung** — im bestehenden `test_flagship_beats_the_2026_benchmark` (Stil des Tests übernehmen; er prüft available_torque/reach/TOPS-Quantities der Flagship-Spec) ergänzen:

```python
    # 2026-Energie-Anker: Flagship muss >= 180 min Dauerbetrieb nachweisen
    spec = build_humanoid(FLAGSHIP_HUMANOID)
    a = assess_specification(spec)
    endurance = next(r for c, r in zip(a.physics_checks, run_physics_checks(a.physics_checks))
                     if c.name == "robot battery endurance")
    assert endurance["endurance_min"] >= 180.0
    assert endurance["ok"]
```
(Falls der Test bisher ohne `assess_specification` arbeitet: Import + Aufruf lokal im Test; `run_physics_checks` aus `gen.physics_validation`.)

- [ ] **Step 2: rot laufen lassen, dann ggf. nichts implementieren** — wenn Task 1-3 korrekt: sofort grün. Rot nur bei unplausiblen Config-Werten → Werte in FLAGSHIP anpassen (physikalisch begründet, Claim aktualisieren).

- [ ] **Step 3: Volle Suite**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run -q --extra dev python -m pytest tests/ -p no:cacheprovider -q --ignore=tests/test_build123d.py
```
Expected: 0 failed (Skips ok). JEDER Fail wird behoben, bevor weitergemacht wird.

- [ ] **Step 4: BUILD_LOG-Eintrag** — ans Ende von `docs/BUILD_LOG.md`:

```markdown
## 2026-07-04 — Humanoid Teilprojekt 1: Energie & Thermik (Claude)
Batterie-Laufzeit (battery_endurance) und Motor-Überhitzung (overtemperature,
Konduktions-Schranke) sind jetzt gate-relevante Checks beider Humanoiden.
Leistungskette als DERIVED-Formeln (q_p_mech_joint → q_p_loco → q_p_total),
kein neuer Validator. Negativ-Tests beweisen Schärfe (200-Wh-Akku und
Miniatur-Wärmepfad fallen durch). Benchmark: Flagship ≥ 180 min.
Spec: docs/superpowers/specs/2026-07-04-humanoid-energy-thermal-design.md
```

- [ ] **Step 5: Commit + Abschluss**

```bash
git add tests/test_competitive_humanoid.py docs/BUILD_LOG.md
git commit -m "feat(humanoid): 2026-Benchmark um Endurance erweitert + BUILD_LOG"
```
Danach: Cross-Review-Anforderung an Grok in `/tmp/genesis-bridge/tasks_for_claude.md`-Gegenrichtung (`tasks_for_grok.md`) schreiben; Branch-Integration mit Ozan/Grok koordinieren (main gehört Grok — KEIN eigenmächtiger Merge nach main, stattdessen Bridge-Notiz + ggf. Push des Branches).
