"""CalculiX (ccx) FEM bridge — an INDEPENDENT second-opinion linear-elastic solver.

GENESIS has its own in-house tetrahedral FEM (``fem3d`` / ``fem3d_quadratic``, pure numpy).
A second, independently-implemented solver is a real cross-check: if CalculiX — a mature,
widely-used open-source FEM solver — reproduces the in-house displacement field on the SAME
mesh and boundary conditions, that is strong evidence the in-house solver is right (the same
"cross-model verification" idea CLAUDE.md §3 applies to facts, applied to a physics solve).

On this machine CalculiX (``ccx`` 2.23) is bundled inside the FreeCAD flatpak at
``/app/bin/ccx`` (there is no standalone host binary). So this is a SUBPROCESS bridge through
``flatpak run --command=ccx org.freecad.FreeCAD``. The crucial constraint is the flatpak
sandbox: its filesystem is private, so the whole job (write the ``.inp`` deck, run ccx, read
the ``.dat`` result) runs in ONE ``sh -c`` inside a sandbox-internal ``mktemp -d``, and the
result text is piped back over STDOUT — never relying on host ``/tmp`` ↔ sandbox ``/tmp``
being shared (they are not).

HONEST boundary: this is the clean, useful path (raw ccx as a cross-check). Driving the
FreeCAD FEM *workbench object model* headlessly is deliberately NOT attempted — it is
heavyweight and sandbox-path-fragile with no capability gain over raw ccx (see the module
test's docstring for the documented reasoning).

Failure is LOUD and typed (``GenesisError``): flatpak/FreeCAD/ccx missing, a non-zero ccx
exit, or a result that cannot be parsed — all surface, never a fabricated displacement.
Linear isotropic elasticity, static, C3D4 (linear tet) — matching ``fem3d.solve_elasticity``.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import numpy as np

from ..core.errors import GenesisError

#: The FreeCAD flatpak application id (verified on this box: v1.1.1, ccx 2.23 bundled).
_FLATPAK_APP = "org.freecad.FreeCAD"

#: ccx inside the flatpak sandbox.
_CCX_IN_SANDBOX = "/app/bin/ccx"

#: Generous default timeout (s) for a small ccx solve incl. flatpak spin-up.
_DEFAULT_TIMEOUT = 180.0


def flatpak_available() -> bool:
    """True iff the ``flatpak`` CLI is on PATH (necessary but not sufficient)."""
    return shutil.which("flatpak") is not None


def calculix_available() -> bool:
    """True iff the FreeCAD flatpak (which bundles ccx) is installed.

    Mirrors ``cad_available`` / ``openfoam_available`` so the integration tests skip-guard
    cleanly. Probes ``flatpak info <app>``; a False is a definitive 'no ccx here'. It does
    NOT prove ccx runs — the first real :func:`solve_displacements` does that, loudly.
    """
    if not flatpak_available():
        return False
    try:
        proc = subprocess.run(
            ["flatpak", "info", _FLATPAK_APP],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0
    except Exception:
        return False


def build_inp_deck(
    nodes: np.ndarray,
    tets: np.ndarray,
    e_modulus: float,
    nu: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
) -> str:
    """Emit a CalculiX ``.inp`` deck for a linear-elastic C3D4 tet model.

    Same problem statement as :func:`gen.fem3d.solve_elasticity`: ``fixed_dofs`` and
    ``loads`` are keyed by global DOF index (3·node + component, 0/1/2 = x/y/z). CalculiX
    node/element ids are 1-based, so node ``n`` (0-based) becomes ``n+1`` and DOF component
    ``c`` (0/1/2) becomes ccx direction ``c+1``.

    Only homogeneous (zero) Dirichlet constraints are written as ``*BOUNDARY``; a non-zero
    prescribed displacement is written as a boundary with its value (ccx supports that). A
    point load goes in ``*CLOAD``. The deck requests ``*NODE PRINT, U`` so displacements
    land in the ``.dat`` text file this bridge parses.

    Raises GenesisError on an empty mesh (nothing to solve) — never an empty deck.
    """
    nodes = np.asarray(nodes, dtype=float)
    tets = np.asarray(tets, dtype=int)
    if len(nodes) == 0 or len(tets) == 0:
        raise GenesisError("cannot build a CalculiX deck from an empty mesh")
    if tets.shape[1] != 4:
        raise GenesisError(
            f"CalculiX C3D4 needs 4-node tets; got {tets.shape[1]}-node elements"
        )

    lines: list[str] = ["*NODE, NSET=Nall"]
    for i, (x, y, z) in enumerate(nodes, start=1):
        lines.append(f"{i}, {x:.9e}, {y:.9e}, {z:.9e}")
    lines.append("*ELEMENT, TYPE=C3D4, ELSET=Eall")
    for e, tet in enumerate(tets, start=1):
        a0, b0, c0, d0 = (int(t) for t in tet)
        # CalculiX C3D4 requires a POSITIVE Jacobian (specific node winding); a mesher's
        # own tet orientation may be either sign. Compute the signed volume and, if it is
        # negative, swap the last two nodes to flip the orientation — otherwise ccx aborts
        # with "nonpositive jacobian determinant". (This is geometry bookkeeping, not a
        # fabricated value: it only re-labels node order, the element is unchanged.)
        p0, p1, p2, p3 = nodes[a0], nodes[b0], nodes[c0], nodes[d0]
        signed6 = float(np.dot(np.cross(p1 - p0, p2 - p0), p3 - p0))
        if signed6 < 0.0:
            c0, d0 = d0, c0
        lines.append(f"{e}, {a0 + 1}, {b0 + 1}, {c0 + 1}, {d0 + 1}")
    lines.append("*MATERIAL, NAME=MAT")
    lines.append("*ELASTIC")
    lines.append(f"{e_modulus:.9e}, {nu:.9e}")
    lines.append("*SOLID SECTION, ELSET=Eall, MATERIAL=MAT")

    # Dirichlet BCs: group by value so identical-value rows are compact; ccx wants
    # node, first_dir, last_dir [, value].
    if fixed_dofs:
        lines.append("*BOUNDARY")
        for dof, val in sorted(fixed_dofs.items()):
            node = dof // 3 + 1
            comp = dof % 3 + 1
            if abs(val) < 1e-300:
                lines.append(f"{node}, {comp}, {comp}")
            else:
                lines.append(f"{node}, {comp}, {comp}, {val:.9e}")

    lines.append("*STEP")
    lines.append("*STATIC")
    if loads:
        lines.append("*CLOAD")
        for dof, val in sorted(loads.items()):
            node = dof // 3 + 1
            comp = dof % 3 + 1
            lines.append(f"{node}, {comp}, {val:.9e}")
    lines.append("*NODE PRINT, NSET=Nall")
    lines.append("U")
    lines.append("*END STEP")
    return "\n".join(lines) + "\n"


def _parse_dat_displacements(dat_text: str, n_nodes: int) -> np.ndarray:
    """Parse the ``displacements`` block of a ccx ``.dat`` into an (n_nodes, 3) array.

    The ccx ``.dat`` lists, after a ``displacements (vx,vy,vz) ...`` header, one line per
    node: ``<node_id> <ux> <uy> <uz>``. Raises GenesisError if the block is missing or the
    node count does not match (a silently-truncated field would be worse than failing).
    """
    lines = dat_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "displacements" in ln.lower():
            start = i + 1
            break
    if start is None:
        raise GenesisError(
            f"no 'displacements' block in the CalculiX .dat output (got {len(dat_text)} "
            f"chars); the solve may have failed"
        )
    u = np.zeros((n_nodes, 3))
    seen = 0
    for ln in lines[start:]:
        parts = ln.split()
        if len(parts) < 4:
            if seen > 0:
                break  # the block ended
            continue
        try:
            nid = int(parts[0])
            ux, uy, uz = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            if seen > 0:
                break
            continue
        if 1 <= nid <= n_nodes:
            u[nid - 1] = (ux, uy, uz)
            seen += 1
    if seen != n_nodes:
        raise GenesisError(
            f"CalculiX .dat had {seen} displacement rows but the mesh has {n_nodes} nodes "
            f"— refusing a partially-parsed field"
        )
    return u


@dataclass(frozen=True)
class CalculixResult:
    """Displacement field from a CalculiX solve (read out of the .dat, not asserted)."""

    displacements: np.ndarray   #: (N, 3) nodal displacement field
    n_nodes: int
    n_tets: int


def solve_displacements(
    nodes: np.ndarray,
    tets: np.ndarray,
    e_modulus: float,
    nu: float,
    fixed_dofs: dict[int, float],
    loads: dict[int, float],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> CalculixResult:
    """Solve a linear-elastic C3D4 model with CalculiX and return the displacement field.

    Builds the ``.inp`` deck (:func:`build_inp_deck`), then runs the ENTIRE job inside the
    flatpak sandbox in a single ``sh -c`` (write deck → ``ccx`` → ``cat`` the ``.dat`` to
    stdout) within a sandbox-internal ``mktemp -d``, so nothing depends on host/sandbox
    filesystem sharing. Parses the displacements from stdout.

    Returns a :class:`CalculixResult` whose ``displacements`` is the SAME shape as
    ``fem3d.solve_elasticity``'s first return, so the two solvers can be compared directly.

    Raises:
        GenesisError: flatpak/FreeCAD/ccx unavailable, ccx exits non-zero, or the ``.dat``
            cannot be parsed (loud — never a fabricated field).
    """
    if not flatpak_available():
        raise GenesisError(
            "the CalculiX bridge needs 'flatpak' on PATH (CalculiX ccx is bundled in the "
            "FreeCAD flatpak on this machine); install flatpak + the FreeCAD flatpak, or "
            "use the in-house fem3d solver."
        )
    if not calculix_available():
        raise GenesisError(
            f"the FreeCAD flatpak ({_FLATPAK_APP}, which bundles ccx) is not installed; "
            f"`flatpak install {_FLATPAK_APP}`, or use the in-house fem3d solver."
        )
    deck = build_inp_deck(nodes, tets, e_modulus, nu, fixed_dofs, loads)
    n_nodes = len(nodes)

    # One sandbox-internal job: heredoc the deck, run ccx, emit the .dat between markers.
    # ccx is invoked WITHOUT the .inp extension (ccx -i job expects job.inp).
    script = (
        'set -e\n'
        'D=$(mktemp -d)\n'
        'cd "$D"\n'
        "cat > job.inp <<'GENESIS_EOF'\n"
        f"{deck}"
        "GENESIS_EOF\n"
        f'{_CCX_IN_SANDBOX} -i job > ccx.log 2>&1\n'
        'echo "GENESIS_CCX_RC=$?"\n'
        'echo "GENESIS_DAT_BEGIN"\n'
        'cat job.dat 2>/dev/null || true\n'
        'echo "GENESIS_DAT_END"\n'
        'rm -rf "$D"\n'
    )
    try:
        proc = subprocess.run(
            ["flatpak", "run", "--command=sh", _FLATPAK_APP, "-c", script],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GenesisError(f"CalculiX (flatpak) timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise GenesisError(
            f"the flatpak CalculiX wrapper exited {proc.returncode}: "
            f"{proc.stderr.strip()[:400] or proc.stdout.strip()[:400]}"
        )
    out = proc.stdout
    # check ccx's own exit code (carried in the marker)
    ccx_rc = None
    for ln in out.splitlines():
        if ln.startswith("GENESIS_CCX_RC="):
            ccx_rc = ln.split("=", 1)[1].strip()
            break
    if ccx_rc not in ("0", None):
        raise GenesisError(
            f"CalculiX ccx exited {ccx_rc}; the model did not solve "
            f"(stdout tail: {out[-400:]!r})"
        )
    if "GENESIS_DAT_BEGIN" not in out or "GENESIS_DAT_END" not in out:
        raise GenesisError(
            f"CalculiX produced no parseable .dat output (stdout: {out[-400:]!r})"
        )
    dat = out.split("GENESIS_DAT_BEGIN", 1)[1].split("GENESIS_DAT_END", 1)[0]
    u = _parse_dat_displacements(dat, n_nodes)
    return CalculixResult(displacements=u, n_nodes=n_nodes, n_tets=len(tets))


__all__ = [
    "flatpak_available",
    "calculix_available",
    "build_inp_deck",
    "solve_displacements",
    "CalculixResult",
]
