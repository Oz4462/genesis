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
import itertools
import json
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional, Protocol, runtime_checkable

import mpmath
import sympy as sp

DomainId = Literal["R", "R+", "C", "Z", "N"]
VarType = Literal["real", "positive", "integer", "complex"]
FpTier = Literal["proved_equal", "structural", "not_proven_equal"]
Status = Literal[
    "REFUTED", "INCONCLUSIVE", "SURVIVED_KNOWN", "SURVIVED_NOVEL", "SURVIVED_NOVELTY_UNCHECKED"
]

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
    sp.Rational(-1, 4), sp.Integer(0), sp.Rational(1, 4), sp.Rational(1, 2), sp.Integer(1),
    sp.Rational(3, 2), sp.Integer(2), sp.Integer(3), sp.Integer(5), sp.sqrt(2), sp.pi, sp.E,
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


MatchKind = Literal["REDISCOVERED", "NEAR_DUPLICATE", "NOVEL", "PRIOR_ART_UNCHECKED"]


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
               term_canon: tuple[str, ...], query_text: str = "") -> SearchReceipt:
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


@runtime_checkable
class NoveltyBackend(Protocol):
    """Uniform prior-art interface — local index or online corpus, same SearchReceipt."""
    corpus_id: str

    def search(self, novelty_key: str, manifest_hash: str, fp_tier: FpTier,
               term_canon: tuple[str, ...], query_text: str = "") -> SearchReceipt: ...

    def register(self, entry: IndexedIdentity) -> str: ...


def _text_jaccard(a: str, b: str) -> float:
    def toks(s: str) -> set[str]:
        for ch in "=()+-*/^,":
            s = s.replace(ch, " ")
        return {t for t in s.lower().split() if t}
    ta, tb = toks(a), toks(b)
    if not ta and not tb:
        return 1.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


