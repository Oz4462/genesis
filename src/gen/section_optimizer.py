"""section_optimizer — a minimum-material geometry PROPOSER behind the structural yield gate.

The generative-design adoption (agent-B), in the honest tractable form: instead of a human hand-
parameterising a part's cross-section, PROPOSE the lightest rectangular section that keeps the bending
stress within the allowable, subject to manufacturability bounds — then let GENESIS's existing
``structural`` / SMT yield gate VERIFY it. This is exactly the proposer/gate split the research stresses:
the optimiser suggests geometry, the deterministic gate disposes; a proposal it returns is a candidate,
never a certified part until the gate re-checks it.

Scope is honest: this sizes a rectangular cantilever section (GENESIS's demo printed part) by
deterministic search over the depth ``h`` — the dominant lever (``σ = 6·F·L/(b·h²) ∝ 1/h²``). 

Full density-based topology optimisation (SIMP) over an FEA mesh (fem3d structured hex) is now the
richer next step, implemented in topology_optimizer.py as a DENSITY-FIELD PROPOSAL (verdict="vorschlag_unverifiziert").
It re-uses the same trusted fem3d kernels and guards. Use threshold_resolve + printability/mesh gates for
the δ path to certification. The simple rectangular case here remains the minimal tractable form.
Deterministic, offline. See topology_optimizer for SIMP details, constants (with sources), and the delta_path.
"""

from __future__ import annotations

from dataclasses import dataclass

from .materials import Material, get_material
from .verification.cegis import cantilever_yield_check
from .verification.smt import prove_cantilever_within_yield


@dataclass(frozen=True)
class SectionDesign:
    """A proposed rectangular section: its dimensions, the bending stress it achieves, a material proxy
    (volume = b·h·L), and the safety factor against the allowable. ``feasible`` is False when no design
    within the bounds meets the stress limit."""

    breadth: float
    depth: float
    stress: float
    volume: float
    safety_factor: float
    feasible: bool


def optimize_cantilever_section(
    *,
    force: float,
    arm: float,
    sigma_allow: float,
    min_wall: float = 1.0,
    max_wall: float = float("inf"),
    max_aspect: float = 4.0,
    h_steps: int = 400,
) -> SectionDesign:
    """Lightest rectangular section ``(b, h)`` for a tip-loaded cantilever keeping ``6·F·L/(b·h²) ≤
    sigma_allow``, subject to ``min_wall ≤ b, h ≤ max_wall`` and depth/breadth aspect ``h/b ≤
    max_aspect``. Deterministic grid search over the depth; for each depth the minimal feasible breadth
    is ``b = max(required_b, min_wall, h/max_aspect)``. Returns the minimum-volume feasible design (a
    PROPOSAL the structural gate re-verifies).

    ``max_wall`` is the largest section dimension the process can build (build-volume / max wall bound);
    it defaults to ``inf`` (unbounded). When no ``(b, h)`` within ``[min_wall, max_wall]`` keeps the
    stress within ``sigma_allow`` — an over-constrained load — the search finds nothing and the result
    is the honest ``feasible=False`` abstention (``stress=inf``), never a fabricated section. Without an
    upper bound the breadth could always grow to absorb any load, so this abstention path is only
    genuinely reachable once ``max_wall`` is finite (CLAUDE.md §4: honest abstention)."""
    if force <= 0 or arm <= 0 or sigma_allow <= 0:
        raise ValueError("force, arm and sigma_allow must be positive")
    required_bh2 = 6.0 * force * arm / sigma_allow          # need b·h² ≥ this to keep σ ≤ allowable
    # search depth from the wall up to where even an aspect-limited section comfortably clears the load,
    # but never deeper than the build bound — beyond max_wall the depth is unbuildable.
    h_lo = min_wall
    h_hi = min(max(min_wall * 2.0, (required_bh2 * max_aspect) ** (1.0 / 3.0) * 2.0), max_wall)
    best: SectionDesign | None = None
    for k in range(h_steps + 1):
        h = h_lo + (h_hi - h_lo) * k / h_steps
        if h < min_wall or h > max_wall:
            continue
        # smallest breadth that satisfies the stress limit (with a hair of margin), the wall and aspect
        b = max(required_bh2 / (h * h) * (1.0 + 1e-9), min_wall, h / max_aspect)
        if b > max_wall:                                   # section too wide to build within the bound
            continue
        if h / b > max_aspect + 1e-9:
            continue
        stress = 6.0 * force * arm / (b * h * h)
        if stress > sigma_allow:
            continue
        volume = b * h * arm
        if best is None or volume < best.volume:
            best = SectionDesign(
                breadth=b, depth=h, stress=stress, volume=volume,
                safety_factor=sigma_allow / stress, feasible=True,
            )
    if best is None:
        return SectionDesign(min_wall, min_wall, float("inf"), float("inf"), 0.0, False)
    return best


