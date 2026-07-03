# Why these modules are vendored

`anamnesis_mem/` contains four modules copied from the ANAMNESIS project
(`anamnesis-py/src/anamnesis`): `capture.py`, `conformal.py`, `storage.py`,
`retrieve.py`.

## Why vendor instead of depend?

The upstream `anamnesis` package lists `anthropic>=0.40` and `openai>=1.50` as
**hard core dependencies**, and `anamnesis/__init__.py` imports `distill`/`receipts`
which import those SDKs. Installing `anamnesis` would therefore pull cloud-LLM SDKs
into GENESIS. GENESIS is local-first and anti-cloud-leak (see `docs/VISION.md` /
ANONYMITY ethos): it must not carry `anthropic`/`openai` as runtime deps.

The four vendored modules need only `numpy` + stdlib (zero cloud deps). Vendoring the
needed subset is the dependency-light, ethos-preserving choice. Author is the same
(Ozan Küsmez), so this is licence-clean (`conformal.py` is Apache-2.0).

Contrast: `trust-core` (Phase 1) IS a real dependency — it is small (5 deps), has no
cloud SDKs, and is already consumed by VERIDEX. Different trade-off, different choice.

## What was changed

Only intra-package imports were rewritten to relative form
(`from anamnesis.X` -> `from .X`). No logic changes — the behaviour proven in PoV-2
carries over verbatim.

## Update procedure

Pinned to anamnesis v0.1.0 (2026-06-13). To refresh: re-copy the four files, re-apply
the relative-import rewrite, run `tests/test_verified_facts.py`, and bump the pin in
`anamnesis_mem/__init__.py`.
