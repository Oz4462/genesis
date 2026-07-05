"""topology_optimizer — SIMP density-field PROPOSER on the fem3d structured box mesh.

The section optimizer (section_optimizer.py) sizes ONE rectangular section — the
honest tractable form of generative design. This module is the declared "richer
next step": classic density-based topology optimisation (SIMP — Solid Isotropic
Material with Penalisation, Bendsøe 1989; Bendsøe & Sigmund, *Topology
Optimization*, 2003) over the SAME structured tet mesh and solver kernels the
δ FEM layer already trusts (fem3d.py). One density variable per hex cell,
modified-SIMP stiffness interpolation E(ρ) = E_min + ρ^p·(E0 − E_min),
compliance objective, volume constraint, Optimality-Criteria update and
Sigmund's sensitivity filter against checkerboarding — the exact scheme of the
canonical 88/99-line references (Sigmund 2001; Andreassen et al. 2011 "top88").

HONEST BOUNDARY — the result is a DENSITY-FIELD PROPOSAL, NOT a verified part:
``TopologyProposal.verdict`` is ``"vorschlag_unverifiziert"`` and stays that
way inside this module. The δ path to a certified design is named in
``delta_path``: threshold the field, RE-SOLVE the binary design against the
same FEM (``threshold_resolve`` below gives that second, interpolation-free
proof), then run the geometry through the printability/mesh-integrity gates
before any claim. "Optimiert" is never asserted without the measured
compliance factor against the equal-volume uniform baseline.

Deterministic (no randomness anywhere), pure numpy, offline. Fail-loud: input
validation and the finite-solution guard are REUSED from fem3d (same functions
modal.py / fem3d_quadratic.py import — the step-7d isfinite hardening is
inherited, not bypassed), and every intermediate (compliance, sensitivities,
densities) is isfinite-checked per iteration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core.errors import GeometryError
from .fem3d import (
    _check_material_and_bcs,
    _check_solution_finite,
    _elasticity_matrix,
    _tet_b_and_volume,
    structured_box_mesh,
)

# --- named constants (sources in comments; no anonymous magic numbers) ---------------------------

#: SIMP penalisation exponent p. p=3 is the standard choice: it satisfies the
#: Hashin–Shtrikman bound argument for ν≈1/3 and is the value used throughout
#: Bendsøe & Sigmund (2003) and the 99/88-line codes (Sigmund 2001, Andreassen 2011).
SIMP_PENALTY = 3.0

#: Void stiffness ratio E_min/E0 of the *modified* SIMP interpolation
#: E(ρ) = E_min + ρ^p·(E0−E_min). 1e-9 is the top88 value: small enough not to
#: carry load, large enough to keep K non-singular for fully void cells.
E_MIN_RATIO = 1e-9

#: Optimality-Criteria move limit m: a density may change at most this much per
#: iteration (stabilises the fixed-point iteration; top88 uses 0.2).
OC_MOVE_LIMIT = 0.2

#: Optimality-Criteria damping exponent η = 1/2 (the classic ρ·(B_e)^η update;
#: Bendsøe & Sigmund 2003, eq. (2.7); top88).
OC_DAMPING = 0.5

#: Sensitivity-filter radius in units of the hex-cell size. 1.5 cells is the
#: canonical top88 choice: the smallest radius that couples every cell to its
#: face neighbours (distance 1 < 1.5) and thereby breaks the checkerboard mode
#: (alternating cells are decoupled in the CST/hex stiffness but coupled by the
#: filter), while blurring the design as little as possible. Radius ≤ 1 keeps
#: only the self-weight → filtering effectively OFF (used by the negative test).
DEFAULT_FILTER_RADIUS_CELLS = 1.5

#: Density floor used ONLY in the filter denominator (Sigmund 1997 filter is
#: dĉ_e = Σ w·ρ·dc / (max(ρ_e, floor)·Σ w)); prevents division blow-up for
#: near-void cells. Same 1e-3 as top88.
SENSITIVITY_DENSITY_FLOOR = 1e-3

#: Relative width at which the OC Lagrange-multiplier bisection stops (top88: 1e-3
#: on (l2-l1)/(l1+l2); we use a tighter 1e-4 so the volume constraint is met to
#: ~1e-4 in density mean).
OC_BISECTION_RTOL = 1e-4

#: Hard fail-loud bound: after every OC update the mean density must sit within
#: this distance of the target volume fraction, or the run aborts (the volume
#: constraint is a constraint, not a suggestion).
VOLUME_CONSTRAINT_TOL = 1e-3

_TETS_PER_HEX = 6  # structured_box_mesh splits every hex cell into 6 tets


# --- results --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyProposal:
    """A SIMP density field with its measured evidence — explicitly UNVERIFIED.

    ``densities`` is (nx, ny, nz), one value in [0, 1] per hex cell of the
    structured mesh. All compliances are MEASURED under the identical mesh/BCs,
    and each factor compares like with like:

    * ``improvement_factor = compliance_start / compliance`` — start (uniform
      ρ ≡ volume_fraction) vs final field, BOTH under the SIMP interpolation:
      the optimisation gain within its own model. Exactly 1.0 when nothing ran.
    * ``compliance_uniform_linear`` — the equal-volume uniform field at LINEAR
      stiffness ρ·E0, i.e. the Voigt bound: no real uniform material at this
      volume fraction can be stiffer. The cross-model proof against it lives in
      ``threshold_resolve`` (binary design vs this baseline), not here — the
      grey SIMP field itself may honestly LOSE against Voigt.

    ``volume_history`` records the mean density after every OC update (the
    constraint audit trail). ``verdict`` is ``"vorschlag_unverifiziert"`` (or
    ``"nicht_optimiert"`` when the iteration budget was 0 — the field is then
    just the uniform start, honestly labelled); ``delta_path`` names what must
    happen before any certified claim."""

    densities: np.ndarray
    compliance: float
    compliance_start: float
    compliance_uniform_linear: float
    improvement_factor: float
    volume_fraction: float
    achieved_volume_fraction: float
    iterations: int
    converged: bool
    compliance_history: tuple[float, ...]
    volume_history: tuple[float, ...]
    verdict: str
    delta_path: str


@dataclass(frozen=True)
class ThresholdCheck:
    """The second, interpolation-free proof: the density field thresholded to a
    BINARY solid/void design at the SAME volume fraction, freshly re-solved.

    ``compliance_binary`` comes from a solve where kept cells have full
    stiffness and void cells E_min — no ρ^p interpolation, so a SIMP artefact
    that only 'helps' through grey material would be exposed here. ``passed``
    is True iff the binary design is stiffer (lower compliance) than the
    equal-volume uniform baseline. Still NOT a certified part: printability /
    mesh-integrity gates remain (see ``note``)."""

    compliance_binary: float
    compliance_uniform: float
    improvement_factor: float
    kept_fraction: float
    passed: bool
    note: str


_DELTA_PATH = (
    "δ-Pfad bis zur Zertifizierung: (1) threshold_resolve — binäres Design bei gleichem "
    "Volumen frisch lösen (zweiter Beweis, ohne SIMP-Interpolation); (2) Geometrie aus dem "
    "Schwellwert-Feld durch printability/mesh_integrity-Gates; erst ein Gate-PASS macht "
    "aus dem Vorschlag ein Bauteil."
)


# --- FEM kernel (element cache + scaled assembly, reusing fem3d guards) ---------------------------


class _ElementCache:
    """Per-element stiffness (at full modulus E0) and DOF maps, computed ONCE.

    SIMP re-solves the same mesh dozens of times with only per-element scale
    factors changing; caching ke0 keeps each iteration to an assembly + solve."""

    def __init__(self, nodes: np.ndarray, tets: np.ndarray, e_modulus: float, nu: float):
        d = _elasticity_matrix(e_modulus, nu)
        self.n_dof = 3 * len(nodes)
        self.ke0: list[np.ndarray] = []
        self.dofs: list[np.ndarray] = []
        for tet in tets:
            b, vol = _tet_b_and_volume(nodes[tet])
            self.ke0.append(vol * b.T @ d @ b)
            self.dofs.append(np.array([3 * n + c for n in tet for c in range(3)]))


def _assemble_and_solve(
    cache: _ElementCache,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
    tet_scale: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Assemble K = Σ s_e·ke0_e, solve K·u = F, return (compliance, per-tet
    unit-scale strain energies u_eᵀ·ke0_e·u_e).

    Homogeneous Dirichlet only (u = 0 on fixed DOFs): compliance c = fᵀu then
    equals the total strain energy ·2, the standard SIMP objective. Non-zero
    prescribed displacements would change the objective's meaning and are
    rejected fail-loud. Non-finite scales are rejected; a non-finite solution
    raises GeometryError via fem3d's guard (step-7d hardening, inherited)."""
    if not np.all(np.isfinite(tet_scale)) or np.any(tet_scale <= 0.0):
        raise ValueError("element stiffness scales must be finite and positive")
    for dof, val in fixed_dofs.items():
        if val != 0.0:
            raise ValueError(
                f"fixed_dofs[{dof}]={val!r}: topology optimisation supports only "
                "homogeneous (zero) prescribed displacements"
            )
    k = np.zeros((cache.n_dof, cache.n_dof))
    for s, ke0, dofs in zip(tet_scale, cache.ke0, cache.dofs):
        k[np.ix_(dofs, dofs)] += s * ke0
    f = np.zeros(cache.n_dof)
    for dof, val in loads.items():
        f[dof] += val
    free = np.array([i for i in range(cache.n_dof) if i not in fixed_dofs])
    u = np.zeros(cache.n_dof)
    u[free] = np.linalg.solve(k[np.ix_(free, free)], f[free])
    _check_solution_finite(u)
    compliance = float(f @ u)
    energies = np.array([float(u[dofs] @ ke0 @ u[dofs]) for ke0, dofs in zip(cache.ke0, cache.dofs)])
    if not np.isfinite(compliance) or not np.all(np.isfinite(energies)):
        raise GeometryError("non-finite compliance/strain energy — ill-posed SIMP state")
    return compliance, energies


