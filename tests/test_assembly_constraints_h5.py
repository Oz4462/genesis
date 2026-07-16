"""H5: assembly placement constraints (offset / stack_z / align_xy)."""

from __future__ import annotations

import pytest

from gen.cad.assembly import (
    AssemblyConstraint,
    default_spacing_constraints,
    resolve_constraint_positions,
)


def test_offset_constraint_from_world():
    pos, gaps = resolve_constraint_positions(
        ["A", "B"],
        [
            AssemblyConstraint(kind="offset", fixed="WORLD", moving="A", offset_mm=(0, 0, 0)),
            AssemblyConstraint(kind="offset", fixed="A", moving="B", offset_mm=(150, 0, 0)),
        ],
    )
    assert pos["A"] == (0.0, 0.0, 0.0)
    assert pos["B"] == (150.0, 0.0, 0.0)
    assert not any("unpositioned" in g for g in gaps)


def test_stack_z_uses_part_height_and_gap():
    pos, gaps = resolve_constraint_positions(
        ["base", "lid"],
        [
            AssemblyConstraint(kind="offset", fixed="WORLD", moving="base"),
            AssemblyConstraint(
                kind="stack_z", fixed="base", moving="lid", gap_mm=2.0
            ),
        ],
        part_heights_mm={"base": 10.0},
    )
    assert pos["lid"][2] == pytest.approx(12.0)
    assert pos["lid"][0] == pos["base"][0]


def test_bad_kind_is_loud():
    with pytest.raises(ValueError, match="kind"):
        AssemblyConstraint(kind="coincident_magic", fixed="A", moving="B")


def test_default_spacing_matches_legacy_offsets():
    cons = default_spacing_constraints(["p0", "p1", "p2"])
    pos, _ = resolve_constraint_positions(["p0", "p1", "p2"], cons)
    assert pos["p0"] == (0.0, 0.0, 0.0)
    assert pos["p1"] == (150.0, 0.0, 0.0)
    assert pos["p2"] == (0.0, 110.0, 0.0)


def test_unresolved_fixed_is_gap_not_crash():
    pos, gaps = resolve_constraint_positions(
        ["A", "B"],
        [AssemblyConstraint(kind="offset", fixed="B", moving="A", offset_mm=(1, 0, 0))],
    )
    assert "A" not in pos or any("unresolved" in g for g in gaps)
    assert any("unresolved" in g or "unpositioned" in g for g in gaps)
