"""Verify-extra seam: the guarded trust-core imports must fail LOUD and HONEST.

Root cause (Audit Prio-2, 2026-07-04): the real trust-core is a PRIVATE companion
library (editable install from the sibling repo, see docs/integration/PHASE1_TRUSTCORE.md)
with `trust_core.conformal.*` / `trust_core.math.fdr` / `trust_core.receipts.keystore`.
The `trust-core` package ON PYPI (0.1.0: engine/keys/proof/wire) is an unrelated
NAMESAKE — so the guard messages' old advice `pip install -e '.[verify]'` resolved to
the namesake, and with it installed `pytest.importorskip("trust_core")` succeeded while
the subsequent submodule imports turned five test files into COLLECTION ERRORS instead
of clean skips (reproduced live before this fix).

These tests run in EVERY environment (with, without, or with the wrong trust-core) by
injecting stand-ins into sys.modules:
  * a NAMESAKE package: `trust_core` importable, needed submodules missing;
  * an ABSENT package: `sys.modules["trust_core"] = None` -> ImportError on import.
In both worlds each guarded module must raise its own ImportError whose message names
the missing submodule and warns about the PyPI namesake instead of recommending it.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest

# (guarded gen module, trust_core submodule its guard message must name)
_SEAMS = [
    ("gen.verification.drift_monitor", "trust_core.conformal.ccdd"),
    ("gen.verification.trustcore_adapter", "trust_core.conformal.split"),
    ("gen.audit.run_audit", "trust_core.receipts.keystore"),
]


def _evict(monkeypatch: pytest.MonkeyPatch, *prefixes: str) -> None:
    """Drop cached modules so the import under test really re-executes the guard."""
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            monkeypatch.delitem(sys.modules, name, raising=False)


def _namesake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a stand-in for the PyPI namesake: package exists, submodules do not."""
    _evict(monkeypatch, "trust_core")
    fake = types.ModuleType("trust_core")
    fake.__path__ = []  # a package -- but one where no submodule can be found
    monkeypatch.setitem(sys.modules, "trust_core", fake)


def _absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate trust-core not installed at all (None entry -> ImportError)."""
    _evict(monkeypatch, "trust_core")
    monkeypatch.setitem(sys.modules, "trust_core", None)


@pytest.mark.parametrize(("gen_module", "needed"), _SEAMS)
@pytest.mark.parametrize("world", ["namesake", "absent"])
def test_guarded_import_fails_loud_and_warns_about_pypi_namesake(
    monkeypatch: pytest.MonkeyPatch, gen_module: str, needed: str, world: str
) -> None:
    (_namesake if world == "namesake" else _absent)(monkeypatch)
    _evict(monkeypatch, gen_module)

    with pytest.raises(ImportError) as excinfo:
        importlib.import_module(gen_module)

    msg = str(excinfo.value)
    assert needed in msg, "message must name the exact missing trust_core submodule"
    assert "PyPI" in msg and "namesake" in msg, (
        "message must warn that the PyPI 'trust-core' is an unrelated namesake"
    )
    # The old advice actively installed the namesake; it must be gone.
    assert ".[verify]" not in msg
    assert "pip install trust-core" not in msg
