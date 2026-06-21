"""section_optimizer — a minimum-material geometry PROPOSER behind the structural yield gate.

The generative-design adoption (agent-B), in the honest tractable form: instead of a human hand-
parameterising a part's cross-section, PROPOSE the lightest rectangular section that keeps the bending
stress within the allowable, subject to manufacturability bounds — then let GENESIS's existing
``structural`` / SMT yield gate VERIFY it. This is exactly the proposer/gate split the research stresses:
the optimiser suggests geometry, the deterministic gate disposes; a proposal it returns is a candidate,
never a certified part until the gate re-checks it.

Scope is honest: this sizes a rectangular cantilever section (GENESIS's demo printed part) by
deterministic search over the depth ``h`` — the dominant lever (``σ = 6·F·L/(b·h²) ∝ 1/h²``). Full
density-based topology optimisation (SIMP) over an FEA mesh is the richer next step and needs an
FEA-in-the-gate path; it is deliberately NOT claimed here. Deterministic, offline.
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
    max_aspect: float = 4.0,
    h_steps: int = 400,
) -> SectionDesign:
    """Lightest rectangular section ``(b, h)`` for a tip-loaded cantilever keeping ``6·F·L/(b·h²) ≤
    sigma_allow``, subject to ``b ≥ min_wall``, ``h ≥ min_wall`` and depth/breadth aspect ``h/b ≤
    max_aspect``. Deterministic grid search over the depth; for each depth the minimal feasible breadth
    is ``b = max(required_b, min_wall, h/max_aspect)``. Returns the minimum-volume feasible design (a
    PROPOSAL the structural gate re-verifies)."""
    if force <= 0 or arm <= 0 or sigma_allow <= 0:
        raise ValueError("force, arm and sigma_allow must be positive")
    required_bh2 = 6.0 * force * arm / sigma_allow          # need b·h² ≥ this to keep σ ≤ allowable
    # search depth from the wall up to where even an aspect-limited section comfortably clears the load
    h_lo = min_wall
    h_hi = max(min_wall * 2.0, (required_bh2 * max_aspect) ** (1.0 / 3.0) * 2.0)
    best: SectionDesign | None = None
    for k in range(h_steps + 1):
        h = h_lo + (h_hi - h_lo) * k / h_steps
        if h < min_wall:
            continue
        # smallest breadth that satisfies the stress limit (with a hair of margin), the wall and aspect
        b = max(required_bh2 / (h * h) * (1.0 + 1e-9), min_wall, h / max_aspect)
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
        min_wall=min_wall, max_aspect=max_aspect, h_steps=h_steps,
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