def _cell_energies(tet_energies: np.ndarray, n_cells: int) -> np.ndarray:
    """Sum the 6 tet strain energies of each hex cell (structured mesh order:
    tets t belong to cell t // 6)."""
    return tet_energies.reshape(n_cells, _TETS_PER_HEX).sum(axis=1)


def _filter_matrix(nx: int, ny: int, nz: int, radius_cells: float) -> tuple[np.ndarray, np.ndarray]:
    """Sigmund's linear ('cone') sensitivity-filter weights over hex-cell centres.

    Returns dense (n, n) weights w_ij = max(0, r − dist_ij) (distance in cell
    units) and their row sums. Dense is deliberate: the design grids here are
    small (hundreds of cells) and dense keeps it dependency-free and exact."""
    ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
    centers = np.stack([ii.ravel(order="C"), jj.ravel(order="C"), kk.ravel(order="C")], axis=1).astype(float)
    dist = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    w = np.maximum(0.0, radius_cells - dist)
    return w, w.sum(axis=1)


def _cell_index_order(nx: int, ny: int, nz: int) -> np.ndarray:
    """Map flat design-variable index (C-order over (nx, ny, nz), as produced by
    ``densities.ravel(order="C")`` with ij-indexing) to the hex-cell index used
    by structured_box_mesh (k-major, then j, then i)."""
    order = np.empty(nx * ny * nz, dtype=int)
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                mesh_cell = k * ny * nx + j * nx + i
                flat = (i * ny + j) * nz + k
                order[flat] = mesh_cell
    return order


