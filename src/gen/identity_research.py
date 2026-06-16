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

import mpmath
import sympy as sp

DomainId = Literal["R", "R+", "C", "Z", "N"]
VarType = Literal["real", "positive", "integer", "complex"]
FpTier = Literal["proved_equal", "structural", "not_proven_equal"]
Status = Literal["REFUTED", "INCONCLUSIVE", "SURVIVED_KNOWN", "SURVIVED_NOVEL"]

# Rough fraction of the relevant universe a domain's sampling can cover — feeds severity
# so an identity verified on all of R outranks one only checked on a sparse integer window.
_DOMAIN_FRACTION: dict[str, float] = {"R": 1.0, "C": 1.0, "R+": 0.5, "Z": 0.4, "N": 0.25}

# Deterministic sample anchors as EXACT sympy numbers (reproducibility — Kernprinzip 5;
# never random()). Rational anchors are evaluated exactly; the irrational anchors
# (sqrt2, pi, E) go through rigorous mpmath interval arithmetic. For ANALYTIC identities
# on a connected set, agreement on all rationals implies agreement everywhere (rationals
# are dense) — so the rational grid cannot miss an 'irrational-only' counterexample; the
# real residual gap is measure-zero / non-analytic (floor, piecewise) cases.
_REAL_ANCHORS = (
    sp.Integer(-3), sp.Integer(-2), sp.Rational(-3, 2), sp.Integer(-1), sp.Rational(-1, 2),
    sp.Rational(-1, 4), sp.Rational(1, 4), sp.Rational(1, 2), sp.Integer(1), sp.Rational(3, 2),
    sp.Integer(2), sp.Integer(3), sp.Integer(5), sp.sqrt(2), sp.pi, sp.E,
)
_POS_ANCHORS = tuple(a for a in _REAL_ANCHORS if a.is_positive)
_INT_ANCHORS = tuple(sp.Integer(i) for i in range(-6, 13))
_NAT_ANCHORS = tuple(sp.Integer(i) for i in range(0, 19))


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


MatchKind = Literal["REDISCOVERED", "NEAR_DUPLICATE", "NOVEL"]


@dataclass(frozen=True)
class IdentityClaim:
    claim_id: str
    lhs: str
    rhs: str
    manifest: AssumptionManifest
    fingerprint: Optional[str] = None       # truth_fp: proves 'are lhs,rhs equal' (|0 collapse)
    fp_tier: Optional[FpTier] = None
    novelty_key: Optional[str] = None        # statement identity (structural, NOT truth)


@dataclass(frozen=True)
class SearchReceipt:
    """Coverage-bounded prior-art result. ``hits==0`` means 'none found in this corpus
    within this bound', never absolute novelty (PLAN B5 honesty).

    REDISCOVERED is decided on the ``novelty_key`` (statement identity), never on the
    truth-fingerprint — the latter collapses every true identity under a manifest to |0
    and would falsely rediscover every new theorem (locked with co-architect)."""

    query_novelty_key: str
    match_kind: MatchKind
    hits: int
    nearest_distance: float                  # 0.0 = exact rediscovery, 1.0 = no proximity
    corpora_checked: tuple[str, ...]
    coverage_bound: str
    matched_claim_id: Optional[str] = None


@dataclass(frozen=True)
class IndexedIdentity:
    """One prior-art record. Stores BOTH keys: ``novelty_key`` (statement identity, used
    for REDISCOVERED) and ``truth_fp`` (equality witness). ``term_canon`` is a JSON-friendly
    sorted tuple of structural term reprs for the NEAR_DUPLICATE Jaccard check."""

    novelty_key: str
    truth_fp: str
    fp_tier: FpTier
    manifest_hash: str
    claim_id: str
    lhs: str
    rhs: str
    term_canon: tuple[str, ...]
    corpus_id: str = "genesis-local-v1"

    def content_address(self) -> str:
        return _sha(json.dumps({
            "novelty_key": self.novelty_key, "truth_fp": self.truth_fp,
            "fp_tier": self.fp_tier, "manifest_hash": self.manifest_hash,
            "lhs": self.lhs, "rhs": self.rhs, "corpus_id": self.corpus_id,
        }, sort_keys=True))


