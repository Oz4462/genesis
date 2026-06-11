"""`architect` — Phase γ: structure verified claims + a grounded approach into a
complete, actionable Specification.

Like `conductor` and `synthesizer`, the architect INVENTS NOTHING. The LLM only
proposes STRUCTURE — which quantities exist, which formulas derive which values,
what the geometry/BOM/steps look like — and then this CODE enforces the five
Zwänge (PHASE_GAMMA.md §0) before anything reaches the state:

  * GROUNDED quantities must reference existing VERIFIED claims AND the value
    must appear literally in a grounding claim's text (the γ analogue of
    `scholar`'s verbatim-quote guard) — otherwise the quantity is dropped.
  * DERIVED values are COMPUTED HERE from the proposed formula. A value the LLM
    "precomputed" is ignored and overwritten: the LLM never does math.
  * DECISION quantities/Decisions without a rationale are hidden decisions and
    are dropped.
  * The assembled candidate is self-checked against GATE γ (the same pure
    function the conductor uses). If the structure is defective — dangling
    reference, incomplete step, unbuildable order, broken geometry — the
    architect emits NO partial specification: it abstains with a named gap. A
    half build plan is more dangerous than none.

See docs/agents/architect.md and PHASE_GAMMA.md §4.
"""

from __future__ import annotations

import re

from ..core.errors import GenesisError, LLMOutputError, UnitError
from ..core.state import (
    Approach,
    BomItem,
    BomRole,
    Claim,
    ClaimStatus,
    Component,
    Constraint,
    Decision,
    Derivation,
    GeometryNode,
    Quantity,
    RunState,
    Specification,
    Step,
    ValueOrigin,
)
from ..llm.base import LLMClient
from ..llm.parsing import extract_json
from ..verification.derivation import DEFAULT_TOLERANCE, topological_values
from ..verification.gates import gate_gamma, value_in_text
from ..verification.units import formula_dimension, parse_unit