# --- the optimiser --------------------------------------------------------------------------------


def simp_optimize(
    *,
    lx: float,
    ly: float,
    lz: float,
    nx: int,
    ny: int,
    nz: int,
    e_modulus: float,
    nu: float,
    volume_fraction: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
    penalty: float = SIMP_PENALTY,
    filter_radius_cells: float = DEFAULT_FILTER_RADIUS_CELLS,
    max_iterations: int = 60,
    change_tol: float = 0.01,
    move_limit: float = OC_MOVE_LIMIT,
) -> TopologyProposal:
    """SIMP compliance minimisation under a volume constraint — returns an
    UNVERIFIED density-field proposal (see module docstring for the honesty
    contract and ``delta_path`` for what certification still requires).

    Mesh/BC convention is exactly fem3d's: ``structured_box_mesh(lx, ly, lz,
    nx, ny, nz)``, DOFs keyed 3·node+component. ``volume_fraction`` ∈ (0, 1) is
    the allowed material fraction; the OC update holds the mean density on it
    (audited in ``volume_history``, hard-checked to VOLUME_CONSTRAINT_TOL).
    Deterministic: no randomness, fixed iteration order.

    Raises ValueError on invalid material/BC/load values (fem3d's shared guard),
    a non-positive/NaN volume fraction, penalty < 1, or a non-zero prescribed
    displacement; raises GeometryError when a solve or an intermediate quantity
    goes non-finite (never returns NaN silently).
    """
    _check_material_and_bcs(e_modulus, nu, fixed_dofs, loads)
    if not np.isfinite(volume_fraction) or not (0.0 < volume_fraction < 1.0):
        raise ValueError(f"volume_fraction must be in (0, 1), got {volume_fraction!r}")
    if not np.isfinite(penalty) or penalty < 1.0:
        raise ValueError(f"penalty must be finite and >= 1 (no reward for grey), got {penalty!r}")
    if max_iterations < 0:
        raise ValueError(f"max_iterations must be >= 0, got {max_iterations!r}")
    if nx < 1 or ny < 1 or nz < 1:
        raise ValueError("nx, ny, nz must be >= 1")
    if not loads:
        raise ValueError("loads must not be empty — compliance of an unloaded body is trivially 0")

    nodes, tets = structured_box_mesh(lx, ly, lz, nx, ny, nz)
    cache = _ElementCache(nodes, tets, e_modulus, nu)
    n_cells = nx * ny * nz
    to_mesh = _cell_index_order(nx, ny, nz)          # flat design index -> mesh cell index
    w_filter, w_sums = _filter_matrix(nx, ny, nz, filter_radius_cells)

    def tet_scales(rho_flat: np.ndarray) -> np.ndarray:
        cell_scale_mesh = np.empty(n_cells)
        cell_scale_mesh[to_mesh] = E_MIN_RATIO + rho_flat ** penalty * (1.0 - E_MIN_RATIO)
        return np.repeat(cell_scale_mesh, _TETS_PER_HEX)

    rho = np.full(n_cells, volume_fraction)           # flat, C-order over (nx, ny, nz)
    # Voigt reference: equal-volume uniform field at LINEAR stiffness ρ·E0 (see
    # TopologyProposal docstring — the cross-model bar threshold_resolve must clear)
    uniform_scale = np.full(len(tets), volume_fraction)
    compliance_uniform_linear, _ = _assemble_and_solve(cache, fixed_dofs, loads, uniform_scale)
    # the optimisation start state, evaluated with the SIMP interpolation itself
    compliance_start, energies = _assemble_and_solve(cache, fixed_dofs, loads, tet_scales(rho))
    compliance = compliance_start

    compliance_history: list[float] = []
    volume_history: list[float] = []
    converged = False
    iterations = 0
    for _ in range(max_iterations):
        # sensitivities of compliance wrt design densities (chain rule through E(ρ)):
        # dc/dρ_e = −p·ρ^(p−1)·(1−E_min/E0)·u_eᵀ·ke0_e·u_e  (≤ 0)
        cell_e_mesh = _cell_energies(energies, n_cells)
        cell_e = cell_e_mesh[to_mesh]
        dc = -penalty * rho ** (penalty - 1.0) * (1.0 - E_MIN_RATIO) * cell_e
        dc = np.minimum(dc, 0.0)                      # numerics guard: compliance sens. is never positive
        # Sigmund sensitivity filter (mesh-independency, kills checkerboards)
        dc_hat = (w_filter @ (rho * dc)) / (np.maximum(rho, SENSITIVITY_DENSITY_FLOOR) * w_sums)
        if not np.all(np.isfinite(dc_hat)):
            raise GeometryError("non-finite filtered sensitivities — aborting SIMP")
        # Optimality-Criteria update with bisection on the volume multiplier λ
        lo, hi = 1e-9, 1e9
        rho_new = rho
        while (hi - lo) / (hi + lo) > OC_BISECTION_RTOL:
            lam = 0.5 * (lo + hi)
            candidate = rho * np.abs(dc_hat / lam) ** OC_DAMPING
            rho_new = np.clip(
                candidate,
                np.maximum(0.0, rho - move_limit),
                np.minimum(1.0, rho + move_limit),
            )
            if rho_new.mean() > volume_fraction:
                lo = lam
            else:
                hi = lam
        if not np.all(np.isfinite(rho_new)):
            raise GeometryError("non-finite densities after OC update — aborting SIMP")
        vol = float(rho_new.mean())
        if abs(vol - volume_fraction) > VOLUME_CONSTRAINT_TOL:
            raise GeometryError(
                f"volume constraint violated after OC update: mean density {vol:.6f} "
                f"vs target {volume_fraction:.6f} (tol {VOLUME_CONSTRAINT_TOL})"
            )
        change = float(np.max(np.abs(rho_new - rho)))
        rho = rho_new
        compliance, energies = _assemble_and_solve(cache, fixed_dofs, loads, tet_scales(rho))
        compliance_history.append(compliance)
        volume_history.append(vol)
        iterations += 1
        if change < change_tol:
            converged = True
            break

    densities = rho.reshape(nx, ny, nz)
    if iterations == 0:
        verdict = "nicht_optimiert"                   # honest: budget 0 → the field is the uniform start
    else:
        verdict = "vorschlag_unverifiziert"
    return TopologyProposal(
        densities=densities,
        compliance=compliance,
        compliance_start=compliance_start,
        compliance_uniform_linear=compliance_uniform_linear,
        improvement_factor=compliance_start / compliance,
        volume_fraction=volume_fraction,
        achieved_volume_fraction=float(rho.mean()),
        iterations=iterations,
        converged=converged,
        compliance_history=tuple(compliance_history),
        volume_history=tuple(volume_history),
        verdict=verdict,
        delta_path=_DELTA_PATH,
    )


