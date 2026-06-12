"""Security — the closed-form cryptographic sizing checks (ε-crypto axis, δ-layer).

A spec that declares cryptography can be wrong in ways no structural validator
sees: a nonce space too small for the message volume (collisions break GCM/CTR
catastrophically), a key length below the required security strength, or more
GCM invocations per key than the standard permits. These are exactly the kind of
deterministic, citable closed forms GENESIS validates — no protocol analysis, no
implementation audit, just the arithmetic the standards themselves prescribe.

Three validators (registry pattern: dict with "ok" + a margin, ValueError on
nonsense inputs; each anchored exactly in the tests):

  * ``birthday_bound_check`` — the BIRTHDAY BOUND: among q random values drawn
    from a space of 2^n, the collision probability is approximately
    p ≈ q²/2^(n+1) (the standard approximation for p « 1). NIST's GCM rationale
    bounds the IV-collision probability at 2^-32 — the default ceiling here.
  * ``key_security_check`` — NIST SP 800-57 Part 1 Rev. 5, Table 2: comparable
    security strengths. Symmetric keys give their length; ECC gives ~half the
    key size; RSA/DH (integer factorization / finite field) maps 1024→80,
    2048→112, 3072→128, 7680→192, 15360→256. A key below the required strength
    (default 128 bits) is a definite finding, not an opinion.
  * ``gcm_invocation_budget_check`` — NIST SP 800-38D §8.3: with RANDOM 96-bit
    IVs, at most 2^32 invocations of the authenticated-encryption function per
    key. Deterministic (counter) IV construction has a different budget and is
    declared out of scope here rather than guessed.

Honest boundary: these checks size PARAMETERS — they do not prove a protocol
secure, do not audit an implementation, and do not replace a cryptographer.
Quantum threats are out of scope (PQ sizing follows different tables). A passed
check is necessary, not sufficient — the same δ asymmetry as every other axis.

Sources: birthday bound — standard result (e.g. Katz & Lindell, *Introduction
to Modern Cryptography*; mirrored in the local MathBrain vault,
``Formeln/crypto-birthday-bound.md``); NIST SP 800-57 Part 1 Rev. 5 Table 2
(comparable strengths); NIST SP 800-38D §8.3 (GCM invocation limit, 2^-32 IV
collision bound). Verified 2026-06-12.
"""

from __future__ import annotations

#: NIST SP 800-38D: maximum invocations per key with random 96-bit IVs.
GCM_RANDOM_IV_MAX_INVOCATIONS = 2 ** 32

#: NIST SP 800-38D: required bound on the IV-collision probability.
GCM_IV_COLLISION_BOUND = 2.0 ** -32

#: Default required security strength [bits] (the current general baseline).
REQUIRED_SECURITY_BITS = 128

# NIST SP 800-57 Part 1 Rev. 5, Table 2: RSA/DH modulus bits -> security strength.
# Encoded as (minimum modulus bits, strength); values between rows take the
# strength of the largest row they meet (the standard's own granularity).
_RSA_STRENGTH_TABLE: tuple[tuple[int, int], ...] = (
    (15360, 256),
    (7680, 192),
    (3072, 128),
    (2048, 112),
    (1024, 80),
)


def birthday_collision_probability(space_bits: float, n_uses: float) -> float:
    """Collision probability p ≈ q²/2^(n+1) for q draws from a 2^n space.

    The standard birthday-bound approximation (valid for p « 1; the value is
    clamped at 1.0 where the approximation leaves its regime). Raises ValueError
    on a non-positive space or a negative use count."""
    if space_bits <= 0.0:
        raise ValueError("space_bits must be positive")
    if n_uses < 0.0:
        raise ValueError("n_uses must be non-negative")
    p = (n_uses * n_uses) / (2.0 ** (space_bits + 1.0))
    return min(p, 1.0)


