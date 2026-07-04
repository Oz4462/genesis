"""Human-in-the-loop ratification — the AI suggests, the human decides (research #5).

SOTA for trustworthy AI ("the AI suggests; the human decides — nothing irreversible without
sign-off"; Architect-in-the-Loop, where oversight begins at the SPECIFICATION level) makes a
human the gatekeeper of consequence. GENESIS already structures the right surfaces — Decisions
are explicitly human-ratifiable design choices and gaps are honest residual risk — but nothing
forces a sign-off. This module adds it: it assembles a ratification PACKET from a spec (the
decisions to ratify, the gaps to acknowledge, the gate verdicts as evidence) and decides
"done" ONLY against an explicit human sign-off.

The non-negotiable rule (matching the Agent-SDK guidance: never fake approval with hidden
auto-allow): nothing is approved by default. A blocking item — every Decision, every gap, and
any FAILED gate — must be EXPLICITLY in the sign-off, or the spec is not ratified. So the
system surfaces exactly what needs human judgement and refuses to call the work done until a
human actually exercised it. The real UI / identity / audit record is the deployment layer;
this is the deterministic, offline core of the contract. Pure functions, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from .core.interfaces import GateResult
from .core.state import Specification


@dataclass(frozen=True)
class RatificationItem:
    """One thing a human must sign off on (or acknowledge).

    `kind`     "decision" | "gap" | "gate".
    `ref`      a stable reference key used to match a sign-off.
    `summary`  the human-readable content being ratified.
    `blocking` True if "done" requires this item to be explicitly approved (every
               Decision and gap blocks; a FAILED gate blocks; a PASSED gate is
               non-blocking evidence).
    """

    kind: str
    ref: str
    summary: str
    blocking: bool


@dataclass(frozen=True)
class SignOff:
    """The explicit human approval. `approved` holds the refs the human ratified; nothing
    is approved that is not listed here (no default approval). `approver` is the identity,
    carried for the audit record (the real identity binding is the deployment layer)."""

    approved: frozenset[str] = frozenset()
    approver: str = ""

    def __post_init__(self) -> None:
        # Coerce to a frozenset so the approval set cannot be mutated AFTER the sign-off was
        # made: a mutable set passed in would otherwise let approvals grow without a new sign-off.
        if not isinstance(self.approved, frozenset):
            object.__setattr__(self, "approved", frozenset(self.approved))


def ratification_packet(
    spec: Specification, gate_results: dict[str, GateResult] | None = None
) -> list[RatificationItem]:
    """Assemble the items a human must ratify before the spec is "done": every Decision
    (a design choice), every gap (residual risk to acknowledge), and each gate verdict
    (evidence; a FAILED gate blocks). Deterministic, order-stable. Raises ValueError on a
    None gate result — a placeholder verdict has no honest blocking/non-blocking reading
    (a gate that did not run must be omitted, not passed as None)."""
    for name, result in (gate_results or {}).items():
        if result is None:
            raise ValueError(
                f"gate result {name!r} is None — omit a gate that did not run, "
                "a None verdict cannot be ratified")
    items: list[RatificationItem] = []
    seen: set[str] = set()
    for i, d in enumerate(sorted(spec.decisions, key=lambda x: x.id)):  # order-stable
        ref = f"decision:{d.id}"                         # namespaced -> never collides with gap:/gate:
        if ref in seen:                                  # a duplicate id gets a distinct ref so one
            ref = f"decision:{d.id}#{i}"                 # sign-off cannot silently ratify the sibling
        seen.add(ref)
        items.append(RatificationItem(
            "decision", ref, f"{d.title}: Wahl {d.choice!r} — {d.rationale}", True))
    for i, gap in enumerate(spec.gaps):
        items.append(RatificationItem("gap", f"gap:{i}", gap, True))
    for name, result in sorted((gate_results or {}).items()):
        verdict = "PASS" if result.passed else "FAIL"
        items.append(RatificationItem(
            "gate", f"gate:{name}",
            f"{name}: {verdict} ({len(result.failures)} Abweichungen)",
            blocking=not result.passed))
    return items


def unratified_items(packet: list[RatificationItem], signoff: SignOff) -> list[RatificationItem]:
    """The blocking items the human has NOT yet explicitly approved — what still stands
    between the spec and "done"."""
    return [it for it in packet if it.blocking and it.ref not in signoff.approved]


def is_ratified(packet: list[RatificationItem], signoff: SignOff) -> bool:
    """True only if a NAMED human approver has explicitly signed off EVERY blocking item. An
    empty sign-off, an anonymous one (no `approver`), or even an empty packet with no approver
    is NOT "done" — nothing is approved by default and no approval is anonymous."""
    return bool(signoff.approver.strip()) and not unratified_items(packet, signoff)