class NoveltyIndex:
    """Local, persistable prior-art index keyed by ``novelty_key``. Pluggable: a live
    arxiv/OEIS backend can later register under another ``corpus_id`` with the SAME
    semantics. Match rule (conservative — no fuzzy merge, locked with co-architect):

    1. REDISCOVERED  iff an entry shares the exact ``novelty_key`` (same statement+manifest).
    2. NEAR_DUPLICATE iff a structural-tier entry under the same manifest has Jaccard term
       overlap >= 0.85 but a different novelty_key — FLAG only, status stays NOVEL.
    3. NOVEL otherwise (within the checked corpora's coverage bound).
    """

    NEAR_DUP_JACCARD = 0.85

    def __init__(self, corpus_id: str = "genesis-local-v1") -> None:
        self.corpus_id = corpus_id
        self._by_key: dict[str, IndexedIdentity] = {}
        self._all: list[IndexedIdentity] = []

    @staticmethod
    def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 1.0
        union = sa | sb
        return len(sa & sb) / len(union) if union else 0.0

    def search(self, novelty_key: str, manifest_hash: str, fp_tier: FpTier,
               term_canon: tuple[str, ...]) -> SearchReceipt:
        bound = f"exact novelty_key in [{self.corpus_id}] (+structural Jaccard>={self.NEAR_DUP_JACCARD})"
        hit = self._by_key.get(novelty_key)
        if hit is not None:
            return SearchReceipt(novelty_key, "REDISCOVERED", 1, 0.0, (self.corpus_id,), bound, hit.claim_id)
        if fp_tier == "structural":
            best, best_j = None, 0.0
            for e in self._all:
                if e.manifest_hash == manifest_hash and e.fp_tier == "structural":
                    j = self._jaccard(term_canon, e.term_canon)
                    if j > best_j:
                        best, best_j = e, j
            if best is not None and best_j >= self.NEAR_DUP_JACCARD:
                return SearchReceipt(novelty_key, "NEAR_DUPLICATE", 0, round(1.0 - best_j, 4),
                                     (self.corpus_id,), bound, best.claim_id)
        return SearchReceipt(novelty_key, "NOVEL", 0, 1.0, (self.corpus_id,), bound, None)

    def register(self, entry: IndexedIdentity) -> str:
        # first-writer-wins on novelty_key (the original discovery keeps priority)
        if entry.novelty_key not in self._by_key:
            self._by_key[entry.novelty_key] = entry
            self._all.append(entry)
        return entry.content_address()


@dataclass(frozen=True)
class FalsificationReceipt:
    samples_tested: int
    witness: Optional[dict[str, float]]
    passed: bool
    refutation_mode: Optional[Literal["exact", "interval"]] = None
    interval_prec_dps: int = 30
    witness_residual: Optional[str] = None
    counts: dict[str, int] = field(default_factory=dict)
    sampling_note: str = "rational grid + irrational anchors (sqrt2, pi, e)"
    coverage_claim: str = "finite-grid falsification only; SURVIVED != universal identity"


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


def _statement_novelty_key(lhs: sp.Expr, rhs: sp.Expr, manifest_hash: str) -> str:
    """Structural canonical key of the STATEMENT itself (NOT the truth-fingerprint).

    Uses sympy's canonical srepr (commutative args are auto-ordered), WITHOUT simplify():
    x+y==y+x -> same key (same statement); sin^2+cos^2==1 vs (x+1)^2==... -> different keys
    (different theorems). False-split on non-expanded equivalents is consciously accepted
    (conservative); a false merge would require literally identical structure (= same claim).
    """
    return _sha(manifest_hash + "|stmt|" + sp.srepr(lhs) + "=" + sp.srepr(rhs))


def _term_canon(lhs: sp.Expr, rhs: sp.Expr) -> tuple[str, ...]:
    """JSON-friendly sorted set of structural term reprs (for the NEAR_DUPLICATE Jaccard)."""
    terms: set[str] = set()
    for side in (lhs, rhs):
        try:
            for t in sp.Add.make_args(sp.expand(side)):
                terms.add(sp.srepr(t))
        except Exception:
            terms.add(sp.srepr(side))
    return tuple(sorted(terms))


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


class _IvUnsupported(Exception):
    """A node the interval enclosure cannot rigorously handle — that point is skipped
    (never silently treated as consistent or refuted)."""


def _iv_enclose(expr: sp.Expr, env: dict):
    """Rigorous mpmath interval enclosure of ``expr`` with symbols bound to interval
    values in ``env``. Raises _IvUnsupported on any node it cannot bound rigorously."""
    iv = mpmath.iv
    if expr.is_Integer:
        return iv.mpf(int(expr))
    if expr.is_Rational:
        return iv.mpf(int(expr.p)) / iv.mpf(int(expr.q))
    if expr.is_Float:
        return iv.mpf(str(expr))
    if expr is sp.pi:
        return iv.pi
    if expr is sp.E:
        return iv.e
    if expr.is_Symbol:
        if expr in env:
            return env[expr]
        raise _IvUnsupported(f"unbound symbol {expr}")
    if expr.is_Add:
        acc = iv.mpf(0)
        for a in expr.args:
            acc = acc + _iv_enclose(a, env)
        return acc
    if expr.is_Mul:
        acc = iv.mpf(1)
        for a in expr.args:
            acc = acc * _iv_enclose(a, env)
        return acc
    if expr.is_Pow:
        base = _iv_enclose(expr.base, env)
        e = expr.exp
        if e.is_Integer:
            return base ** int(e)
        if e == sp.Rational(1, 2):
            return iv.sqrt(base)
        if e == sp.Rational(-1, 2):
            return iv.mpf(1) / iv.sqrt(base)
        raise _IvUnsupported(f"non-integer/half power {e}")
    fn = {sp.sin: iv.sin, sp.cos: iv.cos, sp.tan: iv.tan, sp.exp: iv.exp, sp.log: iv.log}.get(expr.func)
    if fn is not None and len(expr.args) == 1:
        return fn(_iv_enclose(expr.args[0], env))
    raise _IvUnsupported(f"unsupported node {expr.func}")


