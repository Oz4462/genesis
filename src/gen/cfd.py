"""GATE CFD — a real OpenFOAM-backed fluid-dynamics validation axis (a NEW axis).

The δ-physics validators (``physics_validation.py``) are closed-form / FEM screens that
each answer ONE failure mode by pure computation, with no external solver. Fluid dynamics
has no such single closed form for a general geometry: the honest tool is a CFD run. This
module is that axis. It does NOT fabricate a drag number from a correlation and call it
verified — it writes a real OpenFOAM case, runs ``blockMesh`` + ``simpleFoam`` as
subprocesses, parses the solver's own output, and (for the validating case) compares the
solver's independently-computed field against an analytic closed form. The verdict is
honest by construction:

  • OpenFOAM not installed  → ``CFDError`` (loud; never a silent "ok").
  • mesh/solver returncode ≠ 0 or solver diverged → ``ok=False`` with the captured reason
    (an un-evaluatable case is surfaced, not swallowed, and never a silent pass).
  • solver ran and converged, AND its field matches the closed form within tolerance
    → ``ok=True``; outside tolerance → ``ok=False`` (the CFD result disagreeing with
    theory is a real, reportable gap, not something to paper over).

Why a SEPARATE gate (``gate_cfd``) and registry (``CFD_VALIDATORS``) instead of folding
into ``physics_validation.VALIDATORS``: the δ-physics gate is pure, deterministic and
fast (it runs in the inner pipeline loop and in every offline test). A CFD check spawns
external processes and takes seconds. Mixing them would make the fast gate slow and
non-hermetic. So CFD is its own opt-in axis with the SAME contract (validator returns a
``{..., "ok": bool}`` dict; ``gate_cfd(checks) -> GateResult``), composed alongside —
not inside — the δ-physics gate.

Validated case: pressure-/body-force-driven LAMINAR plane Poiseuille flow between two
parallel plates (the canonical channel flow). For a constant streamwise body force
``g`` [m/s²], kinematic viscosity ``ν`` [m²/s] and plate spacing ``H`` [m], the
fully-developed profile is ``u(y) = g/(2ν)·(h² − (y−h)²)`` with ``h = H/2``, so the
centreline maximum is ``u_max = g·h²/(2ν)`` and the mean is ``2/3·u_max``. OpenFOAM
solves the incompressible Navier–Stokes momentum equation on a 1-D-in-x cyclic channel
and we recover ``u_max`` to ~0 % and the parabola to <0.1 % L2 on a 40-cell mesh (the
residual is genuine second-order discretisation error of a parabola, documented — not a
tuned-to-pass artefact).

Honest boundary: this validates the SOLVER PIPELINE and the laminar momentum balance
against theory. It is not a turbulence-model validation, not a mesh-independence study,
and not a claim about any arbitrary geometry — those are larger CFD efforts. What it
gives Genesis is a real, fail-loud CFD verdict for cases it actually runs, replacing any
"trust me, the drag is X" with "OpenFOAM computed it and it matches the closed form".
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .core.errors import GenesisError
from .core.interfaces import GateFailure, GateResult

#: OpenFOAM ships an environment file that must be sourced before its tools find their
#: ``etc`` entries (WM_PROJECT_DIR et al. are empty otherwise). On this box it lives here;
#: overridable via $FOAM_BASHRC for other installs.
DEFAULT_FOAM_BASHRC = os.environ.get("FOAM_BASHRC", "/usr/share/openfoam/etc/bashrc")

#: Solver binaries. Overridable so a test can point at a nonexistent name to exercise the
#: missing-binary failure path without uninstalling OpenFOAM.
BLOCKMESH = os.environ.get("GENESIS_BLOCKMESH", "blockMesh")
SIMPLEFOAM = os.environ.get("GENESIS_SIMPLEFOAM", "simpleFoam")

#: Convergence threshold on the streamwise-velocity INITIAL residual reported by the
#: linear solver: the momentum equation is genuinely converged when its initial residual
#: per outer iteration has fallen below this. (At our default iteration count it reaches
#: ~1e-9; 1e-6 is a conservative "definitely converged" bar.)
U_RESIDUAL_CONVERGED = 1e-6

#: Default acceptance tolerance (relative) for the OpenFOAM field vs the analytic closed
#: form. 2 % comfortably covers the ~0.1 % discretisation error on the default mesh while
#: still failing a genuinely wrong result. Caller-overridable.
DEFAULT_REL_TOLERANCE = 0.02


class CFDError(GenesisError):
    """A CFD run could not be performed at all (OpenFOAM missing, or its environment
    file absent). Loud per CLAUDE.md §1 + §"keine stillen Defaults": a CFD axis with no
    solver must fail, never return a fabricated or vacuous "ok"."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"CFD (OpenFOAM) unavailable: {reason}")