def threshold_resolve(
    *,
    densities: np.ndarray,
    lx: float,
    ly: float,
    lz: float,
    e_modulus: float,
    nu: float,
    volume_fraction: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
) -> ThresholdCheck:
    """Second, independent proof: threshold the density field to a BINARY design
    keeping exactly the ``volume_fraction`` stiffest-ranked cells, re-solve it
    fresh (kept cells at full E0, void cells at E_min — no ρ^p interpolation),
    and compare against the equal-volume uniform baseline solved the same way.

    'Independent' here means independent of the SIMP interpolation and of the
    optimiser's own bookkeeping — same trusted FEM kernel, new solve. Threshold
    selection by stable ranking (ties resolved deterministically), so the kept
    volume matches the target exactly (equal-volume comparison, no advantage).

    Raises ValueError/GeometryError under the same fail-loud contract as
    ``simp_optimize``. NOT a printability/mesh-integrity verdict — see ``note``.
    """
    _check_material_and_bcs(e_modulus, nu, fixed_dofs, loads)
    if not np.isfinite(volume_fraction) or not (0.0 < volume_fraction < 1.0):
        raise ValueError(f"volume_fraction must be in (0, 1), got {volume_fraction!r}")
    if densities.ndim != 3:
        raise ValueError(f"densities must be (nx, ny, nz), got shape {densities.shape}")
    if not np.all(np.isfinite(densities)):
        raise ValueError("densities must be finite")
    nx, ny, nz = densities.shape
    n_cells = nx * ny * nz
    n_keep = int(round(volume_fraction * n_cells))
    if n_keep < 1:
        raise ValueError("volume_fraction keeps zero cells — nothing to solve")

    nodes, tets = structured_box_mesh(lx, ly, lz, nx, ny, nz)
    cache = _ElementCache(nodes, tets, e_modulus, nu)
    to_mesh = _cell_index_order(nx, ny, nz)
    rho_flat = densities.ravel(order="C")
    keep = np.zeros(n_cells, dtype=bool)
    keep[np.argsort(-rho_flat, kind="stable")[:n_keep]] = True

    def scales(cell_scale_flat: np.ndarray) -> np.ndarray:
        mesh_scale = np.empty(n_cells)
        mesh_scale[to_mesh] = cell_scale_flat
        return np.repeat(mesh_scale, _TETS_PER_HEX)

    binary = np.where(keep, 1.0, E_MIN_RATIO)
    # uniform baseline uses linear (un-penalised) stiffness ρ·E0: the honest,
    # conservative equal-volume reference — penalising the baseline (ρ^p·E0)
    # would make it artificially soft and flatter the design by ~1/ρ².
    uniform = np.full(n_cells, volume_fraction)
    compliance_binary, _ = _assemble_and_solve(cache, fixed_dofs, loads, scales(binary))
    compliance_uniform, _ = _assemble_and_solve(cache, fixed_dofs, loads, scales(uniform))
    return ThresholdCheck(
        compliance_binary=compliance_binary,
        compliance_uniform=compliance_uniform,
        improvement_factor=compliance_uniform / compliance_binary,
        kept_fraction=n_keep / n_cells,
        passed=compliance_binary < compliance_uniform,
        note=(
            "binäres Design bei gleichem Volumen frisch gelöst — bestätigt/widerlegt den "
            "SIMP-Vorschlag, ersetzt aber NICHT die printability/mesh_integrity-Gates."
        ),
    )


