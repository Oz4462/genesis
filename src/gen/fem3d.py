"""3-D continuum FEM — linear elasticity on 4-node tetrahedra (numpy, no solver dep).

The δ-2 statics layer and the 1-D beam FEM (fem.py) model a beam. The real
continuum stress field — the thing that, at a hole, rises to the Kirsch
concentration the statics layer only bounds conservatively (Kt=3) — needs a 3-D
continuum FEM. This module is one: the constant-strain 4-node tetrahedron of
linear isotropic elasticity, assembled and solved in pure numpy, with a built-in
structured box mesher (each hex cell split into 6 tets). No external solver
(CalculiX/FreeCAD) and no mesher (gmsh) are required.

Verified, not asserted: the constant-strain tetrahedron reproduces a UNIFORM stress
state exactly, so a prismatic bar in axial tension must return σ = F/A to machine
precision on any mesh, with the correct Poisson contraction — the test pins exactly
that.

The "next layer" this docstring used to defer — a conforming mesh of a HOLED part, to
COMPUTE the Kt field itself rather than bound it — is now wired in:
:func:`unstructured_tet_mesh` builds a real gmsh-meshed plate-with-a-hole (refined at
the hole), and :func:`stress_concentration_field` solves it and returns the full
per-tet σ_xx / von-Mises field with Kt DERIVED from that field (peak / far-field), not
hardcoded. :func:`mesh_to_meshio` / :func:`write_mesh` bridge to meshio so the same mesh
is portable to VTK/VTU/Gmsh/Abaqus and viewable in ParaView. (gmsh and meshio are
OPTIONAL: the structured-box path and the solver are pure numpy; the unstructured/IO
helpers lazy-import and fail loud if the package is absent.)

Consistent SI-ish units: pass E and tractions in MPa/N-mm or Pa/N-m consistently;
lengths set the scale. Honest boundary: linear (small-strain, small-displacement)
isotropic elasticity, static — no plasticity, contact, or large deformation.

Wiring (physics validators campaign): core 4-node tet solver + structured_box_mesh for
3D continuum linear elasticity. Used directly by modal.py:41 (internals for stiffness),
plate_hole.py:156 (Kt), bracket_fem.py:102 (capstone). Resonance path to
physics_validation.VALIDATORS["resonance"], physics_selection recipe, pipeline.assess_specification
+ gate_delta_physics. Cross fem3d_quadratic (shared _elasticity_matrix). L3 seam to δ-gate,
structural (Kt bound), HORIZON δ, sim/inventor via modal quantities.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# the 6-tetrahedron (Freudenthal) split of a hex with local corner order
# 0:(0,0,0) 1:(1,0,0) 2:(1,1,0) 3:(0,1,0) 4:(0,0,1) 5:(1,0,1) 6:(1,1,1) 7:(0,1,1)
_HEX_TETS = (
    (0, 1, 3, 7), (0, 1, 7, 5), (0, 5, 7, 4),
    (0, 3, 2, 7), (0, 2, 6, 7), (0, 6, 4, 7),
)
_HEX_CORNERS = (
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
)


def structured_box_mesh(
    lx: float, ly: float, lz: float, nx: int, ny: int, nz: int
) -> tuple[np.ndarray, np.ndarray]:
    """A structured tetrahedral mesh of an ``lx×ly×lz`` box (nx·ny·nz hex cells,
    6 tets each). Returns ``(nodes (Nx3), tets (Mx4))``."""
    xs = np.linspace(0.0, lx, nx + 1)
    ys = np.linspace(0.0, ly, ny + 1)
    zs = np.linspace(0.0, lz, nz + 1)
    nodes = np.array([(x, y, z) for z in zs for y in ys for x in xs], dtype=float)

    def nid(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    tets: list[tuple[int, int, int, int]] = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                corner = [nid(i + dx, j + dy, k + dz) for (dx, dy, dz) in _HEX_CORNERS]
                for t in _HEX_TETS:
                    tets.append((corner[t[0]], corner[t[1]], corner[t[2]], corner[t[3]]))
    return nodes, np.array(tets, dtype=int)


def _elasticity_matrix(e_modulus: float, nu: float) -> np.ndarray:
    """6×6 isotropic elasticity matrix D (Voigt: xx,yy,zz,xy,yz,zx)."""
    lam = e_modulus * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = e_modulus / (2.0 * (1.0 + nu))
    d = np.zeros((6, 6))
    d[:3, :3] = lam
    d[0, 0] = d[1, 1] = d[2, 2] = lam + 2.0 * mu
    d[3, 3] = d[4, 4] = d[5, 5] = mu
    return d


def _tet_b_and_volume(coords: np.ndarray) -> tuple[np.ndarray, float]:
    """Strain-displacement matrix B (6×12) and volume of a 4-node tetrahedron.
    Constant over the element (constant-strain tetrahedron)."""
    m = np.ones((4, 4))
    m[:, 1:] = coords                       # rows [1, x, y, z]
    vol6 = np.linalg.det(m)                 # = 6·V (signed)
    minv = np.linalg.inv(m)
    grads = minv[1:4, :]                    # (3×4): rows dN/dx, dN/dy, dN/dz
    b = np.zeros((6, 12))
    for i in range(4):
        bx, cy, dz = grads[0, i], grads[1, i], grads[2, i]
        col = 3 * i
        b[0, col] = bx
        b[1, col + 1] = cy
        b[2, col + 2] = dz
        b[3, col] = cy
        b[3, col + 1] = bx
        b[4, col + 1] = dz
        b[4, col + 2] = cy
        b[5, col] = dz
        b[5, col + 2] = bx
    return b, abs(vol6) / 6.0


def solve_elasticity(
    nodes: np.ndarray,
    tets: np.ndarray,
    e_modulus: float,
    nu: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Solve K·u = F for a linear-elastic tet mesh.

    `fixed_dofs` and `loads` are keyed by global DOF index (3·node + component,
    component 0/1/2 = x/y/z). Returns ``(displacements (Nx3), element_stresses
    (Mx6))`` in Voigt order. Deterministic.
    """
    n_dof = 3 * len(nodes)
    d = _elasticity_matrix(e_modulus, nu)
    k = np.zeros((n_dof, n_dof))
    b_cache = []
    for tet in tets:
        coords = nodes[tet]
        b, vol = _tet_b_and_volume(coords)
        ke = vol * b.T @ d @ b
        dofs = np.array([3 * n + c for n in tet for c in range(3)])
        k[np.ix_(dofs, dofs)] += ke
        b_cache.append((b, dofs))

    f = np.zeros(n_dof)
    for dof, val in loads.items():
        f[dof] += val
    # Dirichlet BCs by row/col elimination (penalty-free, exact).
    free = np.array([i for i in range(n_dof) if i not in fixed_dofs])
    u = np.zeros(n_dof)
    for dof, val in fixed_dofs.items():
        u[dof] = val
    f_red = f[free] - k[np.ix_(free, np.array(list(fixed_dofs)))] @ np.array(
        list(fixed_dofs.values())
    ) if fixed_dofs else f[free]
    u[free] = np.linalg.solve(k[np.ix_(free, free)], f_red)

    stresses = np.zeros((len(tets), 6))
    for e, (b, dofs) in enumerate(b_cache):
        stresses[e] = d @ b @ u[dofs]
    return u.reshape(-1, 3), stresses


