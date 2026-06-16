"""Bounded Identity Falsifier + Witness Finder — first stone of the math-research branch.

GENESIS creates new validated knowledge; the LLM PROPOSES a candidate identity
``lhs == rhs`` (under an explicit AssumptionManifest), and this module verifies it
with DETERMINISTIC, LLM-free checks (Kernprinzip 2+5). The honest epistemics agreed
with the co-architect (see docs):

- Truth is produced by DEDUCTION (symbolic proof: ``simplify(lhs-rhs)==0``) or by
  FALSIFICATION (no counterexample on a sampled grid). Data-consistency is a shared
  necessary GATE, never sufficient on its own.
- "New" is a GATE result (a coverage-bounded prior-art check), never an LLM label.
- Simulation/search proves IMPOSSIBILITY (a counterexample REFUTES), never possibility.
- Canonicalization errs toward NOT-proven-equal: a false split is harmless, a false
  merge (calling two different claims the same) is forbidden.

v1 scope — IN: polynomial / rational / trig identities; AssumptionManifest with domain
+ per-variable assumptions + predicates; two-bucket fingerprint; deterministic grid
falsification with a witness; a novelty index stub; an honest status + severity; a Lean
statement string (recorded, not executed). OUT (deferred): Lean execution, live
OEIS/OpenAlex, integrals/limits/series, full real-z3, ESTABLISHED promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import sympy as sp

DomainId = Literal["R", "R+", "C", "Z", "N"]
VarType = Literal["real", "positive", "integer", "complex"]
FpTier = Literal["proved_equal", "structural", "not_proven_equal"]
Status = Literal["REFUTED", "INCONCLUSIVE", "SURVIVED_KNOWN", "SURVIVED_NOVEL"]

# Rough fraction of the relevant universe a domain's sampling can cover — feeds severity
# so an identity verified on all of R outranks one only checked on a sparse integer window.
_DOMAIN_FRACTION: dict[str, float] = {"R": 1.0, "C": 1.0, "R+": 0.5, "Z": 0.4, "N": 0.25}

# Deterministic sample anchors per domain (reproducibility — Kernprinzip 5; never random()).
_REAL_ANCHORS = (-3.0, -2.0, -1.5, -1.0, -0.5, -0.25, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5)
_POS_ANCHORS = tuple(a for a in _REAL_ANCHORS if a > 0)
_INT_ANCHORS = tuple(float(i) for i in range(-6, 13))
_NAT_ANCHORS = tuple(float(i) for i in range(0, 19))


def _sha(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class AssumptionManifest:
    """The explicit context an identity is claimed under (prevents a 'true on R+ only'
    relation from being used on all of R). ``manifest_hash`` is derived, not supplied."""

    domain_id: DomainId = "R"
    variables: dict[str, VarType] = field(default_factory=dict)
    predicates: tuple[str, ...] = ()
    branch_policy: Literal["principal", "real", "explicit"] = "principal"
    convergence: Optional[tuple[str, ...]] = None

    def manifest_hash(self) -> str:
        payload = json.dumps(
            {
                "domain_id": self.domain_id,
                "variables": dict(sorted(self.variables.items())),
                "predicates": sorted(self.predicates),
                "branch_policy": self.branch_policy,
                "convergence": sorted(self.convergence) if self.convergence else None,
            },
            sort_keys=True,
        )
        return _sha(payload)


@dataclass(frozen=True)
class IdentityClaim:
    claim_id: str
    lhs: str
    rhs: str
    manifest: AssumptionManifest
    fingerprint: Optional[str] = None
    fp_tier: Optional[FpTier] = None


@dataclass(frozen=True)
class SearchReceipt:
    """Coverage-bounded prior-art result. ``hits==0`` means 'none found in this corpus
    within this bound', never absolute novelty (PLAN B5 honesty)."""

    query_fp: str
    hits: int
    nearest_distance: float
    coverage_bound: str


@dataclass(frozen=True)
class FalsificationReceipt:
    samples_tested: int
    witness: Optional[dict[str, float]]
    passed: bool


@dataclass(frozen=True)
class IdentityArtifact:
    claim: IdentityClaim
    status: Status
    promotion: str
    search: Optional[SearchReceipt]
    falsify: Optional[FalsificationReceipt]
    severity: float
    proof_tier: int
    lean_statement: str
    note: str = ""
    quelle: str = "gen.identity_research.assess_identity (math-research branch, first stone)"


def _make_symbols(manifest: AssumptionManifest) -> dict[str, sp.Symbol]:
    kw_by_type: dict[str, dict] = {
        "real": {"real": True},
        "positive": {"positive": True},
        "integer": {"integer": True},
        "complex": {"complex": True},
    }
    return {n: sp.Symbol(n, **kw_by_type[t]) for n, t in manifest.variables.items()}


