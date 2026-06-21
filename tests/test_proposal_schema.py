"""Tests for the validated proposal schema (llm/schemas.py) + its use in the proposer.

Pins: valid JSON parses to ProposalModels; a shape-invalid item is SKIPPED (honest abstention), never
trusted or crashing (the old hand-rolled path raised on a non-dict ``exponents``); an unparseable
payload yields []; the model exposes a JSON schema for the live structured-output path; and the
GrokProposer routes its output through the validated parser. Offline, no network, no LLM.
"""

import pytest

from gen.discovery.symbiosis import GrokProposer
from gen.llm.base import ScriptedLLM
from gen.llm.schemas import ProposalModel, parse_proposals


def test_parses_a_valid_proposal_list():
    text = '[{"exponents": {"L": 0.5, "g": -0.5}, "rationale": "dimensional"}]'
    out = parse_proposals(text)
    assert len(out) == 1
    assert out[0].exponents == {"L": 0.5, "g": -0.5} and out[0].rationale == "dimensional"


def test_skips_shape_invalid_items_keeps_valid():
    text = (
        '[{"exponents": {"L": 0.5}, "rationale": "ok"},'
        ' {"rationale": "missing exponents"},'         # no exponents -> skipped
        ' {"exponents": [1, 2]},'                       # exponents not a mapping -> skipped (old code CRASHED)
        ' {"exponents": {"a": "abc"}},'                 # non-numeric value -> skipped
        ' {"exponents": {"a": 1.5}, "extra": 9}]'       # extra key tolerated -> kept
    )
    out = parse_proposals(text)
    assert [p.exponents for p in out] == [{"L": 0.5}, {"a": 1.5}]


def test_string_numbers_are_coerced():
    assert parse_proposals('[{"exponents": {"L": "0.5"}}]')[0].exponents == {"L": 0.5}


def test_unparseable_payload_returns_empty():
    assert parse_proposals("not json at all") == []
    assert parse_proposals("") == []


def test_model_exposes_json_schema_for_the_live_path():
    schema = ProposalModel.model_json_schema()
    assert "exponents" in schema["properties"] and "rationale" in schema["properties"]


@pytest.mark.asyncio
async def test_grok_proposer_routes_through_the_validated_parser():
    # the proposer turns validated models into domain Proposals, tagging the source; a bad item is dropped.
    scripted = ScriptedLLM(
        "grok-build",
        '[{"exponents": {"L": 0.5, "g": -0.5}, "rationale": "T~sqrt(L/g)"}, {"exponents": [1]}]',
    )
    proposer = GrokProposer(client=scripted, model="grok-build")
    from gen.discovery.benchmark import pendulum_case

    proposals = await proposer.propose(pendulum_case().problem, n=3)
    assert len(proposals) == 1                                  # the invalid second item was skipped
    assert proposals[0].exponents == {"L": 0.5, "g": -0.5}
    assert proposals[0].source == "grok-build"