@dataclass(frozen=True)
class VerifiedSection:
    """A material-grounded section PROPOSAL together with an INDEPENDENT gate verdict.

    ``gate_passed`` is the closed-form yield gate (``verification.cegis.cantilever_yield_check``) re-
    checking that the proposed ``(b, h)`` actually satisfies ``σ ≤ σ_allow`` — a path separate from the
    optimiser's own accept/reject, so an optimiser search/margin bug surfaces here. ``machine_proved`` is
    the z3 ∀-proof (``verification.smt``) clearing the same bound via a representation-independent
    polynomial rewrite; it is ``False`` (not a pass) when z3 is unavailable. The optimiser proposes, the
    gate disposes — a section is certified only when the gate agrees (CLAUDE.md §1/§2)."""

    material: Material
    sigma_allow: float
    design: SectionDesign
    gate_passed: bool
    machine_proved: bool
    detail: str


def propose_and_verify(
    *,
    material_name: str,
    force: float,
    arm: float,
    safety_factor: float = 1.0,
    min_wall: float = 1.0,
    max_wall: float = float("inf"),
    max_aspect: float = 4.0,
    h_steps: int = 400,
) -> VerifiedSection:
    """Propose the lightest cantilever section for a load and a GROUNDED material, then verify it.

    ``sigma_allow`` is the material's yield strength (a sourced fact via ``materials.get_material``)
    divided by ``safety_factor`` — never an anonymous constant. The proposed section is then re-checked
    by an INDEPENDENT closed-form yield gate and, when z3 is present, machine-proved. The optimiser's own
    ``feasible`` flag is NOT trusted as the verdict: ``gate_passed`` comes from the separate gate.

    Raises ``ValueError`` for an unknown material (via ``get_material``), a non-positive
    ``safety_factor``, or non-positive ``force``/``arm`` (via ``optimize_cantilever_section``).
    """
    if safety_factor <= 0:
        raise ValueError("safety_factor must be positive")
    material = get_material(material_name)            # raises on an unknown material — no guessed property
    sigma_allow = material.yield_strength_mpa / safety_factor
    design = optimize_cantilever_section(
        force=force, arm=arm, sigma_allow=sigma_allow,
        min_wall=min_wall, max_wall=max_wall, max_aspect=max_aspect, h_steps=h_steps,
    )
    if not design.feasible:
        return VerifiedSection(
            material, sigma_allow, design, gate_passed=False, machine_proved=False,
            detail=f"no section within bounds keeps σ ≤ {sigma_allow:.4g} MPa for {material.name}",
        )
    # INDEPENDENT verification: the gate, not the optimiser, decides whether the proposal is certified.
    counterexample = cantilever_yield_check(
        {"F": force, "L": arm, "b": design.breadth, "h": design.depth}, sigma_allow
    )
    gate_passed = counterexample is None
    proof = prove_cantilever_within_yield(
        force=force, arm=arm, breadth=design.breadth, depth=design.depth, sigma_allow=sigma_allow
    )
    machine_proved = proof.available and proof.proved
    detail = (
        f"{material.name}: σ={design.stress:.4g} ≤ {sigma_allow:.4g} MPa, SF={design.safety_factor:.3g}; "
        + ("gate PASS" if gate_passed else f"gate FAIL ({counterexample.detail if counterexample else ''})")
        + ("; z3 proved" if machine_proved else ("; z3 unavailable" if not proof.available else "; z3 refuted"))
    )
    return VerifiedSection(material, sigma_allow, design, gate_passed, machine_proved, detail)