@dataclass(frozen=True)
class PrismaticBarResponse:
    """Axial response of a force-controlled prismatic bar.

    ``axial_stress`` is the volume-mean σ_xx and ``axial_deflection`` is the
    mean x-displacement of the loaded end face. Both are READ OUT of
    ``solve_elasticity`` — they are not canned. They only happen to match the
    closed forms σ = F/A (exact, by equilibrium) and δ ≈ F·L/(A·E) because the
    constant-strain tet reproduces the uniform axial field.
    """

    axial_stress: float
    axial_deflection: float


def prismatic_bar_axial_response(
    length: float,
    width: float,
    height: float,
    e_modulus: float,
    nu: float,
    force: float,
    nx: int = 6,
    ny: int = 2,
    nz: int = 2,
) -> PrismaticBarResponse:
    """Drive a parametric axial-tension case through :func:`solve_elasticity`.

    Builds a ``length×width×height`` prismatic bar, locks the symmetry faces
    (ux on x=0, uy on y=0, uz on z=0), spreads ``force`` evenly over the
    ``x=length`` end-face nodes, solves, and returns the mean axial stress and
    the mean end-face axial deflection.

    This is the single driver behind the scaling-law characterization: because
    σ_xx and u_x emerge from the solver as functions of ``force`` and the
    geometry, a test that pins σ ∝ F/A and δ ∝ F·L/(A·E) proves the FEM
    genuinely consumes load and geometry rather than returning constants.

    Cross-section area A = width·height. Raises ``ValueError`` on a non-positive
    dimension/modulus or a Poisson ratio outside (-1, 0.5) — either would make
    the elasticity matrix or the mesh degenerate and yield a silent wrong value
    instead of failing loud (no silent defaults on factual outputs).
    """
    if min(length, width, height, e_modulus) <= 0.0:
        raise ValueError("length, width, height and e_modulus must be > 0")
    # nu = 0.5 makes (1 - 2nu) = 0 → the Lamé constant diverges (incompressible
    # limit); nu <= -1 makes the shear/bulk moduli non-physical. Guard both.
    if not -1.0 < nu < 0.5:
        raise ValueError("nu must satisfy -1 < nu < 0.5 for a valid isotropic D")

    nodes, tets = structured_box_mesh(length, width, height, nx, ny, nz)
    fixed: dict[int, float] = {}
    for n, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-9:
            fixed[3 * n] = 0.0          # x=0 face: ux = 0
        if abs(y) < 1e-9:
            fixed[3 * n + 1] = 0.0      # y=0 face: uy = 0
        if abs(z) < 1e-9:
            fixed[3 * n + 2] = 0.0      # z=0 face: uz = 0

    end = [n for n, (x, y, z) in enumerate(nodes) if abs(x - length) < 1e-9]
    loads = {3 * n: force / len(end) for n in end}
    u, sig = solve_elasticity(nodes, tets, e_modulus, nu, fixed, loads)
    return PrismaticBarResponse(
        axial_stress=float(sig[:, 0].mean()),
        axial_deflection=float(u[end, 0].mean()),
    )