# --- canonical benchmark BCs ----------------------------------------------------------------------


def cantilever_tip_load_bcs(
    nodes: np.ndarray, lx: float, force: float
) -> tuple[dict[int, float], dict[int, float]]:
    """The classic SIMP cantilever benchmark: clamp the x=0 face (all DOFs),
    pull the bottom edge of the free face (x=lx, y=0) downward with total
    ``force`` split equally over its nodes. Returns ``(fixed_dofs, loads)``
    in fem3d DOF convention. Raises ValueError if no load nodes exist."""
    fixed: dict[int, float] = {}
    tip: list[int] = []
    for n, (x, y, _z) in enumerate(nodes):
        if abs(x) < 1e-9:
            fixed[3 * n] = 0.0
            fixed[3 * n + 1] = 0.0
            fixed[3 * n + 2] = 0.0
        if abs(x - lx) < 1e-9 and abs(y) < 1e-9:
            tip.append(n)
    if not tip:
        raise ValueError("no nodes found on the loaded edge (x=lx, y=0)")
    loads = {3 * n + 1: -force / len(tip) for n in tip}
    return fixed, loads


def checkerboard_index(densities: np.ndarray) -> float:
    """Mean absolute density jump across face-adjacent hex cells — a measurable
    proxy for checkerboarding (the alternating 0/1 pattern maximises it, a
    smooth field minimises it). Used by the filter negative test: the metric
    must be measurably smaller WITH the sensitivity filter than without.

    Raises ValueError on a non-3D or non-finite field."""
    if densities.ndim != 3:
        raise ValueError(f"densities must be (nx, ny, nz), got shape {densities.shape}")
    if not np.all(np.isfinite(densities)):
        raise ValueError("densities must be finite")
    jumps: list[np.ndarray] = []
    for axis in range(3):
        if densities.shape[axis] > 1:
            d = np.abs(np.diff(densities, axis=axis))
            jumps.append(d.ravel())
    if not jumps:
        return 0.0
    return float(np.concatenate(jumps).mean())
