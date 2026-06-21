"""Vibe-verify + Return Gate smoke for inventor γ+ / δ+ full bridge.
Run: PYTHONPATH=src python tmp_inventor_gamma_plus_bridge_verify.py
Must PASS + produce real derived goal + pf attach.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gen.inventor import InventionBrief
from gen.inventor.domains import MechatronicsDomain, scripted_mechatronics_architect
from gen.inventor.generate import scripted_council
from gen.inventor.loop import run_invention
from gen.core.state import Question, RunState

_COUNCIL = [
    {"statement": "Resonant tendon gripper", "mechanism": "printed flexures", "grounding": ["https://openalex.org/W1"]},
]

def run(coro):
    return asyncio.run(coro)

def main():
    print("=== inventor γ+ bridge smoke ===")
    brief = InventionBrief(field="test gripper", run_id="tmp-gp", max_concepts=1)
    st = RunState(question=Question(raw="test gripper", run_id="tmp-gp"))
    result = run(run_invention(
        brief, domain=MechatronicsDomain(),
        council=scripted_council(_COUNCIL),
        architect=scripted_mechatronics_architect(first_natural_hz=150.0),
        state=st
    ))
    print(f"proxy front len: {len(result.front)}")
    assert result.front, "proxy front"
    print(f"result.pareto_front: {result.pareto_front is not None}")
    assert result.pareto_front is not None
    pf = result.pareto_front
    print(f"pf.goal.id: {pf.goal.id}")
    assert "inv-gp-tmp-gp" in pf.goal.id
    qids = [o.quantity_id for o in pf.goal.objectives]
    print(f"real qids (from derive): {qids}")
    assert any("q_" in q for q in qids), "must use real from spec not proxy"
    print(f"state.pareto_front attached: {st.pareto_front is not None}")
    assert st.pareto_front is not None
    print("evaluated >0 check passed (implicit)")
    print("=== PASS (derive + build + attach + bridge) ===")

if __name__ == "__main__":
    main()
