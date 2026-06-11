"""Phase γ acceptance — the four idea classes through the REAL pipeline.

Each class runs scout -> scholar -> skeptic -> synthesizer -> architect in a
deterministic "scripted world" (scripted models + canned sources) and checks the
γ GUARANTEES (PHASE_GAMMA.md §6/§7), not real model quality. No network, no LLM.

  A  buildable          -> complete, gated specification             (G1-G5,G8)
  B  fabricated value / LLM math trap -> dropped / recomputed        (G1,G2,G6)
  C  nothing verifiable -> abstention, no fabricated specification   (G7)
  D  incomplete-instruction trap -> abstention, never a partial plan (G5,G6)

Run:  pytest tests/test_phase_gamma_acceptance.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.architect import Architect  # noqa: E402
from gen.agents.conductor import Conductor  # noqa: E402
from gen.agents.scholar import Scholar  # noqa: E402
from gen.agents.scout import Scout  # noqa: E402
from gen.agents.skeptic import Skeptic  # noqa: E402
from gen.agents.synthesizer import Synthesizer  # noqa: E402
from gen.core.state import (  # noqa: E402
    ClaimStatus,
    Question,
    RunState,
    SourceCandidate,
    ValueOrigin,
)
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.tools.fetch import WebFetchTool  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402
from gen.verification.gates import gate_gamma  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeBackend:
    def __init__(self, name, urls):
        self.name = name
        self._urls = urls

    async def search(self, query, limit):
        return [
            SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="r")
            for u in self._urls
        ][:limit]


def http_all(mapping):
    async def _get(url):
        return HttpResponse(status=200, body=mapping.get(url, ""), final_url=url)

    return _get


def scholar_llm(extract_map):
    """extract_map: list of (content_substr, claim_text, quote)."""
    def responder(system, user):
        content = user.split("SOURCE TEXT:", 1)[-1]
        for sub, text, quote in extract_map:
            if sub in content:
                return json.dumps([{"text": text, "quote": quote}])
        return "[]"

    return ScriptedLLM("claude-opus-4-8", responder)


def verifier_llm():
    def responder(system, user):
        return json.dumps({"relation": "supports", "confidence": 0.85, "reason": "x"})

    return ScriptedLLM("gpt-4o", responder)


def synth_llm(groups):
    """groups: list of (keyword, approach_name); ids read from the prompt."""
    def responder(system, user):
        block = user.split("VERIFIED CLAIMS:", 1)[-1]
        pairs = _id_lines(block)
        out = []
        for keyword, name in groups:
            ids = [cid for cid, text in pairs.items() if keyword.lower() in text.lower()]
            if ids:
                out.append({"name": name, "grounding": [ids[0]], "tradeoffs": []})
        return json.dumps(out)

    return ScriptedLLM("claude-opus-4-8", responder)


def _id_lines(block):
    out = {}
    for ln in block.strip().splitlines():
        if ": " in ln:
            cid, text = ln.split(": ", 1)
            out[cid.strip()] = text.strip()
    return out


def _bracket_proposal(ap_id, c_load, c_screw, *, mutate=None):
    proposal = {
        "approach_id": ap_id,
        "quantities": [
            {"id": "q_load", "name": "verified shelf load", "unit": "kg",
             "origin": "grounded", "value": 12, "grounding": [c_load]},
            {"id": "q_screw_d", "name": "screw diameter", "unit": "mm",
             "origin": "grounded", "value": 4, "grounding": [c_screw]},
            {"id": "q_sf", "name": "safety factor", "unit": "1", "origin": "decision",
             "value": 2, "rationale": "conservative; 1.5 and 3 considered"},
            {"id": "q_design", "name": "design load", "unit": "kg", "origin": "derived",
             "formula": "q_load * q_sf", "inputs": ["q_load", "q_sf"]},
            {"id": "q_hole_d", "name": "hole diameter", "unit": "mm", "origin": "decision",
             "value": 4.5, "rationale": "clearance fit for M4"},
            {"id": "q_hole_r", "name": "hole radius", "unit": "mm", "origin": "derived",
             "formula": "q_hole_d / 2", "inputs": ["q_hole_d"]},
            {"id": "q_w", "name": "width", "unit": "mm", "origin": "decision",
             "value": 60, "rationale": "fits shelf depth"},
            {"id": "q_h", "name": "height", "unit": "mm", "origin": "decision",
             "value": 80, "rationale": "lever arm"},
            {"id": "q_t", "name": "thickness", "unit": "mm", "origin": "decision",
             "value": 6, "rationale": "printable wall"},
        ],
        "components": [
            {"id": "c_bracket", "name": "bracket",
             "quantity_ids": ["q_w", "q_h", "q_t", "q_hole_d", "q_hole_r"],
             "geometry": {
                 "kind": "difference",
                 "children": [
                     {"kind": "box", "params": {"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}},
                     {"kind": "cylinder", "params": {"radius": "q_hole_r", "height": "q_t"}},
                 ],
             }},
        ],
        "bom": [
            {"id": "b_bracket", "name": "bracket", "role": "part", "count": 1,
             "component_id": "c_bracket"},
            {"id": "b_screw", "name": "M4 screw", "role": "part", "count": 2,
             "grounding": [c_screw]},
            {"id": "b_printer", "name": "3D printer", "role": "tool", "count": 1},
        ],
        "steps": [
            {"id": "s1", "index": 1, "action": "3D-print the bracket.",
             "uses": ["b_printer"], "inputs": ["b_bracket"], "outputs": ["a_printed"],
             "check": "Part measures q_w x q_h x q_t.", "quantity_refs": ["q_w", "q_h", "q_t"]},
            {"id": "s2", "index": 2, "action": "Mount the bracket with both screws.",
             "uses": ["b_screw"], "inputs": ["a_printed"], "outputs": ["a_mounted"],
             "check": "Bracket carries q_design without movement.",
             "quantity_refs": ["q_design"]},
        ],
        "constraints": [
            {"id": "k1", "kind": "ge", "left": "q_hole_d", "right": "q_screw_d",
             "reason": "screw must pass through the hole"},
        ],
        "decisions": [
            {"id": "d_mat", "title": "Material", "choice": "PLA, 3D-printed",
             "rationale": "available; sufficient for static indoor load"},
        ],
    }
    if mutate is not None:
        mutate(proposal)
    return proposal


def architect_llm(*, mutate=None):
    """Builds the bracket proposal from ids parsed out of the architect prompt."""
    def responder(system, user):
        approaches = _id_lines(
            user.split("GROUNDED APPROACHES:", 1)[-1].split("VERIFIED CLAIMS:", 1)[0]
        )
        claims = _id_lines(user.split("VERIFIED CLAIMS:", 1)[-1])
        ap_id = next(iter(approaches), None)
        c_load = next((cid for cid, t in claims.items() if "12 kg" in t), None)
        c_screw = next((cid for cid, t in claims.items() if "4 mm" in t), None)
        if not (ap_id and c_load and c_screw):
            return "{}"
        return json.dumps(_bracket_proposal(ap_id, c_load, c_screw, mutate=mutate))

    return ScriptedLLM("claude-opus-4-8", responder)


BRACKET_DOCS = {
    "https://d/load": "A typical wall shelf must carry a load of 12 kg.",
    "https://d/screw": "An M4 screw has a nominal diameter of 4 mm.",
    "https://d/bracket": "Cantilever brackets are used for wall-mounted shelves.",
}
BRACKET_EXTRACT = [
    ("must carry a load", "A typical wall shelf must carry a load of 12 kg.",
     "must carry a load of 12 kg"),
    ("nominal diameter", "An M4 screw has a nominal diameter of 4 mm.",
     "a nominal diameter of 4 mm"),
    ("Cantilever brackets", "Cantilever brackets are used for wall-mounted shelves.",
     "Cantilever brackets are used"),
]
IDEA = "A wall-mounted shelf bracket that carries the verified shelf load"


def build(*, docs=None, extract_map=None, skeptic_urls=("https://i1", "https://i2"),
          architect=None, run_id="rg"):
    docs = BRACKET_DOCS if docs is None else docs
    extract_map = BRACKET_EXTRACT if extract_map is None else extract_map
    ledger = InMemoryLedgerStore()
    http = {**docs, **{u: "SUPPORT: independent corroborating text" for u in skeptic_urls}}
    fetch = WebFetchTool(http_all(http))
    scout = Scout([FakeBackend("scout", list(docs.keys()))])
    scholar = Scholar(fetch, scholar_llm(extract_map), ledger)
    skeptic = Skeptic(
        [FakeBackend("skeptic", list(skeptic_urls))],
        fetch,
        verifier_llm(),
        ledger,
        min_sources_for_verified=2,
    )
    synth = Synthesizer(synth_llm([("cantilever", "Cantilever bracket")]))
    arch = architect or Architect(architect_llm())
    conductor = Conductor(scout, scholar, skeptic, synthesizer=synth, architect=arch)
    state = RunState(question=Question(raw=IDEA, run_id=run_id))
    run(conductor.run_specification(state))
    return state, ledger


def _verified_ids(ledger, run_id="rg"):
    return {c.id for c in run(ledger.get_claims(run_id)) if c.status is ClaimStatus.VERIFIED}


# --- Class A: buildable — a complete, honest specification ---------------------

def test_class_A_complete_specification():
    state, ledger = build()
    spec = state.specification
    assert spec is not None

    # the build plan exists and is anchored (β chain)
    assert spec.components and spec.steps and spec.bom
    assert spec.approach_id is not None
    assert any(ap.id == spec.approach_id for ap in state.approaches)

    # G1: grounded values reference VERIFIED ledger claims only
    verified = _verified_ids(ledger)
    for q in spec.quantities:
        if q.origin is ValueOrigin.GROUNDED:
            assert q.grounding and all(cid in verified for cid in q.grounding)

    # G2: derived values are code-computed and recomputable
    q_design = next(q for q in spec.quantities if q.id == "q_design")
    assert q_design.value == 24.0

    # G3: every decision carries a rationale
    for q in spec.quantities:
        if q.origin is ValueOrigin.DECISION:
            assert q.rationale.strip()
    for d in spec.decisions:
        assert d.rationale.strip() and d.choice.strip()

    # G4/G5/G8: the independent gate confirms the whole structure
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    assert any("gate gamma" in ln and "passed=True" in ln for ln in state.log)

    # 3D content: a parametric CSG tree whose params are quantity ids
    geom = spec.components[0].geometry
    assert geom is not None and geom.kind == "difference"
    qids = {q.id for q in spec.quantities}
    box = geom.children[0]
    assert set(box.params.values()) <= qids


def test_class_A_is_reproducible():
    s1, _ = build()
    s2, _ = build()
    shape1 = sorted((q.id, q.value, q.origin.value) for q in s1.specification.quantities)
    shape2 = sorted((q.id, q.value, q.origin.value) for q in s2.specification.quantities)
    assert shape1 == shape2


# --- Class B: fabricated value / LLM-math trap ----------------------------------

def test_class_B_fabricated_value_dropped_and_math_recomputed():
    def mutate(proposal):
        # (a) a fabricated grounded value: 70 is in NO claim text
        proposal["quantities"].append(
            {"id": "q_fake", "name": "tensile strength", "unit": "MPa",
             "origin": "grounded", "value": 70,
             "grounding": [proposal["quantities"][0]["grounding"][0]]}
        )
        # (b) the LLM "precomputes" nonsense for a derived value
        proposal["quantities"][3]["value"] = 999  # q_design

    state, _ = build(architect=Architect(architect_llm(mutate=mutate)))
    spec = state.specification
    assert spec is not None and spec.components            # plan still asserted

    # (a) the fabricated value never reaches the specification
    assert all(q.id != "q_fake" for q in spec.quantities)
    assert any("q_fake" in ln and "not found literally" in ln for ln in state.log)

    # (b) the asserted value is the CODE-computed one, not the LLM's
    q_design = next(q for q in spec.quantities if q.id == "q_design")
    assert q_design.value == 24.0
    assert any("ignoring LLM-supplied value" in ln for ln in state.log)

    assert gate_gamma(state).passed


# --- Class C: nothing verifiable -> abstention -----------------------------------

def test_class_C_abstention():
    state, ledger = build(
        docs={"https://d/ftl": "Some speculative FTL idea is described here in prose."},
        extract_map=[
            ("speculative FTL", "A speculative FTL mechanism is proposed.",
             "Some speculative FTL idea is described here"),
        ],
        skeptic_urls=(),                                   # no independent corroboration
    )
    spec = state.specification
    assert spec is not None
    assert spec.components == [] and spec.steps == [] and spec.quantities == []
    assert spec.gaps                                       # honest, named gap
    assert gate_gamma(state).passed                        # honest emptiness passes


# --- Class D: incomplete-instruction trap -> abstention, never a partial plan ----

def test_class_D_incomplete_instruction_yields_abstention():
    def mutate(proposal):
        proposal["steps"][1]["check"] = ""                 # step without a check
        proposal["steps"][1]["uses"] = ["b_ghost"]         # dangling reference
        proposal["steps"][1]["inputs"] = ["a_never_made"]  # input never produced

    state, _ = build(architect=Architect(architect_llm(mutate=mutate)))
    spec = state.specification
    assert spec is not None

    # never a partial/drifted plan: abstention with named defects
    assert spec.components == [] and spec.steps == []
    assert any("structural defects" in g for g in spec.gaps)
    log = "\n".join(state.log)
    assert "INCOMPLETE_STEP" in log
    assert "DANGLING_REFERENCE" in log
    assert "UNBUILDABLE_ORDER" in log
    assert gate_gamma(state).passed                        # abstention is sound


# --- Class E: dimensional-inconsistency trap (Mars-Climate-Orbiter class) --------

def test_class_E_dimensional_trap_value_dropped_and_math_recomputed():
    def mutate(proposal):
        # a derived value that adds mass (kg) to length (mm): dimensional nonsense.
        proposal["quantities"].append(
            {"id": "q_nonsense", "name": "nonsense", "unit": "kg", "origin": "derived",
             "formula": "q_load + q_screw_d", "inputs": ["q_load", "q_screw_d"]}
        )
        # an area (mm*mm) mislabeled as a length (mm)
        proposal["quantities"].append(
            {"id": "q_area", "name": "area", "unit": "mm", "origin": "derived",
             "formula": "q_w * q_h", "inputs": ["q_w", "q_h"]}
        )

    state, _ = build(architect=Architect(architect_llm(mutate=mutate)))
    spec = state.specification
    assert spec is not None and spec.components            # plan still asserted

    # both dimensional errors are dropped, never asserted
    ids = {q.id for q in spec.quantities}
    assert "q_nonsense" not in ids and "q_area" not in ids
    log = "\n".join(state.log)
    assert "dimension" in log.lower()

    # the legitimate derivations survive and recompute correctly
    q_design = next(q for q in spec.quantities if q.id == "q_design")
    assert q_design.value == 24.0
    assert gate_gamma(state).passed                        # rest stays sound


# --- end-to-end wiring: CLI demo through runner + checkpoint ----------------------

def test_spec_demo_end_to_end(tmp_path):
    from gen.cli import build_spec_demo, format_specification
    from gen.runner import run_specification

    idea, deps, cfg = build_spec_demo()
    spec = run(
        run_specification(
            idea, deps, config=cfg, run_id="demo-bracket",
            checkpoint_dir=str(tmp_path),
        )
    )
    assert spec.components and len(spec.steps) == 2
    q_design = next(q for q in spec.quantities if q.id == "q_design")
    assert q_design.value == 24.0

    rendered = format_specification(spec)
    assert "Build steps" in rendered and "Decision sheet" in rendered

    checkpoint = json.loads(
        (tmp_path / "demo-bracket" / "checkpoint.json").read_text(encoding="utf-8")
    )
    assert checkpoint["specification"] is not None
    assert checkpoint["specification"]["steps"]