# --- SIMP topology integration (richer generative step) ---------------------------------------------
# The "full FEA-in-the-gate path" declared above is now wired via topology_optimizer.
# Re-export for discoverability and provide a convenience for the classic cantilever benchmark.
# The result is always an explicit PROPOSAL; the independent gate (threshold + fem3d re-solve + printability)
# decides certification. This makes topology first-class in the structural design flow.

from .topology_optimizer import (
    simp_optimize,
    TopologyProposal,
    cantilever_tip_load_bcs,
    threshold_resolve,
    ThresholdCheck,
)
from .fem3d import structured_box_mesh


@dataclass(frozen=True)
class StructuralProposal:
    """Unified honest proposal surface for structural generative design.

    `design_type`: "section" (rectangular) or "topology" (SIMP density field).
    `verdict`: always "vorschlag_unverifiziert" (or "nicht_optimiert") until independent gates.
    `delta_path`: explicit next steps for certification.
    `payload`: the raw proposal object (SectionDesign/VerifiedSection or TopologyProposal/ThresholdCheck).
    Preserves the proposer/gate split. Immutable.
    """
    design_type: str
    verdict: str
    delta_path: str
    payload: object


def propose_structural(*, design_type: str = "section", **kwargs) -> StructuralProposal:
    """Unified dispatcher for structural proposals.

    Delegates to the appropriate optimizer. Result is always a proposal;
    callers must run the named delta_path gates (cegis/smt + printability for section;
    threshold_resolve + printability/mesh_integrity for topology) before any certified claim.
    """
    if design_type == "section":
        # delegate to existing (use the grounded propose_and_verify when material provided)
        if "material_name" in kwargs:
            vs = propose_and_verify(**kwargs)
            # Gate-passed means the proposer cleared its internal yield/proof
            # checks — still a PROPOSAL until printability/mesh gates re-verify.
            # Gate-failed is NOT a silent "unverified proposal": surface as
            # nicht_optimiert so consumers cannot read success from the verdict.
            return StructuralProposal(
                design_type="section",
                verdict=(
                    "vorschlag_unverifiziert" if vs.gate_passed else "nicht_optimiert"
                ),
                delta_path="structural yield gate (cegis + smt) + printability/mesh_integrity",
                payload=vs,
            )
        else:
            design = optimize_cantilever_section(**kwargs)
            return StructuralProposal(
                design_type="section",
                verdict="vorschlag_unverifiziert" if design.feasible else "nicht_optimiert",
                delta_path="structural yield gate (cegis + smt) + printability",
                payload=design,
            )
    elif design_type in ("topology", "simp"):
        prop = propose_topology_cantilever(**kwargs)
        return StructuralProposal(
            design_type="topology",
            verdict=prop.verdict,
            delta_path=prop.delta_path,
            payload=prop,
        )
    else:
        raise ValueError(f"unknown design_type {design_type!r}; use 'section' or 'topology'")


def propose_topology_cantilever(
    *,
    lx: float = 2.0,
    ly: float = 1.0,
    lz: float = 0.2,
    nx: int = 20,
    ny: int = 10,
    nz: int = 2,
    force: float = 1.0,
    volume_fraction: float = 0.4,
    e_modulus: float = 1.0,
    nu: float = 0.3,
    **opt_kwargs,
) -> TopologyProposal:
    """Convenience: run SIMP topology optimization on a 3D cantilever benchmark.

    Returns a TopologyProposal (density field + measured compliance factors).
    This is the richer next step beyond rectangular section optimization.
    Always a proposal — call threshold_resolve on the densities for the interpolation-free proof,
    then apply geometry gates before claiming a part.

    All parameters and guards inherited from topology_optimizer.simp_optimize (fail-loud, deterministic).
    """
    nodes, _tets = structured_box_mesh(lx, ly, lz, nx, ny, nz)
    fixed, loads = cantilever_tip_load_bcs(nodes, lx, force)
    return simp_optimize(
        lx=lx,
        ly=ly,
        lz=lz,
        nx=nx,
        ny=ny,
        nz=nz,
        e_modulus=e_modulus,
        nu=nu,
        volume_fraction=volume_fraction,
        fixed_dofs=fixed,
        loads=loads,
        **opt_kwargs,
    )