@dataclass(frozen=True)
class CFDRun:
    """Raw outcome of an OpenFOAM subprocess pipeline (before any physics judgement).

    `ok_process` is True iff every stage returned 0. `converged` reflects the solver's
    own residual reaching the threshold. `case_dir` is kept only when `keep=True`.
    """

    ok_process: bool
    converged: bool
    blockmesh_rc: int
    simplefoam_rc: int
    u_initial_residual: float | None
    case_dir: str | None
    stderr_tail: str


def openfoam_available(foam_bashrc: str = DEFAULT_FOAM_BASHRC) -> bool:
    """True iff the OpenFOAM environment file and both solver binaries are present.

    Used by callers/tests to skip-guard. Does NOT raise — it is the cheap predicate;
    :func:`run_poiseuille_case` is the one that raises :class:`CFDError`.
    """
    return (
        Path(foam_bashrc).is_file()
        and shutil.which(BLOCKMESH) is not None
        and shutil.which(SIMPLEFOAM) is not None
    )


# --- OpenFOAM case templates (plane Poiseuille, body-force driven, cyclic in x) -------
# Kept as literal dictionaries so the case is fully reproducible and self-contained; the
# numeric controls that the validator varies (mesh count, viscosity, body force, endTime)
# are substituted via str.format.

_CONTROL_DICT = """\
FoamFile {{ version 2.0; format ascii; class dictionary; object controlDict; }}
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   {end_time};
purgeWrite      1;
writeFormat     ascii;
writePrecision  10;
runTimeModifiable false;
"""

