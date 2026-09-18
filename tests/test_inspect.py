# This file was generated with the assistance of an AI coding tool.
"""Tests for ifckit.inspect.report."""

import pytest

from ifckit import IfcModel, LengthUnit, PendingWall
from ifckit.geometry import Plane, Vec
from ifckit.inspect import ModelReport, report


def _room_model(unit: LengthUnit) -> IfcModel:
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


def _two_room_model() -> IfcModel:
    m = IfcModel(name="TwoRoom")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    storey.add_space(
        [Vec(0, 0, 0), Vec(3, 0, 0), Vec(3, 4, 0), Vec(0, 4, 0)], 3.0, "1.01", "Keuken"
    )
    storey.add_space(
        [Vec(3, 0, 0), Vec(9, 0, 0), Vec(9, 4, 0), Vec(3, 4, 0)], 3.0, "1.02", "Woonkamer"
    )
    return m


def test_report_is_model_report():
    r = report(_room_model(LengthUnit.METRE))
    assert isinstance(r, ModelReport)
    assert r.stage == "S0"


def test_report_s0_metre_and_millimetre_agree():
    metre = report(_room_model(LengthUnit.METRE))
    mm = report(_room_model(LengthUnit.MILLIMETRE))
    assert metre.spaces[0]["area"] == pytest.approx(12.0)
    assert metre.spaces[0]["volume"] == pytest.approx(32.4)
    # mm-model geeft dezelfde SI-metingen
    assert mm.spaces[0]["area"] == pytest.approx(metre.spaces[0]["area"])
    assert mm.spaces[0]["volume"] == pytest.approx(metre.spaces[0]["volume"])
    # de bestandseenheid wordt apart gerapporteerd
    assert metre.model_unit == "METRE"
    assert mm.model_unit == "MILLIMETRE"


def test_report_s0_fields_and_bounds():
    s = report(_room_model(LengthUnit.METRE)).spaces[0]
    assert s["name"] == "1.01"
    assert s["long_name"] == "Keuken"
    assert s["bounds"]["x_max"] == pytest.approx(4.0)
    assert s["bounds"]["y_max"] == pytest.approx(3.0)
    assert s["bounds"]["z_max"] == pytest.approx(2.7)
    assert s["adjacent"] == []


def test_report_s0_adjacency():
    r = report(_two_room_model())
    by_name = {s["name"]: s for s in r.spaces}
    assert by_name["1.01"]["adjacent"] == ["1.02"]
    assert by_name["1.02"]["adjacent"] == ["1.01"]


def test_report_s1_flags_isolated_walls():
    m = IfcModel(name="Walls")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    plane = Plane.world_xy()
    # twee wanden die elkaar niet raken
    storey.add(
        PendingWall([Vec(0, 0, 0), Vec(0.2, 0, 0), Vec(0.2, 4, 0), Vec(0, 4, 0)], plane, 3.0, "W1")
    )
    storey.add(
        PendingWall([Vec(5, 0, 0), Vec(5.2, 0, 0), Vec(5.2, 4, 0), Vec(5, 4, 0)], plane, 3.0, "W2")
    )
    r = report(m, stage="S1")
    assert r.stage == "S1"
    assert r.elements["Wall"] == 2
    assert r.elements["isolated_walls"] == 2
    assert any("zonder aansluiting" in w for w in r.warnings)


def test_report_s2_inventory():
    r = report(_two_room_model(), stage="S2")
    assert r.stage == "S2"
    assert r.elements["OpeningElement"] == 0
    assert all("openings" in s for s in r.spaces)


def test_report_rejects_unknown_stage():
    with pytest.raises(ValueError):
        report(_room_model(LengthUnit.METRE), stage="S9")


def test_report_as_json_serialisable():
    r = report(_two_room_model())
    data = r.to_dict()
    assert data["spaces"][0]["name"] in {"1.01", "1.02"}
    assert '"spaces"' in r.as_json()