def openalex_fetch(query_text: str, *, max_hits: int = 5, timeout: float = 8.0) -> list[str]:
    """Real OpenAlex works search (no auth). Returns hit titles. Raises on ANY network
    failure so the caller turns it into PRIOR_ART_UNCHECKED (never a false NOVEL)."""
    import json as _json
    import urllib.parse
    import urllib.request

    url = ("https://api.openalex.org/works?per-page=" + str(max_hits)
           + "&search=" + urllib.parse.quote_plus(query_text))
    req = urllib.request.Request(url, headers={"User-Agent": "genesis-research/0.1 (mailto:research@genesis.local)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https, fixed host)
        data = _json.loads(resp.read().decode("utf-8"))
    return [(w.get("title") or "") for w in data.get("results", [])]


class OnlineNoveltyBackend:
    """Online prior-art via an injected ``fetch_fn(query_text, max_hits=...) -> [titles]``.

    Honest contract (locked with co-architect): full-text search can NEVER prove
    REDISCOVERED (exact statement identity) nor absolute novelty. A close text match is
    at most NEAR_DUPLICATE (a flag); no match is NOVEL only WITHIN this corpus' bound;
    any fetch failure is PRIOR_ART_UNCHECKED — never a false NOVEL.
    """

    NEAR_DUP_TEXT_JACCARD = 0.85

    def __init__(self, fetch_fn: Callable[..., list[str]] = openalex_fetch, *,
                 corpus_id: str = "openalex:title+abstract", max_hits: int = 5) -> None:
        self.fetch_fn = fetch_fn
        self.corpus_id = corpus_id
        self.max_hits = max_hits

    def search(self, novelty_key: str, manifest_hash: str, fp_tier: FpTier,
               term_canon: tuple[str, ...], query_text: str = "") -> SearchReceipt:
        bound = (f"sources=[{self.corpus_id}]; max_hits={self.max_hits}; text search => "
                 "NEAR_DUPLICATE at best, never REDISCOVERED; hits==0 => no match WITHIN "
                 "this bound (not absolute novelty)")
        try:
            hits = self.fetch_fn(query_text, max_hits=self.max_hits)
        except Exception as exc:
            return SearchReceipt(novelty_key, "PRIOR_ART_UNCHECKED", 0, 1.0, (),
                                 bound + f" | FETCH FAILED ({type(exc).__name__}) — offline/timeout", None)
        if not hits:
            return SearchReceipt(novelty_key, "NOVEL", 0, 1.0, (self.corpus_id,), bound, None)
        best = max((_text_jaccard(query_text, h) for h in hits), default=0.0)
        if best >= self.NEAR_DUP_TEXT_JACCARD:
            return SearchReceipt(novelty_key, "NEAR_DUPLICATE", 0, round(1.0 - best, 4),
                                 (self.corpus_id,), bound, None)
        return SearchReceipt(novelty_key, "NOVEL", 0, 1.0, (self.corpus_id,), bound, None)

    def register(self, entry: IndexedIdentity) -> str:
        return entry.content_address()  # read-only corpus — no-op write


_MATCH_RANK = {"REDISCOVERED": 3, "NEAR_DUPLICATE": 2, "PRIOR_ART_UNCHECKED": 1, "NOVEL": 0}


class ChainedNoveltyBackend:
    """Consults several backends and returns the STRONGEST verdict
    (REDISCOVERED > NEAR_DUPLICATE > PRIOR_ART_UNCHECKED > NOVEL), merging coverage.
    PRIOR_ART_UNCHECKED outranks NOVEL: if an online corpus could not be checked we do
    NOT claim novelty just because the local index was empty. register() -> first NoveltyIndex."""

    def __init__(self, backends, corpus_id: str = "chained") -> None:
        self.backends = list(backends)
        self.corpus_id = corpus_id

    def search(self, novelty_key: str, manifest_hash: str, fp_tier: FpTier,
               term_canon: tuple[str, ...], query_text: str = "") -> SearchReceipt:
        receipts = [b.search(novelty_key, manifest_hash, fp_tier, term_canon, query_text)
                    for b in self.backends]
        best = max(receipts, key=lambda r: _MATCH_RANK.get(r.match_kind, 0))
        corpora = tuple(c for r in receipts for c in r.corpora_checked)
        bound = " || ".join(r.coverage_bound for r in receipts)
        return SearchReceipt(novelty_key, best.match_kind, best.hits, best.nearest_distance,
                             corpora, bound, best.matched_claim_id)

    def register(self, entry: IndexedIdentity) -> str:
        for b in self.backends:
            if isinstance(b, NoveltyIndex):
                return b.register(entry)
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
    proof: Optional["ProofCertificate"] = None
    note: str = ""
    quelle: str = "gen.identity_research.assess_identity (math-research branch, first stone)"


ProofMethod = Literal["z3_qfnra", "cas_simplify", "cas_equals", "grid_only", "none"]
LeanStatus = Literal["admitted", "cas_certified", "z3_certified"]


@dataclass(frozen=True)
class ProofCertificate:
    """How an identity's truth was established. CAS-certified is NOT Lean-kernel-verified:
    sympy simplify is a heuristic, not a proof calculus, so a CAS claim is only made inside
    a safe fragment (no Integral/Sum/Limit/undefined-function/Float) AND only when the grid
    also survived (defence-in-depth against a sympy false-zero). A grid refutation always
    overrides CAS. The Lean statement stays `admit` until a real kernel checks it."""

    method: ProofMethod
    deductively_proved: bool
    cas_check: str
    lean_statement: str
    lean_status: LeanStatus
    notes: str = "SymPy CAS within a safe fragment — NOT machine-checked by a Lean kernel"


_CAS_UNSAFE = (sp.Integral, sp.Sum, sp.Product, sp.Limit, sp.core.function.AppliedUndef)


def prove_identity(e_lhs: sp.Expr, e_rhs: sp.Expr, manifest: Optional[AssumptionManifest] = None,
                   *, grid_passed: bool, lean_statement: str, kernels=None) -> ProofCertificate:
    """Deductive check. Order (Grok-locked): grid refutation (caller) > proof KERNEL (z3
    QF_NRA — a real decision procedure for the polynomial/rational fragment, stronger than
    CAS) > CAS simplify (heuristic, safe fragment) > admitted.

    ``manifest`` is needed for the z3 kernel (variable domains); when omitted the kernel
    step is skipped and only the CAS path runs."""
    if not grid_passed:
        return ProofCertificate("none", False, "grid refuted/empty -> no proof", lean_statement, "admitted")

    # 1) real proof kernels (rigorous decision procedure — stricter than CAS)
    if manifest is not None:
        from .proof_kernels import Z3IdentityKernel
        for kernel in (kernels if kernels is not None else (Z3IdentityKernel(),)):
            res = kernel.check(e_lhs, e_rhs, variables=manifest.variables,
                               domain_id=manifest.domain_id, predicates=manifest.predicates)
            if res.status == "proved":
                status = "z3_certified" if res.kernel == "z3_qfnra" else "cas_certified"
                return ProofCertificate(
                    "z3_qfnra" if res.kernel == "z3_qfnra" else "cas_simplify", True,
                    f"{res.kernel}: {res.detail}", lean_statement, status,
                    notes=f"{res.kernel} decision procedure (rigorous) — still NOT a Lean-kernel proof",
                )

    # 2) CAS fallback (heuristic, whitelist-guarded)
    diff = sp.expand_trig(sp.expand(e_lhs - e_rhs))
    if diff.has(*_CAS_UNSAFE) or diff.atoms(sp.Float):
        return ProofCertificate("grid_only", False, "outside safe CAS fragment (integral/sum/float/undef)",
                                lean_statement, "admitted")
    try:
        if sp.simplify(diff, rational=True) == 0:
            return ProofCertificate("cas_simplify", True, "simplify(lhs-rhs, rational=True) == 0",
                                    lean_statement, "cas_certified")
    except Exception:
        pass
    try:
        if e_lhs.equals(e_rhs) is True:
            return ProofCertificate("cas_equals", True, ".equals() == True (weaker CAS path)",
                                    lean_statement, "cas_certified",
                                    notes="weaker CAS path (.equals heuristic) — NOT Lean-kernel-verified")
    except Exception:
        pass
    return ProofCertificate("grid_only", False, "CAS did not establish equality (grid-survived only)",
                            lean_statement, "admitted")


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


Relation = Literal["eq", "ge", "gt", "le", "lt"]
_REL_SYM = {"eq": "=", "ge": ">=", "gt": ">", "le": "<=", "lt": "<"}


def _exact_verdict(relation: Relation, d) -> str:
    """'refute' | 'ok' | 'unknown' for an EXACT value d = lhs-rhs. The relation is the
    CLAIM (d eq/ge/gt/le/lt 0); 'refute' means the claim is rigorously violated at d."""
    if relation == "eq":
        z = d.is_zero
        return "ok" if z is True else ("refute" if z is False else "unknown")
    if relation == "ge":
        return "ok" if d.is_nonnegative else ("refute" if d.is_negative else "unknown")
    if relation == "gt":
        return "ok" if d.is_positive else ("refute" if d.is_nonpositive else "unknown")
    if relation == "le":
        return "ok" if d.is_nonpositive else ("refute" if d.is_positive else "unknown")
    if relation == "lt":
        return "ok" if d.is_negative else ("refute" if d.is_nonnegative else "unknown")
    return "unknown"


def _interval_verdict(relation: Relation, r) -> str:
    """'refute' | 'ok' | 'unknown' for an interval enclosure [a,b] of d. An interval that
    straddles the boundary is 'unknown' (never a false refutation — Grok-locked)."""
    a_pos, a_nonneg = bool(r.a > 0), bool(r.a >= 0)
    b_neg, b_nonpos = bool(r.b < 0), bool(r.b <= 0)
    if relation == "eq":
        return "refute" if (b_neg or a_pos) else "ok"
    if relation == "ge":   # claim d>=0; fails if d<0
        return "refute" if b_neg else ("ok" if a_nonneg else "unknown")
    if relation == "gt":   # claim d>0; fails if d<=0
        return "refute" if b_nonpos else ("ok" if a_pos else "unknown")
    if relation == "le":   # claim d<=0; fails if d>0
        return "refute" if a_pos else ("ok" if b_nonpos else "unknown")
    if relation == "lt":   # claim d<0; fails if d>=0
        return "refute" if a_nonneg else ("ok" if b_neg else "unknown")
    return "unknown"


def falsify(
    lhs: sp.Expr, rhs: sp.Expr, manifest: AssumptionManifest, syms: dict[str, sp.Symbol],
    *, relation: Relation = "eq", n_samples: int = 500, prec_dps: int = 30,
) -> FalsificationReceipt:
    """Search for a counterexample to ``lhs <relation> rhs`` on a deterministic grid of
    EXACT sympy points. Rigorous, no float tolerance: rational/algebraic points are checked
    exactly; transcendental points are enclosed with mpmath interval arithmetic. A point
    that rigorously VIOLATES the relation REFUTES with a witness; an interval straddling the
    boundary is inconclusive, never a false refutation. SURVIVED means only 'no counterexample
    in this finite set', never a proof of universality."""
    mpmath.iv.dps = prec_dps
    diff = lhs - rhs
    pts = _sample_points(manifest, syms, n_samples)
    counts = {"exact_ok": 0, "exact_refute": 0, "interval_ok": 0,
              "interval_refute": 0, "interval_unknown": 0, "skipped_unsupported": 0}
    tested = 0
    for pt in pts:
        val = diff.subs({syms[n]: v for n, v in pt.items()})
        witness = {n: float(v) for n, v in pt.items()}
        # EXACT path (rational / algebraic)
        if val.is_number:
            verdict = _exact_verdict(relation, val)
            if verdict == "refute":
                counts["exact_refute"] += 1
                tested += 1
                return FalsificationReceipt(tested, witness, False, "exact", prec_dps, str(val), counts)
            if verdict == "ok":
                counts["exact_ok"] += 1
                tested += 1
                continue
            # unknown -> fall through to interval
        # INTERVAL path (transcendental / exact-undecided)
        try:
            env = {syms[n]: _iv_enclose(v, {}) for n, v in pt.items()}
            r = _iv_enclose(diff, env)
            verdict = _interval_verdict(relation, r)
        except Exception:
            counts["skipped_unsupported"] += 1
            continue
        tested += 1
        if verdict == "refute":
            counts["interval_refute"] += 1
            return FalsificationReceipt(tested, witness, False, "interval", prec_dps, f"[{r.a}, {r.b}]", counts)
        counts["interval_ok" if verdict == "ok" else "interval_unknown"] += 1
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
    *, novelty_index: Optional["NoveltyBackend"] = None, register: bool = True,
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

    # GATE-PROOF (conservative CAS, distinct from the aggressive dedup fingerprint):
    # cas_certified (deductively proved in a safe fragment AND grid-survived) => tier 3,
    # otherwise grid-survived only => tier 1. CAS-certified is NOT Lean-kernel-verified.
    cert = prove_identity(e_lhs, e_rhs, manifest, grid_passed=True, lean_statement=lean)
    proof_tier = 3 if cert.deductively_proved else 1

    # GATE-NOVELTY (coverage-bounded; decided on novelty_key, never the truth_fp).
    # The backend may be the local index, an online corpus, or a chain of both.
    index = novelty_index if novelty_index is not None else NoveltyIndex()
    query_text = f"{lhs} = {rhs}"
    receipt = index.search(nkey, mh, fp_tier, term_canon, query_text)
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
            promotion="...->GATE-FALSIFICATION(survived)->GATE-PROOF->GATE-NOVELTY(rediscovered)",
            search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
            proof=cert,
            note=f"rediscovered — same statement as prior art {receipt.matched_claim_id!r} (cite it)",
        )
    if receipt.match_kind == "PRIOR_ART_UNCHECKED":
        return IdentityArtifact(
            claim=claim, status="SURVIVED_NOVELTY_UNCHECKED",
            promotion="...->GATE-FALSIFICATION(survived)->GATE-PROOF->GATE-NOVELTY(prior-art unchecked)",
            search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
            proof=cert,
            note="survived falsification but prior-art could NOT be checked (offline/timeout) — "
                 "novelty deliberately NOT claimed",
        )
    near = " (NEAR_DUPLICATE of prior art — flagged, still novel)" if receipt.match_kind == "NEAR_DUPLICATE" else ""
    return IdentityArtifact(
        claim=claim, status="SURVIVED_NOVEL",
        promotion="...->GATE-FALSIFICATION(survived)->GATE-PROOF->GATE-NOVELTY(novel)->NOVELTY_CLEARED",
        search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
        proof=cert,
        note=f"no exact prior art within coverage bound; proof={cert.lean_status}{near}",
    )


# =============================================================================
# Conjecture generator + auto-disproof (the research act): a parametrized family is
# instantiated over a FINITE structural-parameter grid; each instance is assessed and
# triaged. A family NEVER earns a 'proved' verdict — only finite-grid statistics plus a
# 'universal_candidate' flag meaning 'worth a real proof attempt', not a theorem
# (over-claim is structurally impossible). Designed + locked with the co-architect.
# =============================================================================

FamilyVerdict = Literal[
    "REFUTED_FAMILY", "PARTIALLY_REFUTED", "GRID_ALL_SURVIVED", "INCONCLUSIVE_DOMINANT"
]

_FAMILY_HONESTY = (
    "Explored a FINITE structural-parameter grid; survivors are candidate identities "
    "(ADMITTED, not proven universal), refuted are disproved instances. "
    "universal_candidate=True means 'worth a real proof attempt', never 'theorem proved'."
)


@dataclass(frozen=True)
class ConjectureTemplate:
    """A parametrized identity family. ``lhs_template``/``rhs_template`` are expressions
    over the manifest's free variables PLUS structural integer parameters in ``param_grid``
    (e.g. x is the free var, k/n are structural). Each grid point yields one concrete
    IdentityClaim. ``min_instances`` is the floor for a universal_candidate flag."""

    family_id: str
    lhs_template: str
    rhs_template: str
    param_grid: dict[str, tuple[int, ...]]
    manifest: AssumptionManifest
    min_instances: int = 8


@dataclass(frozen=True)
class FamilyReport:
    family_id: str
    lhs_template: str
    rhs_template: str
    grid_cardinality: int
    instances: tuple[dict, ...]
    refuted: tuple[str, ...]
    surviving_known: tuple[str, ...]
    surviving_novel: tuple[str, ...]
    inconclusive: tuple[str, ...]
    refuted_count: int
    survival_rate: float
    family_verdict: FamilyVerdict
    universal_candidate: bool
    honesty_epistemic: str = _FAMILY_HONESTY


def _subst_template(template: str, params: dict[str, int]) -> str:
    """Substitute structural integer parameters into a template, leaving the manifest's
    free variables symbolic. Returns a re-parseable sympy string."""
    expr = sp.sympify(template, rational=True)
    expr = expr.subs({sp.Symbol(k): sp.Integer(v) for k, v in params.items()})
    return str(expr)


def explore_family(
    template: ConjectureTemplate, *, novelty_index: Optional["NoveltyIndex"] = None,
    n_samples: int = 300, prec_dps: int = 30,
) -> FamilyReport:
    """Instantiate every grid point, assess each through a SHARED NoveltyIndex, and triage.
    The family verdict is finite-grid statistics only — never a proof."""
    index = novelty_index if novelty_index is not None else NoveltyIndex()
    names = sorted(template.param_grid)
    grids = [template.param_grid[n] for n in names]
    combos = list(itertools.product(*grids)) if names else [()]

    instances: list[dict] = []
    refuted: list[str] = []
    surviving_known: list[str] = []
    surviving_novel: list[str] = []
    inconclusive: list[str] = []

    for combo in combos:
        pmap = dict(zip(names, combo))
        cid = f"{template.family_id}[" + ",".join(f"{k}={v}" for k, v in pmap.items()) + "]"
        try:
            lhs = _subst_template(template.lhs_template, pmap)
            rhs = _subst_template(template.rhs_template, pmap)
        except Exception as exc:
            inconclusive.append(cid)
            instances.append({"params": pmap, "claim_id": cid, "status": "INCONCLUSIVE",
                              "novelty_kind": None, "note": f"template error: {exc}"})
            continue
        art = assess_identity(cid, lhs, rhs, template.manifest, novelty_index=index,
                              n_samples=n_samples, prec_dps=prec_dps)
        instances.append({
            "params": pmap, "claim_id": cid, "status": art.status,
            "novelty_kind": art.search.match_kind if art.search else None,
            "coverage_bound": art.search.coverage_bound if art.search else None,
            "severity": art.severity,
        })
        if art.status == "REFUTED":
            refuted.append(cid)
        elif art.status == "SURVIVED_KNOWN":
            surviving_known.append(cid)
        elif art.status == "SURVIVED_NOVEL":
            surviving_novel.append(cid)
        else:
            inconclusive.append(cid)

    n = len(combos)
    refuted_count = len(refuted)
    survived = len(surviving_known) + len(surviving_novel)
    inconclusive_count = len(inconclusive)
    survival_rate = round(survived / n, 4) if n else 0.0

    # total, deterministic verdict (refinement over the co-architect's draft: no gaps)
    if n > 0 and refuted_count == n:
        verdict: FamilyVerdict = "REFUTED_FAMILY"
    elif refuted_count > 0:
        verdict = "PARTIALLY_REFUTED"
    elif n > 0 and inconclusive_count == 0:
        verdict = "GRID_ALL_SURVIVED"
    else:
        verdict = "INCONCLUSIVE_DOMINANT"
    universal_candidate = verdict == "GRID_ALL_SURVIVED" and n >= template.min_instances

    return FamilyReport(
        family_id=template.family_id, lhs_template=template.lhs_template,
        rhs_template=template.rhs_template, grid_cardinality=n, instances=tuple(instances),
        refuted=tuple(refuted), surviving_known=tuple(surviving_known),
        surviving_novel=tuple(surviving_novel), inconclusive=tuple(inconclusive),
        refuted_count=refuted_count, survival_rate=survival_rate,
        family_verdict=verdict, universal_candidate=universal_candidate,
    )


# =============================================================================
# Pipeline seam (d-lite): persist research artifacts into the SHARED wissensbasis store
# — the same store the integrator/pipeline read — so the math-research branch is reachable
# from the rest of GENESIS, not an island. Full conductor/CLI/promotion wiring is d-full.
# =============================================================================

def _artifact_record(artifact: IdentityArtifact) -> dict:
    c = artifact.claim
    fr = artifact.falsify
    return {
        "type": "IdentityArtifact",
        "claim_id": c.claim_id, "lhs": c.lhs, "rhs": c.rhs,
        "status": artifact.status, "promotion": artifact.promotion,
        "proof_tier": artifact.proof_tier, "severity": artifact.severity,
        "truth_fp": c.fingerprint, "novelty_key": c.novelty_key, "fp_tier": c.fp_tier,
        "match_kind": artifact.search.match_kind if artifact.search else None,
        "coverage_bound": artifact.search.coverage_bound if artifact.search else None,
        "lean_statement": artifact.lean_statement,
        "proof_method": artifact.proof.method if artifact.proof else None,
        "lean_status": artifact.proof.lean_status if artifact.proof else None,
        "deductively_proved": artifact.proof.deductively_proved if artifact.proof else False,
        "refutation_mode": fr.refutation_mode if fr else None,
        "witness": fr.witness if fr else None,
        "samples_tested": fr.samples_tested if fr else 0,
        "note": artifact.note, "quelle": artifact.quelle,
    }


def persist_identity_artifact(artifact: IdentityArtifact) -> str:
    """Persist a research artifact into the shared wissensbasis store with provenance,
    returning its store key. Makes the branch's output durable + visible to the rest of
    GENESIS (the integrator/pipeline read the same store)."""
    from .wissensbasis.store import save_fragment

    # filesystem-safe key (the store writes <key>.json; ':' etc. are invalid on Windows)
    raw = f"identity_{artifact.claim.claim_id}_{artifact.claim.fingerprint or 'na'}"
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)
    save_fragment(
        _artifact_record(artifact), key=key, source="identity_research",
        quelle=f"gen.identity_research ({artifact.status}; truth_fp={artifact.claim.fingerprint})",
    )
    return key


