"""Safe, deterministic arithmetic for Derivations (PHASE_GAMMA.md §3.2).

The LLM never does math in GENESIS. This module is the single place where
DERIVED values come from: the `architect` uses it to COMPUTE values from the
formulas the LLM merely proposed, and GATE γ uses it to independently RECOMPUTE
them (condition C-6) — defense in depth against arithmetic hallucination
(hallucination face #2, PHASE_GAMMA.md §0).

The grammar is deliberately tiny: numbers, input names, ``+ - * /``, unary
minus, parentheses. Everything else fails loudly with ``FormulaError`` — a
value that cannot be deterministically recomputed must never exist as DERIVED.
Implementation walks the Python AST; no dynamic code execution of any kind.
"""

from __future__ import annotations

import ast

from ..core.errors import FormulaError
from ..core.state import Derivation

#: Relative tolerance for "recomputes exactly" (C-6) and eq-constraints (C-13).
DEFAULT_TOLERANCE = 1e-9

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def evaluate_formula(formula: str, bindings: dict[str, float]) -> float:
    """Evaluate `formula` over `bindings`. Raises FormulaError on anything
    outside the grammar, unknown names, non-numeric constants, or division by
    zero. Pure and deterministic: same inputs -> same float.
    """
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(formula, f"not parseable: {exc.msg}") from None
    return _eval_node(tree.body, formula, bindings)


def _eval_node(node: ast.AST, formula: str, bindings: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError(formula, f"non-numeric constant {node.value!r}")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in bindings:
            raise FormulaError(formula, f"unknown input {node.id!r}")
        return float(bindings[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand, formula, bindings)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _eval_node(node.left, formula, bindings)
        right = _eval_node(node.right, formula, bindings)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0.0:
            raise FormulaError(formula, "division by zero")
        return left / right
    raise FormulaError(formula, f"disallowed syntax: {type(node).__name__}")


def topological_values(
    known: dict[str, float],
    derived: dict[str, Derivation],
) -> tuple[dict[str, float], dict[str, str]]:
    """Resolve DERIVED values from `known` ones, dependency-ordered.

    Returns ``(values, errors)``: `values` contains every `known` entry plus
    every derived id that could be computed; `errors` maps each failed derived
    id to the reason (formula error, undeclared/unknown input, or an
    unresolvable dependency — which includes cycles). A failed item never gets
    a silently guessed value.

    A formula may only reference ids declared in its Derivation.inputs; the
    binding is restricted to exactly those, so an undeclared name fails as
    "unknown input" — referencing something you did not declare is drift.
    """
    values: dict[str, float] = dict(known)
    errors: dict[str, str] = {}
    pending = dict(derived)

    while pending:
        progressed = False
        for qid in list(pending):
            d = pending[qid]
            missing = [i for i in d.inputs if i not in values]
            if any(i in pending for i in missing):
                continue  # wait for other derived inputs (or fail later as cycle)
            if missing:
                failed = sorted(i for i in missing if i in errors)
                unknown = sorted(i for i in missing if i not in errors)
                parts = []
                if unknown:
                    parts.append(f"unknown input(s): {', '.join(unknown)}")
                if failed:
                    parts.append(f"failed dependency(ies): {', '.join(failed)}")
                errors[qid] = "; ".join(parts)
                del pending[qid]
                progressed = True
                continue
            bindings = {i: values[i] for i in d.inputs}
            try:
                values[qid] = evaluate_formula(d.formula, bindings)
            except FormulaError as exc:
                errors[qid] = str(exc)
            del pending[qid]
            progressed = True
        if not progressed:
            # Remaining items depend on each other (cycle) or on failed items.
            for qid in pending:
                errors[qid] = "unresolvable inputs (cycle or failed dependency)"
            break

    return values, errors


def within_tolerance(stated: float, computed: float, *, tolerance: float) -> bool:
    """Relative comparison used by C-6 (recompute) and eq-constraints (C-13)."""
    return abs(computed - stated) <= tolerance * max(1.0, abs(stated))
