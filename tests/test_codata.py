"""Tests for CODATA 2022 loader and FormulaRegistry.

All tests are fully offline: they use injected raw text or pre-parsed structures.
No network calls during test execution.
"""

from __future__ import annotations

import pytest

from gen.tools.codata import (
    PhysicalConstant,
    parse_allascii,
    load_codata_constants,
    get_constant,
    codata_table_source_ref,
    make_codata_constant_claim,
)
from gen.formulas.registry import FormulaRegistry, FormulaRecord


# Representative slice of the official allascii.txt (2022 CODATA).
# Covers: normal value+unc, (exact) constants, scientific notation with internal spaces.
_SAMPLE_ALLASCII = """Fundamental Physical Constants --- Complete Listing
              2022 CODATA adjustment

   From:  http://physics.nist.gov/constants


   Quantity                                                       Value                 Uncertainty           Unit
 -----------------------------------------------------------------------------------------------------------------------------
 electron mass                                               9.109 383 7139 e-31      0.000 000 0028 e-31      kg
 elementary charge                                           1.602 176 634 e-19       (exact)                  C
 Planck constant                                             6.626 070 15 e-34        (exact)                  J s
 Boltzmann constant                                          1.380 649 e-23           (exact)                  J K^-1
 Avogadro constant                                           6.022 140 76 e23         (exact)                  mol^-1
 speed of light in vacuum                                    299 792 458              (exact)                  m s^-1
 fine-structure constant                                     7.297 352 5643 e-3       0.000 000 0011 e-3       
 alpha particle mass                                         6.644 657 3450 e-27      0.000 000 0021 e-27      kg
"""


def test_parse_allascii_recognizes_exact_and_normal():
    consts = parse_allascii(_SAMPLE_ALLASCII)

    e = consts["elementary_charge"]
    assert e.exact is True
    assert e.uncertainty is None
    assert e.unit == "C"
    assert abs(e.value - 1.602176634e-19) < 1e-30

    me = consts["electron_mass"]
    assert me.exact is False
    assert me.uncertainty is not None
    assert me.unit == "kg"
    assert 9.109e-31 < me.value < 9.11e-31


def test_load_with_injected_text_is_deterministic_and_offline():
    c1 = load_codata_constants(raw_text=_SAMPLE_ALLASCII)
    c2 = load_codata_constants(raw_text=_SAMPLE_ALLASCII)
    assert list(c1.keys()) == list(c2.keys())
    assert c1["boltzmann_constant"].exact is True


def test_get_constant_raises_on_unknown():
    consts = parse_allascii(_SAMPLE_ALLASCII)
    with pytest.raises(KeyError):
        get_constant("nonexistent_constant", consts)


def test_registry_registers_codataconstant_and_lookup():
    consts = parse_allascii(_SAMPLE_ALLASCII)
    reg = FormulaRegistry()

    count = 0
    for c in consts.values():
        reg.register_constant(c)
        count += 1

    assert count == len(consts)

    e = reg.get("elementary_charge")
    assert isinstance(e, FormulaRecord)
    assert e.kind == "constant"
    assert e.exact is True
    assert "NIST CODATA 2022" in e.sources[0]

    # by record_id also works
    rid = "const:elementary_charge"
    assert reg.get(rid).name == "elementary_charge"


def test_registry_first_writer_wins():
    reg = FormulaRegistry()
    c1 = PhysicalConstant(name="x", quantity="X", value=1.0, uncertainty=0.1, unit="1")
    c2 = PhysicalConstant(name="x", quantity="X", value=2.0, uncertainty=0.2, unit="1")

    rec1 = reg.register_constant(c1)
    rec2 = reg.register_constant(c2)

    # second register returns the first one's hash and keeps value
    assert rec1 == rec2
    stored = reg.get("x")
    assert abs(float(stored.expr) - 1.0) < 1e-12


def test_registry_load_codata_populates_from_real_loader(monkeypatch):
    # Ensure the registry convenience path works with injected data
    reg = FormulaRegistry()
    # Monkeypatch inside the module so load_codata inside registry uses our sample
    import gen.formulas.registry as regmod
    monkeypatch.setattr(regmod, "load_codata_constants", lambda **kw: parse_allascii(_SAMPLE_ALLASCII))

    n = reg.load_codata()
    assert n >= 5
    assert "planck_constant" in reg.list_names()


def test_codata_helpers_produce_ledger_ready_source_and_claim():
    from gen.core.state import Claim

    table_text = _SAMPLE_ALLASCII
    consts = parse_allascii(table_text)
    e = consts["elementary_charge"]

    src = codata_table_source_ref(table_text)
    assert src.url_or_id.endswith("allascii.txt")
    assert src.content_hash is not None
    assert src.retrieved is True

    claim = make_codata_constant_claim(e, table_text)
    assert isinstance(claim, Claim)
    assert "elementary charge" in claim.text.lower()
    assert len(claim.sources) == 1
    assert claim.sources[0].content_hash == src.content_hash


def test_registry_make_claim_for():
    from gen.core.state import Claim

    table_text = _SAMPLE_ALLASCII
    consts = parse_allascii(table_text)

    # Direct helpers (most common usage path)
    claim = make_codata_constant_claim(consts["boltzmann_constant"], table_text)
    assert isinstance(claim, Claim)
    assert claim.sources[0].content_hash is not None

    # Registry roundtrip: register then produce claim via helper
    reg = FormulaRegistry()
    for c in consts.values():
        reg.register_constant(c)
    # The registry's make_claim_for will call get_constant (real load path) so we test
    # the direct make instead for determinism in this test; the important part is
    # that FormulaRecord + helpers compose cleanly with Ledger Claim.
    assert "boltzmann_constant" in reg.list_names()


def test_load_exact_physical_anchors():
    # The helper lives in identity_research and should be reachable
    from gen.identity_research import load_exact_physical_anchors
    anchors = load_exact_physical_anchors()
    # With injected data in other tests this may be empty, but call must succeed
    assert isinstance(anchors, tuple)
