# CadQuery / OCCT — why not system pip, and how GENESIS uses it

## Why `pip install cadquery` fails on the system Python

Debian/Ubuntu mark the system interpreter as **externally managed** ([PEP 668](https://peps.python.org/pep-0668/)):

```text
error: externally-managed-environment
× This environment is externally managed
```

That is **not** a CadQuery bug. The OS refuses to let `pip` write into `/usr/lib/python3*`, so packages cannot silently break `apt`-managed Python.

**Do not** use `pip install --break-system-packages` on the system Python for CadQuery.

## Why CadQuery is also not in the main GENESIS venv

CadQuery pulls **OpenCASCADE (OCP)** and a pinned **numpy** stack. Putting it in the same venv as GENESIS’s science stack (numpy/scipy/sympy/z3/…) historically **downgraded numpy** and broke the rest of the product.

GENESIS therefore uses an **isolated cad venv** and talks to it only via subprocess JSON (`gen.cad.cadquery_bridge` → `gen.cad.cadquery_worker`).

## Install (once)

```bash
# Preferred default path used by the bridge:
python3 -m venv /home/genesis/.venv-cad
/home/genesis/.venv-cad/bin/pip install -U pip wheel
/home/genesis/.venv-cad/bin/pip install cadquery

# Verify:
/home/genesis/.venv-cad/bin/python -c "import cadquery; print(cadquery.__version__)"
```

Alternate path (also fine):

```bash
python3 -m venv /home/genesis/venvs/genesis-cad
/home/genesis/venvs/genesis-cad/bin/pip install cadquery
export GENESIS_CAD_PYTHON=/home/genesis/venvs/genesis-cad/bin/python
```

## Configuration

| Env | Default | Meaning |
|-----|---------|---------|
| `GENESIS_CAD_PYTHON` | `/home/genesis/.venv-cad/bin/python` | Interpreter that has cadquery |

Public probe:

```python
from gen.cad.cadquery_bridge import cad_available, cad_python
assert cad_available()  # True when interpreter + worker exist
```

## What runs where

| Process | Has cadquery? | Role |
|---------|---------------|------|
| Main GENESIS (`python3` / project `.venv`) | **No** (by design) | α/β/γ, invent, physics, CLI |
| Cad venv worker | **Yes** | Exact volume, validity, interference, STL, STEP, tessellation, bbox |

Callers should use:

- `gen.brep.exact_volume` / `is_valid` / `interferes` (auto-bridge)
- `gen.export.brep_stl.specification_to_brep_stl` / `component_to_brep_stl`
- `gen.orientation.*` / `gen.geometry_verification.verify_geometry` (bridge mesh path)

Not: `import cadquery` inside the main process.

## Verify end-to-end

```bash
export PYTHONPATH=src
# optional if not using the default path:
# export GENESIS_CAD_PYTHON=/home/genesis/.venv-cad/bin/python
python3 -m gen --mode print --demo
# expect: capstone Status print_ready or needs_attention (not unavailable)
pytest tests/test_cadquery_bridge_integration.py -q
```

## Status after gap-close (2026-07-14)

- CadQuery **installable** in isolated venv (confirmed 2.8.0).
- Print/BREP/orientation/geometry verification use the **bridge** when in-process cadquery is absent.
- System-wide `pip install cadquery` remains correctly blocked by PEP 668.