def von_mises(stress6: np.ndarray) -> float:
    """Von-Mises equivalent stress from a Voigt stress vector (xx,yy,zz,xy,yz,zx)."""
    sx, sy, sz, txy, tyz, tzx = stress6
    return float(
        np.sqrt(
            0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
            + 3.0 * (txy ** 2 + tyz ** 2 + tzx ** 2)
        )
    )


# --- Unstructured (gmsh) meshing of a holed part + meshio I/O ----------------------
#
# These close the "next layer" the module docstring used to defer: a CONFORMING
# unstructured mesh of a holed part, so the stress concentration is COMPUTED from the
# field instead of bounded by a constant. gmsh/meshio are optional; both fail loud.

from .core.errors import GeometryError  # noqa: E402  (kept local to the optional block)


def _require_gmsh():
    """Lazy gmsh import, with the loud no-mesher message (CLAUDE.md: no silent default)."""
    try:
        import gmsh  # type: ignore
    except ImportError as exc:  # pragma: no cover - only without gmsh
        raise GeometryError(
            "the unstructured tetrahedral mesher needs the optional 'gmsh' package; "
            "install it with `pip install gmsh`, or use structured_box_mesh (no hole) "
            "with the conservative Kt=3 statics bound."
        ) from exc
    return gmsh


