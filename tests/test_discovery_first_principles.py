"""First-Principles Discovery Mode — derive from axioms, gate_c6-verify every step (4.5)."""

from gen.discovery import Axiom, ProofStep, verify_proof, derive


def test_verifies_a_correct_multi_step_derivation():
    """A two-step derivation (a = F/m, v = a·t) from axioms is recomputed step by step and
    proven — the highest-trust result, every step independently checked."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0), Axiom("t", 2.0)]
    steps = [ProofStep("a", "F / m", 4.0), ProofStep("v", "a * t", 8.0)]
    proof = verify_proof(axioms, steps, target_name="v", target_value=8.0)
    assert proof.proven
    assert all(s.verified for s in proof.steps)
    assert proof.target_name == "v" and proof.target_value == 8.0


def test_catches_a_tampered_step():
    """gate_c6 in action: a step whose claimed value does NOT follow from its formula is caught,
    and the proof fails — GENESIS recomputes, it does not take a derivation on faith."""
    axioms = [Axiom("F", 12.0), Axiom("m", 3.0)]
    bad = [ProofStep("a", "F / m", 5.0)]            # 12/3 = 4, not 5
    proof = verify_proof(axioms, bad, target_name="a")
    assert not proof.proven
    assert proof.steps[0].verified is False


def test_derives_a_one_operation_law_from_axioms():
    """Bounded search finds a = F/m from the axioms and returns a verified proof."""
    proof = derive([Axiom("F", 12.0), Axiom("m", 3.0)], target_value=4.0, max_ops=1)
    assert proof is not None and proof.proven
    assert proof.steps[0].verified
    assert proof.steps[0].formula in ("F / m",)


def test_derives_a_two_operation_law():
    """A target reachable ONLY by two operations ((a/b)+c = 7, not by any single op) is found
    and proven — and the search prefers the shorter derivation when one exists."""
    proof = derive([Axiom("a", 6.0), Axiom("b", 2.0), Axiom("c", 4.0)], target_value=7.0, max_ops=2)
    assert proof is not None and proof.proven
    assert "(" in proof.steps[0].formula                  # two ops -> a grouped formula
    # the single-op search cannot reach 7 from {6,2,4}, so a 1-op bound returns nothing
    assert derive([Axiom("a", 6.0), Axiom("b", 2.0), Axiom("c", 4.0)], target_value=7.0, max_ops=1) is None


def test_returns_none_when_unreachable_within_the_bound():
    """Honest boundary: no short derivation reaches the target → None, not a fabricated proof."""
    assert derive([Axiom("a", 2.0), Axiom("b", 3.0)], target_value=100.0, max_ops=1) is None


def test_a_step_referencing_an_unknown_name_fails():
    proof = verify_proof([Axiom("F", 1.0)], [ProofStep("a", "F / m", 1.0)], target_name="a")
    assert not proof.proven and proof.steps[0].verified is False