def _parse(expr: str, syms: dict[str, sp.Symbol]) -> sp.Expr:
    """Parse an expression against the manifest's symbols. Raises on bad input or on a
    free symbol not declared in the manifest (no silent guessing of variable nature)."""
    e = sp.sympify(expr, locals=syms, rational=True)
    undeclared = {s.name for s in e.free_symbols} - set(syms)
    if undeclared:
        raise ValueError(f"undeclared free symbols {sorted(undeclared)} (not in manifest.variables)")
    return e


def fingerprint(lhs: sp.Expr, rhs: sp.Expr, manifest_hash: str) -> tuple[FpTier, str]:
    """Two-bucket canonical fingerprint. Merge ONLY within 'proved_equal' + same manifest.
    Errs toward 'not_proven_equal' — a false split is harmless, a false merge is forbidden."""
    diff = sp.powsimp(sp.expand_trig(lhs - rhs), combine="all", force=True)
    proved_zero = False
    try:
        if diff == 0 or sp.simplify(diff) == 0:
            proved_zero = True
        elif bool(lhs.equals(rhs)):  # may be None (undecided) -> falsy -> no merge
            proved_zero = True
    except Exception:
        proved_zero = False
    if proved_zero:
        return "proved_equal", _sha(manifest_hash + "|0")

    # Unevaluated integrals/sums/limits or undefined functions cannot be safely canonicalised.
    if diff.has(sp.Integral, sp.Sum, sp.Product, sp.Limit, sp.core.function.AppliedUndef):
        return "not_proven_equal", _sha(manifest_hash + "|raw|" + sp.srepr(lhs) + "|" + sp.srepr(rhs))

    try:
        terms = sp.expand(diff).as_ordered_terms()
        canon = "+".join(sp.srepr(t) for t in terms)
        return "structural", _sha(manifest_hash + "|s|" + canon)
    except Exception:
        return "not_proven_equal", _sha(manifest_hash + "|raw|" + sp.srepr(lhs) + "|" + sp.srepr(rhs))


