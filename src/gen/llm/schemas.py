"""Validated proposal schemas — one source of truth for breadth proposals.

Replaces ad-hoc dict-poking of LLM JSON with a Pydantic model, so a malformed proposal becomes an
honest ABSTENTION (skipped), never a fabricated parse OR an uncaught crash (the old hand-rolled path
raised ``AttributeError`` on a non-dict ``exponents``). The SAME model drives the live Agent-SDK
structured-output path: ``ProposalModel.model_json_schema()`` is exactly the server-side JSON schema a
proposer model is constrained to. Validation guards only the SHAPE — the deterministic gate still
judges every parsed proposal for correctness (CLAUDE.md §1: the model proposes, the gate disposes).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationError

from .parsing import extract_json


class ProposalModel(BaseModel):
    """The validated shape of one breadth proposal: a power-law exponent hypothesis + a rationale.

    ``extra='ignore'`` tolerates extra keys a model may add; ``exponents`` must be a mapping of names to
    numbers (Pydantic coerces ``"0.5"`` → ``0.5`` and rejects non-numeric), matching the old tolerant
    parse without its crash-on-non-dict footgun.
    """

    model_config = ConfigDict(extra="ignore")

    exponents: dict[str, float]
    rationale: str = ""


def parse_proposals(text: str, *, agent: str = "proposer") -> list[ProposalModel]:
    """Parse LLM text into validated ``ProposalModel``s. Tolerant by design: an unparseable whole
    payload returns ``[]``; an individual item that fails validation is SKIPPED (honest abstention),
    never trusted. Mirrors ``llm.parsing.extract_json`` noise-tolerance, then adds schema validation."""
    try:
        data = extract_json(text, agent=agent)
    except Exception:
        return []
    items = data if isinstance(data, list) else [data]
    out: list[ProposalModel] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            out.append(ProposalModel.model_validate(item))
        except ValidationError:
            continue  # a shape-invalid proposal is skipped, never fabricated
    return out
