"""Tests für Promotion-Gate + HITL-Ratifikation (math-research, Stein d-full).

ESTABLISHED (wiederverwendbarer Anchor) ist ohne expliziten menschlichen SignOff
UNMÖGLICH; CAS-certified allein erreicht autonom höchstens HARDENED. Refutation eines
Anchors kaskadiert über depends_on (Dependents auf HARDENED gedeckelt).
"""

from gen.identity_research import (
    AssumptionManifest,
    IdentityArtifact,
    IdentityClaim,
    ProofCertificate,
    assess_identity,
)
from gen.ratification import SignOff
from gen.research_promotion import (
    PromotionLedger,
    PromotionRecord,
    autonomous_stage,
    is_anchor,
    promote_to_established,
)


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def _grid_only_artifact(cid="g1"):
    claim = IdentityClaim(cid, "f(x)", "f(x)", _mR(), novelty_key=f"nk_{cid}")
    cert = ProofCertificate("grid_only", False, "grid only", "L", "admitted")
    return IdentityArtifact(claim, "SURVIVED_NOVEL", "p", None, None, 1.0, 1, "L", proof=cert)


def test_autonomous_stage_never_returns_established():
    cas = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1", _mR())
    assert autonomous_stage(cas) == "HARDENED"            # cas_certified, autonomous ceiling
    grid = _grid_only_artifact()
    assert autonomous_stage(grid) == "SUPPORTED"          # grid-only
    refuted = assess_identity("f1", "x", "x + 1", _mR())
    assert autonomous_stage(refuted) == "DISPROVED"
    for art in (cas, grid, refuted):
        assert autonomous_stage(art) != "ESTABLISHED"


def test_established_impossible_without_signoff():
    cas = assess_identity("pyth2", "sin(x)**2 + cos(x)**2", "1", _mR())
    assert promote_to_established(cas, SignOff()) is None          # empty sign-off
    rec = promote_to_established(cas, SignOff(approved=frozenset({"pyth2"}), approver="ozan"))
    assert rec is not None
    assert rec.to_stage == "ESTABLISHED"
    assert rec.signoff_ref == "ozan"
    assert is_anchor(rec.to_stage)


def test_grid_only_cannot_be_established_even_with_signoff():
    grid = _grid_only_artifact("g2")
    rec = promote_to_established(grid, SignOff(approved=frozenset({"g2"}), approver="ozan"))
    assert rec is None                                    # not cas_certified -> no anchor


def test_refutation_cascade_caps_dependents_at_hardened():
    led = PromotionLedger()
    led.record(PromotionRecord("A", "HARDENED", "ESTABLISHED", "cas_certified", 3, "ozan", signoff_ref="ozan"))
    led.record(PromotionRecord("B", "HARDENED", "ESTABLISHED", "cas_certified", 3, "ozan",
                               signoff_ref="ozan", depends_on=("A",)))
    led.record(PromotionRecord("C", "SUPPORTED", "ESTABLISHED", "cas_certified", 3, "ozan",
                               signoff_ref="ozan"))  # independent anchor
    assert led.is_anchor("A") and led.is_anchor("B") and led.is_anchor("C")

    demoted = led.demote_refuted_anchor("A")
    assert "A" in demoted and "B" in demoted             # A and its dependent B
    assert led.stage("A") == "DISPROVED"
    assert led.stage("B") == "HARDENED"                  # dependent capped, no longer anchor
    assert not led.is_anchor("A") and not led.is_anchor("B")
    assert led.is_anchor("C")                            # independent anchor untouched