def falsify(
    lhs: sp.Expr, rhs: sp.Expr, manifest: AssumptionManifest, syms: dict[str, sp.Symbol],
    *, n_samples: int = 500, prec_dps: int = 30,
) -> FalsificationReceipt:
    """Search for a counterexample on a deterministic grid of EXACT sympy points.

    Rigorous, no float tolerance: a rational/algebraic point is checked exactly
    (``is_zero`` True/False); a transcendental point is enclosed with mpmath interval
    arithmetic. A point that is rigorously nonzero (exact != 0, or an interval excluding 0)
    REFUTES with a witness. SURVIVED means only 'no counterexample in this finite set',
    never a proof of universality (impossibility is provable, possibility is not)."""
    mpmath.iv.dps = prec_dps
    diff = lhs - rhs
    pts = _sample_points(manifest, syms, n_samples)
    counts = {"exact_zero": 0, "exact_nonzero": 0, "interval_excludes_0": 0,
              "interval_inconclusive": 0, "skipped_unsupported": 0}
    tested = 0
    for pt in pts:
        val = diff.subs({syms[n]: v for n, v in pt.items()})
        witness = {n: float(v) for n, v in pt.items()}
        # EXACT path (rational / algebraic)
        if val.is_number:
            z = val.is_zero
            if z is True:
                counts["exact_zero"] += 1
                tested += 1
                continue
            if z is False:
                counts["exact_nonzero"] += 1
                tested += 1
                return FalsificationReceipt(tested, witness, False, "exact", prec_dps, str(val), counts)
        # INTERVAL path (transcendental / exact-undecided)
        try:
            env = {syms[n]: _iv_enclose(v, {}) for n, v in pt.items()}
            r = _iv_enclose(diff, env)
            excludes0 = bool(r.b < 0) or bool(r.a > 0)
        except Exception:
            counts["skipped_unsupported"] += 1
            continue
        tested += 1
        if excludes0:
            counts["interval_excludes_0"] += 1
            return FalsificationReceipt(tested, witness, False, "interval", prec_dps, f"[{r.a}, {r.b}]", counts)
        counts["interval_inconclusive"] += 1
    return FalsificationReceipt(tested, None, True, None, prec_dps, None, counts)


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
    *, novelty_index: Optional["NoveltyIndex"] = None, register: bool = True,
    n_samples: int = 500, prec_dps: int = 30,
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

    # GATE-FINGERPRINT (truth_fp = equality witness; novelty_key = statement identity)
    fp_tier, fp = fingerprint(e_lhs, e_rhs, mh)
    nkey = _statement_novelty_key(e_lhs, e_rhs, mh)
    term_canon = _term_canon(e_lhs, e_rhs)
    claim = IdentityClaim(claim_id, lhs, rhs, manifest, fingerprint=fp, fp_tier=fp_tier, novelty_key=nkey)

    # GATE-FALSIFICATION
    fr = falsify(e_lhs, e_rhs, manifest, syms, n_samples=n_samples, prec_dps=prec_dps)
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

    # GATE-NOVELTY (coverage-bounded; decided on novelty_key, never the truth_fp)
    index = novelty_index if novelty_index is not None else NoveltyIndex()
    receipt = index.search(nkey, mh, fp_tier, term_canon)
    raw_ops = int(sp.count_ops(e_lhs - e_rhs))
    sev = _severity(proof_tier, fr.samples_tested, manifest.domain_id, raw_ops, refuted=False)

    if register:
        index.register(IndexedIdentity(
            novelty_key=nkey, truth_fp=fp, fp_tier=fp_tier, manifest_hash=mh,
            claim_id=claim_id, lhs=lhs, rhs=rhs, term_canon=term_canon, corpus_id=index.corpus_id,
        ))

    if receipt.match_kind == "REDISCOVERED":
        return IdentityArtifact(
            claim=claim, status="SURVIVED_KNOWN",
            promotion="...->GATE-FALSIFICATION(survived)->GATE-NOVELTY(rediscovered)",
            search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
            note=f"rediscovered — same statement as prior art {receipt.matched_claim_id!r} (cite it)",
        )
    near = " (NEAR_DUPLICATE of prior art — flagged, still novel)" if receipt.match_kind == "NEAR_DUPLICATE" else ""
    return IdentityArtifact(
        claim=claim, status="SURVIVED_NOVEL",
        promotion="...->GATE-FALSIFICATION(survived)->GATE-NOVELTY(novel)->NOVELTY_CLEARED",
        search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
        note=f"no exact prior art within coverage bound; Lean statement recorded, proof ADMITTED{near}",
    )
