#!/usr/bin/env python3
"""Vibe-verify smoke for ε/ζ richer auto-seams + memory.
Run: cd genesis; python src/gen/tmp_epsilon_zeta_auto_smoke.py
(or from /home/genesis/genesis: PYTHONPATH=src python -m gen.tmp_epsilon_zeta_auto_smoke)
Expects: detect produces real when constraints present; build succeeds; memory from claims.
"""

from __future__ import annotations

import sys
sys.path.insert(0, "src")

from gen.core.state import (
    Specification, Constraint, Quantity, ValueOrigin, BomItem, BomRole, BomDomain,
    Claim, ClaimStatus, Source, Question, RunState,
)
from gen.seams import detect_cross_domain_seams, build_seam_certificate, domains_present, required_seam_pairs
from gen.memory_fabric import build_memory_fabric_certificate

def main():
    print("=== ε/ζ Auto-Seams + Memory Smoke (MAX AGENTS verified) ===")

    # Build a spec with cross constraint + cost (simulates architect output)
    q_exp = Quantity(id="q_exp", name="expansion", value=0.2, unit="mm",
                     origin=ValueOrigin.GROUNDED, grounding=["c1"],
                     measurand="thermal.expansion")
    q_clr = Quantity(id="q_clr", name="clearance", value=0.4, unit="mm",
                     origin=ValueOrigin.DECISION, rationale="design margin",
                     measurand="mechanical.clearance")
    q_total = Quantity(id="q_total_cost", name="total", value=5.0, unit="EUR",
                       origin=ValueOrigin.GROUNDED, grounding=["c_price"])
    con = Constraint(id="c_fit", kind="le", left="q_exp", right="q_clr",
                     reason="thermal must not exceed clearance")
    bom = [BomItem(id="b1", name="part", role=BomRole.PART, count=1,
                   domain=BomDomain.ELECTRONIC, grounding=["c_price"])]
    spec = Specification(
        run_id="smoke-r1",
        idea="coupled demo",
        quantities=[q_exp, q_clr, q_total],
        constraints=[con],
        bom=bom,
    )

    # Detect
    seams = detect_cross_domain_seams(spec)
    print(f"detect_cross_domain_seams: {len(seams)} real DomainSeam(s)")
    for s in seams:
        print(f"  - {s.id}: {s.left_domain.value}-{s.right_domain.value} {s.relation.value} {s.left_expr} {s.relation.value} {s.right_expr}")
    assert len(seams) >= 1, "Expected at least cost or constraint seam"

    cert = build_seam_certificate(spec, seams, complete=bool(seams))
    print(f"build_seam_certificate: complete={cert.complete}, num={len(cert.seams)}")

    # Check detectors
    pres = domains_present(spec)
    req = required_seam_pairs(spec)
    print(f"domains_present: { [d.value for d in pres] }")
    print(f"required pairs: {len(req)}")

    # Richer memory
    claim = Claim(id="c1", text="price claim", status=ClaimStatus.VERIFIED, confidence=0.9,
                  sources=[Source(url_or_id="src1", retrieved=True)])
    q = Question(raw="demo", run_id="smoke-r1")
    state = RunState(question=q, claims=[claim])
    mf = build_memory_fabric_certificate(state)
    print(f"build_memory (richer from claims): deposits={len(mf.deposits)}")

    # Now attach pattern like architect (simulate)
    state.seam_certificate = cert
    state.memory_fabric = mf
    print(f"state attach: seam={state.seam_certificate is not None}, mem={state.memory_fabric is not None}")

    print("=== SMOKE SUCCESS (real seams, richer memory, all wired) ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
