# This file was generated with the assistance of an AI coding tool.
"""Tests for ifckit.render.snapshot."""

import pytest

from ifckit import IfcModel, LengthUnit
from ifckit.geometry import Vec
from ifckit.render import Snapshot, snapshot


def _room_model(unit: LengthUnit = LengthUnit.METRE) -> IfcModel:
    scale = 1000.0 if unit is LengthUnit.MILLIMETRE else 1.0
    m = IfcModel(name="R", unit=unit)
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    storey.add_space(
        [Vec(0, 0, 0), Vec(4 * scale, 0, 0), Vec(4 * scale, 3 * scale, 0), Vec(0, 3 * scale, 0)],
        height=2.7 * scale,
        name="1.01",
        long_name="Keuken",
    )
    return m


def test_snapshot_returns_plan_svg():
    snap = snapshot(_room_model())
    assert isinstance(snap, Snapshot)
    assert "plan" in snap.svgs
    assert b"<path" in snap.svgs["plan"]


def test_snapshot_is_deterministic():
    m = _room_model()
    first = snapshot(m)
    second = snapshot(m)
    assert first.svgs["plan"] == second.svgs["plan"]


def test_snapshot_does_not_accumulate_drawings():
    m = _room_model()
    snapshot(m)
    snapshot(m)
    drawings = [
        a
        for a in m.ifc_file.by_type("IfcAnnotation")
        if getattr(a, "ObjectType", None) == "DRAWING"
        and getattr(a, "Name", None) == "__ifckit_plan__"
    ]
    assert len(drawings) == 1


def test_snapshot_metre_and_millimetre():
    metre = snapshot(_room_model(LengthUnit.METRE))
    mm = snapshot(_room_model(LengthUnit.MILLIMETRE))
    assert b"<path" in metre.svgs["plan"]
    assert b"<path" in mm.svgs["plan"]


def test_snapshot_rejects_unknown_view():
    with pytest.raises(ValueError):
        snapshot(_room_model(), views=("iso",))
