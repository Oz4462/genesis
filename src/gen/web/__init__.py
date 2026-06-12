"""GENESIS web UI — a local FastAPI layer over the existing engine contracts.

No new behavior lives here: every endpoint calls the same runner / gates / pipeline /
ratification functions the CLI and tests use. The live LLM path exists but is HARD-GATED
(off by default); everything else is deterministic and offline. See web/app.py.
"""