_FV_SCHEMES = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linear;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes{ default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

_FV_SOLUTION = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers
{
    p { solver GAMG; tolerance 1e-08; relTol 0.01; smoother GaussSeidel; }
    U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-08; relTol 0.1; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      yes;
    pRefCell        0;
    pRefValue       0;
    residualControl { p 1e-6; U 1e-6; }
}
relaxationFactors { equations { U 0.9; } }
"""

_BLOCKMESH_DICT = """\
FoamFile {{ version 2.0; format ascii; class dictionary; object blockMeshDict; }}
convertToMeters 1;
vertices
(
    (0      0      0)
    ({L}    0      0)
    ({L}    {H}    0)
    (0      {H}    0)
    (0      0      {D})
    ({L}    0      {D})
    ({L}    {H}    {D})
    (0      {H}    {D})
);
blocks ( hex (0 1 2 3 4 5 6 7) (1 {ny} 1) simpleGrading (1 1 1) );
edges ();
boundary
(
    inlet  {{ type cyclic; neighbourPatch outlet; faces ((0 4 7 3)); }}
    outlet {{ type cyclic; neighbourPatch inlet;  faces ((1 2 6 5)); }}
    bottom {{ type wall;   faces ((0 1 5 4)); }}
    top    {{ type wall;   faces ((3 7 6 2)); }}
    frontAndBack {{ type empty; faces ((0 3 2 1) (4 5 6 7)); }}
);
"""

_TRANSPORT = """\
FoamFile {{ version 2.0; format ascii; class dictionary; object transportProperties; }}
transportModel  Newtonian;
nu              {nu};
"""

_TURBULENCE = """\
FoamFile { version 2.0; format ascii; class dictionary; object turbulenceProperties; }
simulationType laminar;
"""

_FIELD_U = """\
FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    inlet  { type cyclic; }
    outlet { type cyclic; }
    bottom { type noSlip; }
    top    { type noSlip; }
    frontAndBack { type empty; }
}
"""

_FIELD_P = """\
FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    inlet  { type cyclic; }
    outlet { type cyclic; }
    bottom { type zeroGradient; }
    top    { type zeroGradient; }
    frontAndBack { type empty; }
}
"""

_FV_OPTIONS = """\
FoamFile {{ version 2.0; format ascii; class dictionary; object fvOptions; }}
momentumSource
{{
    type            vectorSemiImplicitSource;
    selectionMode   all;
    volumeMode      specific;
    injectionRateSuSp {{ U (({gx} 0 0) 0); }}
}}
"""


def _write_case(
    case: Path, *, height: float, length: float, depth: float, n_cells: int,
    nu: float, body_force: float, end_time: int,
) -> None:
    """Materialise a complete plane-Poiseuille OpenFOAM case directory on disk."""
    (case / "system").mkdir(parents=True, exist_ok=True)
    (case / "constant").mkdir(parents=True, exist_ok=True)
    (case / "0").mkdir(parents=True, exist_ok=True)
    (case / "system" / "controlDict").write_text(_CONTROL_DICT.format(end_time=end_time))
    (case / "system" / "fvSchemes").write_text(_FV_SCHEMES)
    (case / "system" / "fvSolution").write_text(_FV_SOLUTION)
    (case / "system" / "blockMeshDict").write_text(
        _BLOCKMESH_DICT.format(H=height, L=length, D=depth, ny=n_cells))
    (case / "system" / "fvOptions").write_text(_FV_OPTIONS.format(gx=body_force))
    (case / "constant" / "transportProperties").write_text(_TRANSPORT.format(nu=nu))
    (case / "constant" / "turbulenceProperties").write_text(_TURBULENCE)
    (case / "0" / "U").write_text(_FIELD_U)
    (case / "0" / "p").write_text(_FIELD_P)


def _run_foam_tool(tool: str, case: Path, foam_bashrc: str) -> subprocess.CompletedProcess:
    """Run one OpenFOAM tool in `case`, sourcing the environment file first.

    OpenFOAM tools need their env sourced (WM_PROJECT_DIR etc.), so we invoke through
    ``bash -c 'source <bashrc>; <tool>'`` rather than exec'ing the binary directly.
    """
    cmd = f"source {foam_bashrc!r} >/dev/null 2>&1; exec {tool}"
    return subprocess.run(
        ["bash", "-c", cmd],
        cwd=str(case),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _parse_last_u_initial_residual(simplefoam_stdout: str) -> float | None:
    """Pull the last streamwise-velocity (Ux) INITIAL residual from simpleFoam output.

    Returns None if no Ux solve line is present (a solver that never advanced). This is
    the solver's OWN measure of how far the momentum equation is from converged.
    """
    matches = re.findall(
        r"Solving for Ux,\s*Initial residual = ([0-9.eE+-]+)", simplefoam_stdout)
    return float(matches[-1]) if matches else None


def _parse_u_profile(u_file: Path) -> list[float]:
    """Read the streamwise velocity (Ux) of every cell from an OpenFOAM volVectorField.

    The mesh is one cell thick in x and z, so the internalField is exactly the column of
    cells across the channel height, bottom-to-top. Raises CFDError if the field cannot
    be parsed (a missing/garbled result must surface, never be treated as zeros).
    """
    txt = u_file.read_text()
    # OpenFOAM writes a small field inline — "nonuniform List<vector> 8((..)(..))" — and a
    # large one block-formatted with newlines. Match the count, then the parenthesised body
    # up to the matching close before the ';', whitespace-agnostic so both layouts parse.
    m = re.search(r"nonuniform List<vector>\s*(\d+)\s*\((.*)\)\s*;", txt, re.S)
    if not m:
        raise CFDError(f"could not parse velocity field from {u_file}")
    vecs = re.findall(r"\(([^)]+)\)", m.group(2))
    return [float(v.split()[0]) for v in vecs]


def run_poiseuille_case(
    *,
    height: float = 0.02,
    length: float = 0.1,
    depth: float = 0.01,
    n_cells: int = 40,
    nu: float = 1e-3,
    body_force: float = 0.01,
    end_time: int = 1000,
    foam_bashrc: str = DEFAULT_FOAM_BASHRC,
    keep: bool = False,
) -> tuple[CFDRun, list[float]]:
    """Run a real plane-Poiseuille case through ``blockMesh`` + ``simpleFoam``.

    Returns ``(CFDRun, ux_profile)`` where ``ux_profile`` is the streamwise velocity of
    each cell across the channel height (bottom→top), empty if the solver did not write a
    field. Pure measurement — it makes NO pass/fail decision; that is the validator's job.

    Raises:
        CFDError: OpenFOAM is not available (env file or a binary missing) — the loud,
            fail-fast path. A solver that RUNS but diverges/errors is reported via
            ``CFDRun.ok_process``/``converged``, not by raising.
        ValueError: a non-physical case parameter (non-positive size/viscosity/cells).
    """
    if min(height, length, depth, nu) <= 0.0:
        raise ValueError("height, length, depth and nu must be positive")
    if n_cells < 4:
        raise ValueError("need at least 4 cells across the channel to resolve a parabola")
    if end_time < 1:
        raise ValueError("end_time must be a positive iteration count")
    if not openfoam_available(foam_bashrc):
        raise CFDError(
            f"need env file {foam_bashrc!r} and binaries {BLOCKMESH!r}/{SIMPLEFOAM!r} "
            "on PATH (source OpenFOAM or set $FOAM_BASHRC/$GENESIS_SIMPLEFOAM)")

    tmp = tempfile.mkdtemp(prefix="genesis_cfd_")
    case = Path(tmp)
    try:
        _write_case(case, height=height, length=length, depth=depth, n_cells=n_cells,
                    nu=nu, body_force=body_force, end_time=end_time)
        bm = _run_foam_tool(BLOCKMESH, case, foam_bashrc)
        if bm.returncode != 0:
            return (CFDRun(False, False, bm.returncode, -1, None,
                           tmp if keep else None,
                           (bm.stderr or bm.stdout)[-1500:]), [])
        sf = _run_foam_tool(SIMPLEFOAM, case, foam_bashrc)
        u_resid = _parse_last_u_initial_residual(sf.stdout)
        converged = u_resid is not None and u_resid < U_RESIDUAL_CONVERGED
        if sf.returncode != 0:
            return (CFDRun(False, converged, bm.returncode, sf.returncode, u_resid,
                           tmp if keep else None,
                           (sf.stderr or sf.stdout)[-1500:]), [])

        # The latest written time directory holds the converged field.
        times = sorted((int(d.name) for d in case.iterdir()
                        if d.is_dir() and d.name.isdigit() and d.name != "0"))
        profile: list[float] = []
        if times:
            profile = _parse_u_profile(case / str(times[-1]) / "U")
        return (CFDRun(True, converged, bm.returncode, sf.returncode, u_resid,
                       tmp if keep else None, (sf.stderr or "")[-1500:]), profile)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def poiseuille_channel_check(
    *,
    height: float = 0.02,
    nu: float = 1e-3,
    body_force: float = 0.01,
    n_cells: int = 40,
    end_time: int = 1000,
    rel_tolerance: float = DEFAULT_REL_TOLERANCE,
    foam_bashrc: str = DEFAULT_FOAM_BASHRC,
) -> dict:
    """CFD validator: laminar plane Poiseuille flow vs the analytic closed form.

    Runs a real OpenFOAM case and compares the solver's centreline velocity ``u_max`` and
    full profile against ``u(y) = g/(2ν)·(h² − (y−h)²)`` (``h = H/2``). Mirrors the
    δ-physics validator contract: returns a dict ending in ``"ok": bool``, with a
    ``safety_factor`` = ``rel_tolerance / max_relative_error`` (≥ 1 ⇔ within tolerance).

    Returns ``{"u_max_openfoam", "u_max_analytic", "u_max_rel_error",
    "profile_l2_rel_error", "u_mean_rel_error", "converged", "safety_factor", "ok",
    "detail"}``. ``ok`` is True only if the solver process succeeded, the momentum
    equation converged, AND every relative error is within ``rel_tolerance``. A diverged
    / failed / mismatched run is an honest ``ok=False`` (with the reason in ``detail``),
    never a silent pass.

    Raises:
        CFDError: OpenFOAM unavailable (loud — see :func:`run_poiseuille_case`).
        ValueError: a non-physical parameter or non-positive tolerance.
    """
    if rel_tolerance <= 0.0:
        raise ValueError("rel_tolerance must be positive")

    run, ux = run_poiseuille_case(
        height=height, nu=nu, body_force=body_force, n_cells=n_cells,
        end_time=end_time, foam_bashrc=foam_bashrc)

    h = height / 2.0
    u_max_analytic = body_force * h * h / (2.0 * nu)

    if not run.ok_process or not ux:
        return {
            "u_max_openfoam": None,
            "u_max_analytic": u_max_analytic,
            "u_max_rel_error": None,
            "profile_l2_rel_error": None,
            "u_mean_rel_error": None,
            "converged": run.converged,
            "safety_factor": 0.0,
            "ok": False,
            "detail": (f"solver did not complete (blockMesh rc={run.blockmesh_rc}, "
                       f"simpleFoam rc={run.simplefoam_rc}); {run.stderr_tail[-300:]}"),
        }

    n = len(ux)
    dy = height / n
    # cell-centre y of each cell, bottom→top
    ys = [(i + 0.5) * dy for i in range(n)]
    u_analytic = [body_force / (2.0 * nu) * (h * h - (y - h) ** 2) for y in ys]

    u_max_of = max(ux)
    u_max_rel = abs(u_max_of - u_max_analytic) / u_max_analytic

    num = sum((a - b) ** 2 for a, b in zip(ux, u_analytic)) ** 0.5
    den = sum(b * b for b in u_analytic) ** 0.5
    profile_l2_rel = num / den if den > 0 else float("inf")

    u_mean_of = sum(ux) / n
    u_mean_analytic = (2.0 / 3.0) * u_max_analytic  # exact integral of the parabola
    u_mean_rel = abs(u_mean_of - u_mean_analytic) / u_mean_analytic

    max_err = max(u_max_rel, profile_l2_rel, u_mean_rel)
    safety_factor = rel_tolerance / max_err if max_err > 0 else float("inf")
    ok = run.converged and max_err <= rel_tolerance

    if not run.converged:
        detail = f"solver did not converge (Ux initial residual={run.u_initial_residual})"
    elif not ok:
        detail = (f"OpenFOAM disagrees with analytic Poiseuille: "
                  f"max rel error {max_err:.3%} > tol {rel_tolerance:.3g}")
    else:
        detail = ""

    return {
        "u_max_openfoam": u_max_of,
        "u_max_analytic": u_max_analytic,
        "u_max_rel_error": u_max_rel,
        "profile_l2_rel_error": profile_l2_rel,
        "u_mean_rel_error": u_mean_rel,
        "converged": run.converged,
        "safety_factor": safety_factor,
        "ok": ok,
        "detail": detail,
    }


#: CFD validator registry — same shape as physics_validation.VALIDATORS, but kept SEPARATE
#: (these spawn external solvers and take seconds; the δ-physics registry stays pure/fast).
CFD_VALIDATORS = {
    "poiseuille_channel": poiseuille_channel_check,
}


@dataclass(frozen=True)
class CFDCheck:
    """One declared CFD check: run validator `validator` with keyword `inputs`.

    Mirrors physics_validation.PhysicsCheck. `validator` must key into ``CFD_VALIDATORS``.
    """

    name: str
    validator: str
    inputs: dict = field(default_factory=dict)


def run_cfd_checks(checks: list[CFDCheck]) -> list[dict]:
    """Run every CFD check and return per-check evidence (no pass/fail aggregation here).

    Mirrors physics_validation.run_physics_checks: each result dict carries
    ``{"name","validator","status","ok","detail","result"}`` with status
    "ran" | "unknown" | "error". A validator that raises :class:`CFDError` (no solver) or
    any other exception becomes status "error" — surfaced, never a silent pass.
    """
    out: list[dict] = []
    for check in checks:
        fn = CFD_VALIDATORS.get(check.validator)
        if fn is None:
            out.append({"name": check.name, "validator": check.validator,
                        "status": "unknown", "ok": False,
                        "detail": f"no CFD validator named {check.validator!r}",
                        "result": None})
            continue
        try:
            result = fn(**check.inputs)
        except Exception as exc:  # CFDError, ValueError, … — surface, do not pass
            out.append({"name": check.name, "validator": check.validator,
                        "status": "error", "ok": False,
                        "detail": f"{type(exc).__name__}: {exc}", "result": None})
            continue
        out.append({"name": check.name, "validator": check.validator,
                    "status": "ran", "ok": bool(result.get("ok", False)),
                    "detail": result.get("detail", ""), "result": result})
    return out


def gate_cfd(checks: list[CFDCheck]) -> GateResult:
    """Aggregate declared CFD checks into one GATE CFD verdict (mirrors gate_delta_physics).

    Passes only if EVERY check ran and reported ok. Non-passing checks yield a GateFailure:
    ``CFD_UNKNOWN_VALIDATOR`` (no code for it), ``CFD_CHECK_ERROR`` (validator raised —
    e.g. OpenFOAM missing, un-evaluatable inputs), or ``CFD_CHECK_FAILED`` (ran but the
    solver diverged or disagreed with theory). An empty list passes vacuously, exactly
    like the δ-physics gate on an empty check list.
    """
    failures: list[GateFailure] = []
    for r in run_cfd_checks(checks):
        if r["status"] == "unknown":
            failures.append(GateFailure(code="CFD_UNKNOWN_VALIDATOR",
                                        detail=f"{r['name']}: {r['detail']}"))
        elif r["status"] == "error":
            failures.append(GateFailure(code="CFD_CHECK_ERROR",
                                        detail=f"{r['name']} ({r['validator']}): {r['detail']}"))
        elif not r["ok"]:
            res = r["result"] or {}
            sf = res.get("safety_factor")
            failures.append(GateFailure(
                code="CFD_CHECK_FAILED",
                detail=f"{r['name']} ({r['validator']}): {r['detail']} (safety_factor={sf})"))
    return GateResult(gate="cfd", passed=not failures, failures=failures)


__all__ = [
    "CFDError", "CFDRun", "CFDCheck",
    "openfoam_available", "run_poiseuille_case", "poiseuille_channel_check",
    "CFD_VALIDATORS", "run_cfd_checks", "gate_cfd",
    "DEFAULT_FOAM_BASHRC", "DEFAULT_REL_TOLERANCE",
]
