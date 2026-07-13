# The Well probe (GENESIS) — storage-safe usage

**Source:** [PolymathicAI/the_well](https://github.com/PolymathicAI/the_well) (~15 TB collection)  
**GENESIS policy:** **stream-only**, ≤3 batches, never bulk-download the collection.

## Why

The Well is useful as a **δ/surrogate reference** (physics simulations for ML). The full collection does not fit a laptop. GENESIS exposes a probe that:

1. Lists known datasets offline (catalog)
2. Optionally streams **1–3 batches** from Hugging Face if `the_well` is installed
3. Fails loudly when the package/network is missing — **no fake tensors**

## Commands

```bash
# Offline catalog (no package, no network)
python -m gen --mode well-probe --demo
python -m gen --mode well-probe

# Stream probe (requires venv + the_well + network)
python -m gen --mode well-probe active_matter
python -m gen --mode well-probe 'active_matter|train|2'   # dataset|split|max_batches
```

Exit codes: `0` ok/catalog · `3` package/tooling unavailable · `2` error.

## Install (venv only)

```bash
python -m venv ~/venvs/the_well
source ~/venvs/the_well/bin/activate
pip install the_well
# keep HF cache small
export HF_HOME=/tmp/hf_cache_well
python -m gen --mode well-probe active_matter
```

**Do not** run `the-well-download` without `--dataset` and `--split`.  
**Do not** set bulk download from GENESIS.

## Env

| Variable | Meaning |
|----------|---------|
| `GENESIS_WELL_BASE` | Override data root (default `hf://datasets/polymathic-ai/`) |
| `GENESIS_WELL_ALLOW_LOCAL=1` | Allow a local path only if ONE dataset was deliberately downloaded |
| `HF_HOME` | Hugging Face cache location (prefer `/tmp` on small disks) |

## Module

- `gen.tools.the_well_probe` — API + catalog
- CLI: `--mode well-probe`
- Product surface: `gen.tools.the_well_probe`