def unstructured_tet_mesh(
    *,
    length: float = 20.0,
    width: float = 20.0,
    thickness: float = 1.0,
    hole_radius: float = 2.0,
    refine_size: float = 0.6,
    coarse_size: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """A REAL unstructured linear-tet mesh of a FULL plate with a centered through-hole.

    Unlike :func:`structured_box_mesh` (a regular hex-split grid of a solid box, which
    cannot represent a hole), this cuts a cylindrical hole out of the plate with the
    OCCT kernel inside gmsh and meshes the result with tetrahedra REFINED near the hole
    (a Box size field of edge ``refine_size`` within ~3·radius of the hole axis, coarse
    ``coarse_size`` elsewhere). The full (not quarter-symmetry) plate is meshed so the
    field around the whole hole is available; the hole is centered at (length/2, width/2).

    Returns ``(nodes (N×3), tets (M×4))`` with 0-based connectivity, ready for
    :func:`solve_elasticity`. Deterministic (gmsh ``RandomSeed=1``).

    Raises:
        GeometryError: gmsh is not installed (loud), or the geometry is degenerate
            (hole not strictly inside the plate, or a non-positive dimension) — a
            degenerate mesh would yield a silent wrong field instead of failing.
    """
    if min(length, width, thickness, hole_radius, refine_size, coarse_size) <= 0.0:
        raise GeometryError("all plate/mesh dimensions must be > 0")
    if 2.0 * hole_radius >= min(length, width):
        raise GeometryError(
            f"hole diameter {2 * hole_radius} must be smaller than the plate "
            f"(length {length}, width {width}) — the hole must lie strictly inside"
        )
    gmsh = _require_gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.RandomSeed", 1)
        gmsh.model.add("holed_plate")
        cx, cy = length / 2.0, width / 2.0
        box = gmsh.model.occ.addBox(0, 0, 0, length, width, thickness)
        cyl = gmsh.model.occ.addCylinder(cx, cy, -1.0, 0, 0, thickness + 2.0, hole_radius)
        gmsh.model.occ.cut([(3, box)], [(3, cyl)])
        gmsh.model.occ.synchronize()
        field = gmsh.model.mesh.field.add("Box")
        gmsh.model.mesh.field.setNumber(field, "VIn", refine_size)
        gmsh.model.mesh.field.setNumber(field, "VOut", coarse_size)
        gmsh.model.mesh.field.setNumber(field, "XMin", cx - 3.0 * hole_radius)
        gmsh.model.mesh.field.setNumber(field, "XMax", cx + 3.0 * hole_radius)
        gmsh.model.mesh.field.setNumber(field, "YMin", cy - 3.0 * hole_radius)
        gmsh.model.mesh.field.setNumber(field, "YMax", cy + 3.0 * hole_radius)
        gmsh.model.mesh.field.setNumber(field, "ZMin", -1.0)
        gmsh.model.mesh.field.setNumber(field, "ZMax", thickness + 1.0)
        gmsh.model.mesh.field.setAsBackgroundMesh(field)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.model.mesh.generate(3)
        ntags, ncoords, _ = gmsh.model.mesh.getNodes()
        nodes = np.array(ncoords).reshape(-1, 3)
        index = {int(tag): i for i, tag in enumerate(ntags)}
        _, _, conn = gmsh.model.mesh.getElements(dim=3)
        if not conn or len(conn[0]) == 0:
            raise GeometryError("gmsh produced no volume tetrahedra for the holed plate")
        tets = np.array([index[int(t)] for t in conn[0]]).reshape(-1, 4)
        return nodes, tets
    finally:
        gmsh.finalize()


def mesh_to_meshio(nodes: np.ndarray, tets: np.ndarray, *,
                   point_data: dict | None = None, cell_data: dict | None = None):
    """Wrap a ``(nodes, tets)`` mesh (optionally with fields) as a ``meshio.Mesh``.

    ``point_data`` maps a name to an ``(N,...)`` array, ``cell_data`` a name to an
    ``(M,...)`` array — e.g. the per-tet von-Mises field from
    :func:`stress_concentration_field`. Lets the same mesh GENESIS solved on be written
    to any meshio format (VTU/VTK/Gmsh/Abaqus) and viewed in ParaView.

    Raises GeometryError if meshio is not installed (loud).
    """
    try:
        import meshio  # type: ignore
    except ImportError as exc:  # pragma: no cover - only without meshio
        raise GeometryError(
            "exporting/importing FEM meshes needs the optional 'meshio' package; "
            "install it with `pip install meshio`."
        ) from exc
    cells = [("tetra", np.asarray(tets, dtype=int))]
    cd = None
    if cell_data:
        # meshio cell_data is keyed by name -> list (one array per cell block).
        cd = {k: [np.asarray(v)] for k, v in cell_data.items()}
    return meshio.Mesh(
        points=np.asarray(nodes, dtype=float),
        cells=cells,
        point_data={k: np.asarray(v) for k, v in (point_data or {}).items()} or None,
        cell_data=cd,
    )


def write_mesh(path: str, nodes: np.ndarray, tets: np.ndarray, *,
               point_data: dict | None = None, cell_data: dict | None = None) -> str:
    """Write the mesh (and any attached fields) to ``path`` via meshio; return ``path``.

    The format is inferred from the extension (e.g. ``.vtu`` for ParaView, ``.msh`` for
    Gmsh). Raises GeometryError if meshio is absent.
    """
    mesh = mesh_to_meshio(nodes, tets, point_data=point_data, cell_data=cell_data)
    mesh.write(path)
    return path


@dataclass(frozen=True)
class StressConcentrationField:
    """The COMPUTED stress-concentration result of a holed plate in tension.

    Every number is READ OUT of the solved field — none is a Kirsch constant.
    ``kt`` is the gross stress-concentration factor = peak σ_xx at the hole edge
    divided by the far-field σ_xx away from the hole, so it is the actual concentration
    the §9 statics layer only bounds at 3.0.
    """

    kt: float                      #: peak σ_xx / far-field σ_xx — derived from the field
    peak_sxx: float                #: max tensile σ_xx anywhere (at the hole edge)
    far_field_sxx: float           #: mean σ_xx in the far region (x > 0.8·length)
    peak_von_mises: float          #: max von-Mises equivalent stress
    n_tets: int                    #: number of elements in the unstructured mesh
    sxx: np.ndarray                #: per-tet σ_xx field (M,)
    von_mises_field: np.ndarray    #: per-tet von-Mises field (M,)


def stress_concentration_field(
    *,
    length: float = 20.0,
    width: float = 20.0,
    thickness: float = 1.0,
    hole_radius: float = 2.0,
    e_modulus: float = 210000.0,
    nu: float = 0.3,
    far_strain: float = 1e-3,
    refine_size: float = 0.6,
    coarse_size: float = 3.0,
) -> StressConcentrationField:
    """Mesh a holed plate, pull it in tension, and COMPUTE the stress-concentration field.

    The full plate (not quarter-symmetry) is meshed with :func:`unstructured_tet_mesh`,
    the x=0 face is clamped in x (and one corner pinned in y/z to remove rigid-body
    modes), and the x=length face is displaced by ``far_strain·length`` to impose a
    uniform far-field tension of σ_far ≈ E·far_strain. The solver returns the real
    σ field; this reads the PEAK σ_xx at the hole edge and the FAR-FIELD σ_xx, and
    reports Kt = peak/far — derived from the field, never the hardcoded Kt=3.

    For a finite plate with d/W ≈ 0.2 the computed gross Kt sits near 3 (the Kirsch
    infinite-plate value, sharpened a little by the finite-width correction). The full
    per-tet σ_xx and von-Mises arrays are returned so the field can be exported
    (:func:`write_mesh`) and inspected, not just its peak.

    Raises GeometryError (degenerate geometry / no gmsh) or ValueError (bad ν).
    """
    if not -1.0 < nu < 0.5:
        raise ValueError("nu must satisfy -1 < nu < 0.5 for a valid isotropic D")
    nodes, tets = unstructured_tet_mesh(
        length=length, width=width, thickness=thickness, hole_radius=hole_radius,
        refine_size=refine_size, coarse_size=coarse_size,
    )
    delta = length * far_strain
    fixed: dict[int, float] = {}
    # x=0 face clamped in x; x=length face displaced +delta in x (uniform tension).
    for n, (x, y, z) in enumerate(nodes):
        if abs(x) < 1e-6:
            fixed[3 * n] = 0.0
        if abs(x - length) < 1e-6:
            fixed[3 * n] = delta
    # remove the two remaining rigid-body modes (y, z translation) by pinning the
    # single x=0 node closest to the origin in y and z — a statically admissible,
    # non-redundant restraint that does not load the field.
    x0 = [n for n, (x, y, z) in enumerate(nodes) if abs(x) < 1e-6]
    anchor = min(x0, key=lambda n: nodes[n][1] ** 2 + nodes[n][2] ** 2)
    fixed[3 * anchor + 1] = 0.0
    fixed[3 * anchor + 2] = 0.0

    _, stresses = solve_elasticity(nodes, tets, e_modulus, nu, fixed, {})
    sxx = stresses[:, 0]
    vm = np.array([von_mises(s) for s in stresses])
    centroids = np.array([nodes[te].mean(axis=0) for te in tets])
    far = float(sxx[centroids[:, 0] > 0.8 * length].mean())
    peak = float(sxx.max())
    return StressConcentrationField(
        kt=peak / far,
        peak_sxx=peak,
        far_field_sxx=far,
        peak_von_mises=float(vm.max()),
        n_tets=len(tets),
        sxx=sxx,
        von_mises_field=vm,
    )