_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_SYSTEM = (
    "You structure VERIFIED factual claims and one GROUNDED solution approach into "
    "a complete build SPECIFICATION for the IDEA. Rules: (1) use ONLY the given "
    "claims, never outside knowledge; (2) a quantity with origin 'grounded' must "
    "reference claim ids by EXACT id, and its value must appear literally in the "
    "claim text, in the source's own unit; (3) any converted or computed value has "
    "origin 'derived': provide formula and inputs ONLY — never compute the value "
    "yourself; (4) every design choice has origin 'decision' (numeric) or is a "
    "decision entry (non-numeric), always with a rationale — a choice is never a "
    "fact; (5) geometry params reference quantity ids, never raw numbers; "
    "(6) every step needs an action, a human-verifiable check, and inputs that are "
    "BOM items or outputs of earlier steps; (7) ids must be identifier-safe "
    "([A-Za-z_][A-Za-z0-9_]*). Return ONE JSON object: "
    '{"approach_id":"...","quantities":[{"id","name","unit","origin",'
    '"value","grounding","formula","inputs","rationale"}],'
    '"components":[{"id","name","quantity_ids","geometry":{"kind","params",'
    '"children"}}],"bom":[{"id","name","role","count","component_id","grounding"}],'
    '"steps":[{"id","index","action","uses","inputs","outputs","check",'
    '"quantity_refs"}],"constraints":[{"id","kind","left","right","reason"}],'
    '"decisions":[{"id","title","choice","rationale","informed_by"}]}'
)


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _as_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class Architect:
    """Satisfies the ``Agent`` Protocol. Writes only ``state.specification``.

    Produces no facts of its own; every grounded value is anchored in existing
    VERIFIED claims, every derived value is computed by code, every choice is a
    declared decision. Rebuilds ``state.specification`` from scratch on each
    call so it is idempotent across the conductor's refine rounds.
    """

    name = "architect"

    def __init__(
        self,
        llm: LLMClient,
        *,
        confidence_threshold: float = 0.7,
        derivation_tolerance: float = DEFAULT_TOLERANCE,
    ) -> None:
        self._llm = llm
        self._tau = confidence_threshold
        self._tol = derivation_tolerance

    async def run(self, state: RunState) -> RunState:
        rid = state.question.run_id
        idea = state.question.raw
        verified = {
            c.id: c
            for c in state.claims
            if c.status is ClaimStatus.VERIFIED and c.confidence >= self._tau
        }
        anchors = [
            ap
            for ap in state.approaches
            if ap.grounding and all(cid in verified for cid in ap.grounding)
        ]

        if not anchors:
            state.specification = self._abstain(
                rid, idea, "No grounded approach available to anchor a specification."
            )
            state.log.append("architect: no grounded approach -> abstain")
            return state

        try:
            proposal = await self._propose(idea, anchors, verified)
        except LLMOutputError as exc:
            state.specification = self._abstain(
                rid, idea, "Architect proposal was unparseable; nothing asserted."
            )
            state.log.append(f"architect: unparseable LLM output -> abstain: {exc}")
            return state

        candidate = self._assemble(rid, idea, proposal, anchors, verified, state)

        # Self-check against the very gate the conductor will run (defense in
        # depth, and a single source of truth for what "structurally sound"
        # means). A defective structure is never partially asserted.
        probe = RunState(question=state.question)
        probe.claims = state.claims
        probe.approaches = state.approaches
        probe.specification = candidate
        result = gate_gamma(
            probe,
            confidence_threshold=self._tau,
            derivation_tolerance=self._tol,
        )
        if result.passed:
            state.specification = candidate
            state.log.append(
                f"architect: specification assembled "
                f"(quantities={len(candidate.quantities)} "
                f"components={len(candidate.components)} steps={len(candidate.steps)})"
            )
        else:
            details = [f"{f.code}: {f.detail}" for f in result.failures]
            for d in details:
                state.log.append(f"architect: self-check failure -> {d}")
            state.specification = self._abstain(
                rid,
                idea,
                "Proposal had structural defects and was not asserted: "
                + " | ".join(details[:5]),
            )
        return state

    # --- internals -------------------------------------------------------------

    @staticmethod
    def _dimensionally_sound(qid, unit, derivation, unit_of, log) -> bool:
        """True if the derivation is dimensionally homogeneous and its formula's
        dimension matches the declared unit. Drops (returns False) + logs
        otherwise — a dimensionally inconsistent value never leaves the architect
        (the Mars-Climate-Orbiter guard; GATE γ C-15 backstops independently)."""
        try:
            input_dims = {iid: parse_unit(unit_of[iid]) for iid in derivation.inputs}
            computed = formula_dimension(derivation.formula, input_dims)
            declared = parse_unit(unit)
        except (UnitError, KeyError) as exc:
            log(f"architect: drop derived {qid!r} (dimension error): {exc}")
            return False
        if computed != declared:
            log(
                f"architect: drop derived {qid!r} — formula is {computed.render()} "
                f"but unit {unit!r} is {declared.render()}"
            )
            return False
        return True

    @staticmethod
    def _abstain(run_id: str, idea: str, reason: str) -> Specification:
        return Specification(run_id=run_id, idea=idea, gaps=[reason])

    async def _propose(
        self, idea: str, anchors: list[Approach], verified: dict[str, Claim]
    ) -> dict:
        approach_lines = "\n".join(
            f"{ap.id}: {ap.name} (grounding: {', '.join(ap.grounding)})"
            for ap in anchors
        )
        claim_lines = "\n".join(f"{cid}: {c.text}" for cid, c in verified.items())
        user = (
            f"IDEA:\n{idea}\n\nGROUNDED APPROACHES:\n{approach_lines}\n\n"
            f"VERIFIED CLAIMS:\n{claim_lines}"
        )
        resp = await self._llm.complete(system=_SYSTEM, user=user)
        value = extract_json(resp.text, agent="architect")
        if not isinstance(value, dict):
            raise LLMOutputError("architect", "expected a JSON object specification")
        return value

    def _assemble(
        self,
        rid: str,
        idea: str,
        proposal: dict,
        anchors: list[Approach],
        verified: dict[str, Claim],
        state: RunState,
    ) -> Specification:
        log = state.log.append

        anchor_ids = {ap.id for ap in anchors}
        approach_id = str(proposal.get("approach_id") or "").strip() or None
        if approach_id is not None and approach_id not in anchor_ids:
            # Silently re-anchoring would be drift; the gate self-check will
            # refuse the unanchored content and the architect will abstain.
            log(f"architect: proposed anchor {approach_id!r} is not a grounded approach")
            approach_id = None

        # --- quantities: the five Zwänge start here ------------------------------
        quantities: list[Quantity] = []
        known_values: dict[str, float] = {}
        derived_pending: dict[str, tuple[str, str, Derivation]] = {}
        seen_ids: set[str] = set()

        for item in proposal.get("quantities") or []:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("id") or "").strip()
            if not _ID_RE.match(qid):
                log(f"architect: drop quantity with unsafe id {qid!r}")
                continue
            if qid in seen_ids:
                log(f"architect: drop duplicate quantity id {qid!r}")
                continue
            name = str(item.get("name") or qid).strip()
            unit = str(item.get("unit") or "").strip()
            origin = str(item.get("origin") or "").strip().lower()

            if origin == "grounded":
                grounding = [
                    cid for cid in _as_str_list(item.get("grounding")) if cid in verified
                ]
                value = _as_number(item.get("value"))
                if value is None or not grounding:
                    log(f"architect: drop quantity {qid!r} (no verified grounding/value)")
                    continue
                # Wertzwang im Wortlaut: the value must literally appear in a
                # grounding claim's text — a fabricated number cannot pass this.
                if not any(value_in_text(value, verified[cid].text) for cid in grounding):
                    log(
                        f"architect: drop quantity {qid!r} — value {value} not found "
                        "literally in any grounding claim text"
                    )
                    continue
                try:
                    quantity = Quantity(
                        id=qid, name=name, value=value, unit=unit,
                        origin=ValueOrigin.GROUNDED, grounding=grounding,
                        produced_by=self.name, model=self._llm.model,
                    )
                except GenesisError as exc:
                    log(f"architect: drop quantity {qid!r}: {exc}")
                    continue
                quantities.append(quantity)
                known_values[qid] = value
                seen_ids.add(qid)

            elif origin == "decision":
                value = _as_number(item.get("value"))
                rationale = str(item.get("rationale") or "").strip()
                if value is None or not rationale:
                    log(f"architect: drop quantity {qid!r} (hidden decision: no rationale/value)")
                    continue
                try:
                    quantity = Quantity(
                        id=qid, name=name, value=value, unit=unit,
                        origin=ValueOrigin.DECISION, rationale=rationale,
                        produced_by=self.name, model=self._llm.model,
                    )
                except GenesisError as exc:
                    log(f"architect: drop quantity {qid!r}: {exc}")
                    continue
                quantities.append(quantity)
                known_values[qid] = value
                seen_ids.add(qid)

            elif origin == "derived":
                formula = str(item.get("formula") or "").strip()
                inputs = tuple(_as_str_list(item.get("inputs")))
                if not formula or not inputs:
                    log(f"architect: drop quantity {qid!r} (derived without formula/inputs)")
                    continue
                if item.get("value") is not None:
                    # Rechenzwang: the LLM never does math. Note + overwrite.
                    log(
                        f"architect: ignoring LLM-supplied value for derived {qid!r} "
                        "— code computes it"
                    )
                derived_pending[qid] = (name, unit, Derivation(formula=formula, inputs=inputs))
                seen_ids.add(qid)

            else:
                log(f"architect: drop quantity {qid!r} (unknown origin {origin!r})")

        computed, derivation_errors = topological_values(
            known_values, {qid: d for qid, (_, _, d) in derived_pending.items()}
        )
        # Units known so far: grounded/decision quantities carry their declared
        # unit; derived quantities carry their declared unit too. Used to verify
        # each derivation is dimensionally homogeneous before it is emitted —
        # the architect never asserts a dimensionally inconsistent value (the gate
        # backstops this independently with DIMENSION_MISMATCH).
        unit_of = {q.id: q.unit for q in quantities}
        unit_of.update({qid: unit for qid, (_, unit, _) in derived_pending.items()})
        for qid, (name, unit, derivation) in derived_pending.items():
            if qid in derivation_errors:
                log(f"architect: drop derived {qid!r}: {derivation_errors[qid]}")
                continue
            if not self._dimensionally_sound(qid, unit, derivation, unit_of, log):
                continue
            quantities.append(
                Quantity(
                    id=qid, name=name, value=computed[qid], unit=unit,
                    origin=ValueOrigin.DERIVED, derivation=derivation,
                    produced_by=self.name, model=self._llm.model,
                )
            )

        # --- structure: parsed as data; GATE γ self-check judges soundness -------
        components = [
            comp for comp in (
                self._parse_component(item, log) for item in proposal.get("components") or []
            ) if comp is not None
        ]
        bom = [
            item for item in (
                self._parse_bom_item(raw, verified, log) for raw in proposal.get("bom") or []
            ) if item is not None
        ]
        steps = [
            step for step in (
                self._parse_step(raw, i, log) for i, raw in enumerate(proposal.get("steps") or [])
            ) if step is not None
        ]
        constraints = [
            con for con in (
                self._parse_constraint(raw, log) for raw in proposal.get("constraints") or []
            ) if con is not None
        ]
        decisions = [
            dec for dec in (
                self._parse_decision(raw, verified, log) for raw in proposal.get("decisions") or []
            ) if dec is not None
        ]

        claim_ids_used: list[str] = []
        anchor = next((ap for ap in anchors if ap.id == approach_id), None)
        referenced = [
            *(cid for q in quantities for cid in q.grounding),
            *(cid for b in bom for cid in b.grounding),
            *(cid for d in decisions for cid in d.informed_by),
            *((anchor.grounding if anchor else [])),
        ]
        for cid in referenced:
            if cid not in claim_ids_used:
                claim_ids_used.append(cid)

        return Specification(
            run_id=rid,
            idea=idea,
            approach_id=approach_id,
            quantities=quantities,
            components=components,
            bom=bom,
            steps=steps,
            constraints=constraints,
            decisions=decisions,
            claim_ids_used=claim_ids_used,
            produced_by=self.name,
            model=self._llm.model,
        )

    # --- structural parsers (tolerant on shape, never on meaning) ----------------

    def _parse_geometry(self, raw: object, log) -> GeometryNode | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            log("architect: geometry node is not an object -> dropped")
            return None
        params_raw = raw.get("params")
        params = (
            {str(k): str(v) for k, v in params_raw.items()}
            if isinstance(params_raw, dict)
            else {}
        )
        children = [
            child for child in (
                self._parse_geometry(c, log) for c in raw.get("children") or []
            ) if child is not None
        ]
        return GeometryNode(kind=str(raw.get("kind") or "").strip(), params=params, children=children)

    def _parse_component(self, raw: object, log) -> Component | None:
        if not isinstance(raw, dict):
            return None
        cid = str(raw.get("id") or "").strip()
        if not cid:
            log("architect: drop component without id")
            return None
        return Component(
            id=cid,
            name=str(raw.get("name") or cid).strip(),
            geometry=self._parse_geometry(raw.get("geometry"), log),
            quantity_ids=_as_str_list(raw.get("quantity_ids")),
        )

    def _parse_bom_item(self, raw: object, verified: dict[str, Claim], log) -> BomItem | None:
        if not isinstance(raw, dict):
            return None
        bid = str(raw.get("id") or "").strip()
        if not bid:
            log("architect: drop BOM item without id")
            return None
        role_raw = str(raw.get("role") or "").strip().lower()
        try:
            role = BomRole(role_raw)
        except ValueError:
            log(f"architect: drop BOM item {bid!r} (unknown role {role_raw!r})")
            return None
        count_raw = raw.get("count", 1)
        count = int(count_raw) if isinstance(count_raw, int) and not isinstance(count_raw, bool) else 1
        component_id = str(raw.get("component_id")).strip() if raw.get("component_id") else None
        grounding = [cid for cid in _as_str_list(raw.get("grounding")) if cid in verified]
        return BomItem(
            id=bid, name=str(raw.get("name") or bid).strip(), role=role,
            count=count, component_id=component_id, grounding=grounding,
        )

    def _parse_step(self, raw: object, position: int, log) -> Step | None:
        if not isinstance(raw, dict):
            return None
        sid = str(raw.get("id") or "").strip()
        if not sid:
            log("architect: drop step without id")
            return None
        index_raw = raw.get("index")
        index = (
            index_raw
            if isinstance(index_raw, int) and not isinstance(index_raw, bool)
            else position + 1
        )
        return Step(
            id=sid,
            index=index,
            action=str(raw.get("action") or "").strip(),
            uses=_as_str_list(raw.get("uses")),
            inputs=_as_str_list(raw.get("inputs")),
            outputs=_as_str_list(raw.get("outputs")),
            check=str(raw.get("check") or "").strip(),
            quantity_refs=_as_str_list(raw.get("quantity_refs")),
        )

    def _parse_constraint(self, raw: object, log) -> Constraint | None:
        if not isinstance(raw, dict):
            return None
        kid = str(raw.get("id") or "").strip()
        if not kid:
            log("architect: drop constraint without id")
            return None
        return Constraint(
            id=kid,
            kind=str(raw.get("kind") or "").strip().lower(),
            left=str(raw.get("left") or "").strip(),
            right=str(raw.get("right") or "").strip(),
            reason=str(raw.get("reason") or "").strip(),
        )

    def _parse_decision(self, raw: object, verified: dict[str, Claim], log) -> Decision | None:
        if not isinstance(raw, dict):
            return None
        did = str(raw.get("id") or "").strip()
        if not did:
            log("architect: drop decision without id")
            return None
        try:
            return Decision(
                id=did,
                title=str(raw.get("title") or did).strip(),
                choice=str(raw.get("choice") or "").strip(),
                rationale=str(raw.get("rationale") or "").strip(),
                informed_by=[
                    cid for cid in _as_str_list(raw.get("informed_by")) if cid in verified
                ],
            )
        except GenesisError as exc:
            log(f"architect: drop decision {did!r} (hidden decision): {exc}")
            return None