def _sample_points(manifest: AssumptionManifest, syms: dict[str, sp.Symbol], n_samples: int):
    """Deterministic sample points over the domain that satisfy all predicates."""
    anchors = {
        "R": _REAL_ANCHORS, "C": _REAL_ANCHORS, "R+": _POS_ANCHORS,
        "Z": _INT_ANCHORS, "N": _NAT_ANCHORS,
    }[manifest.domain_id]
    names = list(syms)
    if not names:
        return [{}]
    preds = [sp.sympify(p, locals=syms) for p in manifest.predicates]

    points: list[dict[str, float]] = []
    if len(names) == 1:
        candidates = ({names[0]: v} for v in anchors)
    else:
        # bounded cartesian product over a reduced anchor set to stay deterministic + cheap
        reduced = anchors[:: max(1, len(anchors) // 6)] or anchors
        candidates = []
        # two variables max for v1; more declared vars still work via diagonal sampling
        if len(names) == 2:
            for a in reduced:
                for b in reduced:
                    candidates.append({names[0]: a, names[1]: b})
        else:
            for a in anchors:
                candidates.append({n: a for n in names})  # diagonal
        candidates = iter(candidates)

    for pt in candidates:
        subs = {syms[n]: v for n, v in pt.items()}
        if all(bool(p.subs(subs)) for p in preds):
            points.append(pt)
        if len(points) >= n_samples:
            break
    return points


def falsify(
    lhs: sp.Expr, rhs: sp.Expr, manifest: AssumptionManifest, syms: dict[str, sp.Symbol],
    *, n_samples: int = 500, tol: float = 1e-9,
) -> FalsificationReceipt:
    """Search for a counterexample on a deterministic grid. A single point with
    |lhs-rhs| > tol REFUTES the identity (impossibility is provable; possibility is not)."""
    diff = lhs - rhs
    pts = _sample_points(manifest, syms, n_samples)
    tested = 0
    for pt in pts:
        subs = {syms[n]: sp.nsimplify(v) if float(v).is_integer() else sp.Float(v) for n, v in pt.items()}
        try:
            val = complex(diff.subs(subs).evalf())
        except Exception:
            continue  # singular/undefined point — skip, do not count as a test
        if not (math.isfinite(val.real) and math.isfinite(val.imag)):
            continue
        tested += 1
        if abs(val) > tol:
            return FalsificationReceipt(samples_tested=tested, witness={k: float(v) for k, v in pt.items()}, passed=False)
    return FalsificationReceipt(samples_tested=tested, witness=None, passed=True)


def _severity(proof_tier: int, samples: int, domain_id: str, raw_diff_ops: int, refuted: bool) -> float:
    """0 if refuted. Otherwise rises with proof rigor, samples, domain coverage, and
    INFORMATIVENESS (count_ops of the raw, unsimplified difference) — so a near-tautology
    (x==x, raw_diff_ops=0) scores ~0 while a substantive identity scores high. This is the
    correction to the naive '1/complexity' which would reward trivial identities."""
    if refuted:
        return 0.0
    informativeness = math.log1p(raw_diff_ops)
    return round(proof_tier * math.log1p(samples) * _DOMAIN_FRACTION.get(domain_id, 0.5) * informativeness, 4)


def _lean_statement(lhs: str, rhs: str, manifest: AssumptionManifest) -> str:
    binders = " ".join(f"({n} : {('Int' if t == 'integer' else 'Real')})" for n, t in sorted(manifest.variables.items()))
    hyps = "".join(f" (h{i} : {p})" for i, p in enumerate(manifest.predicates))
    return f"theorem genesis_identity {binders}{hyps} : ({lhs}) = ({rhs}) := by admit"


def assess_identity(
    claim_id: str, lhs: str, rhs: str, manifest: AssumptionManifest,
    *, novelty_index: Optional[set[str]] = None, n_samples: int = 500, tol: float = 1e-9,
) -> IdentityArtifact:
    """Run the math-research gate sequence end-to-end:
    PROPOSED -> GATE-DATA (parse+manifest) -> GATE-FINGERPRINT -> GATE-FALSIFICATION
    -> GATE-NOVELTY -> honest status + severity. ADMITTED-novel only when every gate is green.
    """
    syms = _make_symbols(manifest)
    mh = manifest.manifest_hash()
    lean = _lean_statement(lhs, rhs, manifest)

    # GATE-DATA
    try:
        e_lhs = _parse(lhs, syms)
        e_rhs = _parse(rhs, syms)
    except Exception as exc:
        claim = IdentityClaim(claim_id, lhs, rhs, manifest)
        return IdentityArtifact(
            claim=claim, status="INCONCLUSIVE", promotion="PROPOSED->GATE-DATA(failed)",
            search=None, falsify=None, severity=0.0, proof_tier=0, lean_statement=lean,
            note=f"parse/manifest failure: {type(exc).__name__}: {exc}",
        )

    # GATE-FINGERPRINT
    fp_tier, fp = fingerprint(e_lhs, e_rhs, mh)
    claim = IdentityClaim(claim_id, lhs, rhs, manifest, fingerprint=fp, fp_tier=fp_tier)

    # GATE-FALSIFICATION
    fr = falsify(e_lhs, e_rhs, manifest, syms, n_samples=n_samples, tol=tol)
    if not fr.passed:
        return IdentityArtifact(
            claim=claim, status="REFUTED",
            promotion="PROPOSED->GATE-DATA->GATE-FINGERPRINT->GATE-FALSIFICATION(refuted)",
            search=None, falsify=fr, severity=0.0,
            proof_tier=(2 if fp_tier == "proved_equal" else (1 if fp_tier == "structural" else 0)),
            lean_statement=lean, note="counterexample found — identity is false in this manifest",
        )
    if fr.samples_tested == 0:
        return IdentityArtifact(
            claim=claim, status="INCONCLUSIVE",
            promotion="PROPOSED->GATE-DATA->GATE-FINGERPRINT->GATE-FALSIFICATION(no evaluable point)",
            search=None, falsify=fr, severity=0.0, proof_tier=0, lean_statement=lean,
            note="no evaluable sample point in domain under predicates",
        )

    # proof tier: proved_equal+survived = 3; proved_equal only = 2; structural+survived = 1
    proof_tier = 3 if fp_tier == "proved_equal" else (1 if fp_tier == "structural" else 0)

    # GATE-NOVELTY (v1 stub: exact-fingerprint index lookup, coverage-bounded)
    index = novelty_index or set()
    hits = 1 if fp in index else 0
    receipt = SearchReceipt(
        query_fp=fp, hits=hits, nearest_distance=0.0 if hits else 1.0,
        coverage_bound="v1-fixture-index (no live OEIS/OpenAlex)",
    )
    raw_ops = int(sp.count_ops(e_lhs - e_rhs))
    sev = _severity(proof_tier, fr.samples_tested, manifest.domain_id, raw_ops, refuted=False)

    if hits > 0:
        return IdentityArtifact(
            claim=claim, status="SURVIVED_KNOWN",
            promotion="...->GATE-FALSIFICATION(survived)->GATE-NOVELTY(known)",
            search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
            note="rediscovered — matches prior art in the index (valid output, cite the source)",
        )
    return IdentityArtifact(
        claim=claim, status="SURVIVED_NOVEL",
        promotion="...->GATE-FALSIFICATION(survived)->GATE-NOVELTY(novel)->NOVELTY_CLEARED",
        search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
        note="no prior art found within coverage bound; Lean statement recorded, proof ADMITTED",
    )
