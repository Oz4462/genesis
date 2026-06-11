"""δ-DFM: deterministic Design-for-Manufacturability rules, with NO new gate code.

A spec can pass geometry and statics and still be un-printable. The DFM layer adds
the FDM rules GENESIS can prove from the existing quantities — minimum wall
thickness (two perimeters of a 0.4 mm nozzle = 0.8 mm) and minimum printable hole
diameter (2.0 mm). Each is a GROUNDED/DERIVED quantity plus a numeric constraint
(C-13), dimension-checked by C-15.

Orientation-dependent rules (overhang > 45°, bridge span) need a build-orientation
model the CSG does not carry; they are declared as gaps, not silently passed — a
passed DFM check is necessary, not sufficient.

Offline, no LLM, no network.

Run:  pytest tests/test_dfm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Constraint,
    Derivation,
    Question,
    Quantity,
    RunState,
    Specification,
    ValueOrigin,
)
from gen.dfm import (  # noqa: E402
    FDM_MIN_HOLE_DIAMETER_MM,
    FDM_MIN_WALL_MM,
    FDM_NOZZLE_DIAMETER_MM,
    FDM_WALL_PERIMETERS_MIN,
    min_wall_formula,
)
from gen.verification.derivation import evaluate_formula  # noqa: E402
from gen.verification.gates import gate_gamma  # noqa: E402


def test_fdm_reference_values():
    assert FDM_NOZZLE_DIAMETER_MM == 0.4
    assert FDM_WALL_PERIMETERS_MIN == 2.0
    assert FDM_MIN_WALL_MM == 0.8                       # 2 × 0.4
    assert FDM_MIN_HOLE_DIAMETER_MM == 2.0
    assert min_wall_formula("q_nozzle", "q_perimeters") == "q_nozzle * q_perimeters"


def _dfm_state(*, thickness: float, hole: float) -> RunState:
    """Minimal spec carrying only the two DFM rules (DECISION dims, so no claims
    needed). min_wall is recomputed with the real evaluator (no drift)."""
    f = min_wall_formula("q_nozzle", "q_perimeters")
    min_wall = evaluate_formula(f, {"q_nozzle": FDM_NOZZLE_DIAMETER_MM,
                                    "q_perimeters": FDM_WALL_PERIMETERS_MIN})

    def _dec(qid, value, unit="mm"):
        return Quantity(id=qid, name=qid, value=value, unit=unit,
                        origin=ValueOrigin.DECISION, rationale="declared")

    quantities = [
        _dec("q_t", thickness), _dec("q_hole_d", hole),
        _dec("q_nozzle", FDM_NOZZLE_DIAMETER_MM), _dec("q_perimeters", FDM_WALL_PERIMETERS_MIN, "1"),
        Quantity(id="q_min_wall", name="min wall", value=min_wall, unit="mm",
                 origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula=f, inputs=("q_nozzle", "q_perimeters"))),
        _dec("q_min_hole", FDM_MIN_HOLE_DIAMETER_MM),
    ]
    spec = Specification(
        run_id="r", idea="dfm", quantities=quantities,
        constraints=[
            Constraint(id="k_dfm_wall", kind="ge", left="q_t", right="q_min_wall",
                       reason="printable wall"),
            Constraint(id="k_dfm_hole", kind="ge", left="q_hole_d", right="q_min_hole",
                       reason="printable hole"),
        ],
    )
    st = RunState(question=Question(raw="dfm", run_id="r"))
    st.specification = spec
    return st


def test_printable_part_passes():
    result = gate_gamma(_dfm_state(thickness=12.0, hole=4.5))
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_too_thin_wall_trips_constraint():
    # a 0.3 mm wall is below the 0.8 mm minimum -> would not print reliably
    codes = {f.code for f in gate_gamma(_dfm_state(thickness=0.3, hole=4.5)).failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, codes


def test_too_small_hole_trips_constraint():
    # a 1.0 mm horizontal hole is below the 2.0 mm minimum
    codes = {f.code for f in gate_gamma(_dfm_state(thickness=12.0, hole=1.0)).failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, codes


def test_capstone_is_printable():
    from gen.demo import capstone_state
    st = capstone_state()
    assert gate_gamma(st).passed
    q = {x.id: x for x in st.specification.quantities}
    assert q["q_t"].value >= q["q_min_wall"].value
    assert q["q_hole_d"].value >= q["q_min_hole"].value