def run_identity_research(
    claim_id: str, lhs: str, rhs: str, manifest: AssumptionManifest, *,
    novelty_index: Optional["NoveltyBackend"] = None, persist: bool = True,
    n_samples: int = 300, prec_dps: int = 30,
) -> tuple[IdentityArtifact, Optional[str]]:
    """Pipeline entrypoint: assess an identity and (by default) persist the artifact into
    the shared store. Returns (artifact, store_key | None)."""
    art = assess_identity(claim_id, lhs, rhs, manifest, novelty_index=novelty_index,
                          n_samples=n_samples, prec_dps=prec_dps)
    key = persist_identity_artifact(art) if persist else None
    return art, key


def assess_inequality(
    claim_id: str, lhs: str, rhs: str, relation: Relation, manifest: AssumptionManifest,
    *, novelty_index: Optional["NoveltyBackend"] = None, register: bool = True,
    n_samples: int = 500, prec_dps: int = 30,
) -> IdentityArtifact:
    """Assess a conjectured INEQUALITY ``lhs <relation> rhs`` (relation in ge|gt|le|lt).

    Same honest gate flow as identities, but there is no equality truth-fingerprint: a
    point that rigorously violates the relation REFUTES with a witness; SURVIVED means only
    'no counterexample on this finite grid' (never a proof). Interval straddling the boundary
    is inconclusive, never a false refutation."""
    if relation not in ("ge", "gt", "le", "lt"):
        raise ValueError(f"assess_inequality relation must be ge|gt|le|lt, got {relation!r}")
    syms = _make_symbols(manifest)
    mh = manifest.manifest_hash()
    rel = _REL_SYM[relation]
    binders = " ".join(f"({n} : {('Int' if t == 'integer' else 'Real')})"
                       for n, t in sorted(manifest.variables.items()))
    lean = f"theorem genesis_inequality {binders} : ({lhs}) {rel} ({rhs}) := by admit"

    try:
        e_lhs = _parse(lhs, syms)
        e_rhs = _parse(rhs, syms)
    except Exception as exc:
        claim = IdentityClaim(claim_id, lhs, rhs, manifest)
        return IdentityArtifact(claim=claim, status="INCONCLUSIVE", promotion="PROPOSED->GATE-DATA(failed)",
                                search=None, falsify=None, severity=0.0, proof_tier=0, lean_statement=lean,
                                note=f"parse/manifest failure: {type(exc).__name__}: {exc}")

    nkey = _sha(mh + "|ineq:" + relation + "|" + sp.srepr(e_lhs) + "|" + sp.srepr(e_rhs))
    term_canon = _term_canon(e_lhs, e_rhs)
    claim = IdentityClaim(claim_id, lhs, rhs, manifest, fingerprint=None,
                          fp_tier="not_proven_equal", novelty_key=nkey)

    fr = falsify(e_lhs, e_rhs, manifest, syms, relation=relation, n_samples=n_samples, prec_dps=prec_dps)
    if not fr.passed:
        return IdentityArtifact(claim=claim, status="REFUTED",
                                promotion="PROPOSED->GATE-DATA->GATE-FALSIFICATION(refuted)",
                                search=None, falsify=fr, severity=0.0, proof_tier=0, lean_statement=lean,
                                note=f"counterexample found — '{lhs} {rel} {rhs}' is false in this manifest")
    if fr.samples_tested == 0:
        return IdentityArtifact(claim=claim, status="INCONCLUSIVE",
                                promotion="PROPOSED->GATE-DATA->GATE-FALSIFICATION(no evaluable point)",
                                search=None, falsify=fr, severity=0.0, proof_tier=0, lean_statement=lean,
                                note="no evaluable sample point in domain under predicates")

    proof_tier = 1  # survived a finite grid; inequalities get no universal proof here
    index = novelty_index if novelty_index is not None else NoveltyIndex()
    receipt = index.search(nkey, mh, "not_proven_equal", term_canon, f"{lhs} {rel} {rhs}")
    sev = _severity(proof_tier, fr.samples_tested, manifest.domain_id, int(sp.count_ops(e_lhs - e_rhs)), refuted=False)
    if register:
        index.register(IndexedIdentity(novelty_key=nkey, truth_fp="", fp_tier="not_proven_equal",
                                       manifest_hash=mh, claim_id=claim_id, lhs=lhs, rhs=rhs,
                                       term_canon=term_canon, corpus_id=index.corpus_id))

    if receipt.match_kind == "REDISCOVERED":
        status: Status = "SURVIVED_KNOWN"
    elif receipt.match_kind == "PRIOR_ART_UNCHECKED":
        status = "SURVIVED_NOVELTY_UNCHECKED"
    else:
        status = "SURVIVED_NOVEL"
    return IdentityArtifact(claim=claim, status=status,
                            promotion=f"...->GATE-FALSIFICATION(survived {rel})->GATE-NOVELTY({receipt.match_kind})",
                            search=receipt, falsify=fr, severity=sev, proof_tier=proof_tier, lean_statement=lean,
                            note=f"no counterexample to '{lhs} {rel} {rhs}' on the finite grid; not a universal proof")