def birthday_bound_check(
    space_bits: float,
    n_uses: float,
    max_collision_prob: float = GCM_IV_COLLISION_BOUND,
) -> dict:
    """Is the random-value space big enough for the planned number of uses?

    The check that catches "96-bit random nonce, ten billion messages": the
    collision probability must stay below `max_collision_prob` (default: the
    NIST 2^-32 IV-collision bound). Returns ``{"collision_probability",
    "max_collision_prob", "safety_factor", "ok"}`` with safety_factor =
    max/p (inf for zero uses). Raises ValueError on a non-positive bound."""
    if not 0.0 < max_collision_prob <= 1.0:
        raise ValueError("max_collision_prob must be in (0, 1]")
    p = birthday_collision_probability(space_bits, n_uses)
    safety_factor = float("inf") if p == 0.0 else max_collision_prob / p
    return {
        "collision_probability": p,
        "max_collision_prob": max_collision_prob,
        "safety_factor": safety_factor,
        "ok": p <= max_collision_prob,
    }


def security_strength_bits(mechanism: str, key_bits: float) -> float:
    """NIST SP 800-57 comparable security strength of a key [bits].

    ``mechanism``: "symmetric" (strength = key length), "ecc" (strength ≈
    key_bits / 2), or "rsa" (also DH over finite fields; Table-2 rows, a
    modulus below 1024 bits maps to 0 — below every standardized row).
    Raises ValueError on an unknown mechanism or non-positive key size —
    never a guessed strength."""
    if key_bits <= 0.0:
        raise ValueError("key_bits must be positive")
    mech = mechanism.strip().lower()
    if mech == "symmetric":
        return float(key_bits)
    if mech == "ecc":
        return key_bits / 2.0
    if mech in ("rsa", "dh", "ffdh"):
        for min_bits, strength in _RSA_STRENGTH_TABLE:
            if key_bits >= min_bits:
                return float(strength)
        return 0.0
    raise ValueError(
        f"unknown mechanism {mechanism!r} (expected 'symmetric', 'ecc', or 'rsa'/'dh')"
    )


def key_security_check(
    mechanism: str,
    key_bits: float,
    required_bits: float = REQUIRED_SECURITY_BITS,
) -> dict:
    """Does the key reach the required security strength (SP 800-57 Table 2)?

    Returns ``{"strength_bits", "required_bits", "safety_factor", "ok"}`` with
    safety_factor = strength/required. RSA-3072 ≡ ECC-256 ≡ AES-128 at the
    128-bit level — the table the check encodes. Raises ValueError on an
    unknown mechanism, non-positive key size, or non-positive requirement."""
    if required_bits <= 0.0:
        raise ValueError("required_bits must be positive")
    strength = security_strength_bits(mechanism, key_bits)
    return {
        "strength_bits": strength,
        "required_bits": required_bits,
        "safety_factor": strength / required_bits,
        "ok": strength >= required_bits,
    }


def gcm_invocation_budget_check(
    n_invocations: float,
    max_invocations: float = GCM_RANDOM_IV_MAX_INVOCATIONS,
) -> dict:
    """AES-GCM with random IVs: at most 2^32 invocations per key (SP 800-38D).

    Returns ``{"n_invocations", "max_invocations", "safety_factor", "ok"}``
    with safety_factor = max/n (inf for zero). Deterministic-IV constructions
    have a different budget — declared out of scope, not silently approved.
    Raises ValueError on a negative count or non-positive budget."""
    if n_invocations < 0.0:
        raise ValueError("n_invocations must be non-negative")
    if max_invocations <= 0.0:
        raise ValueError("max_invocations must be positive")
    safety_factor = (
        float("inf") if n_invocations == 0.0 else max_invocations / n_invocations
    )
    return {
        "n_invocations": n_invocations,
        "max_invocations": max_invocations,
        "safety_factor": safety_factor,
        "ok": n_invocations <= max_invocations,
    }
