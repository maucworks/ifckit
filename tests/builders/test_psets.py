"""Tests for EPset_IfcKit_Geometry and EPset_IfcKit property sets."""
from __future__ import annotations

import math
import pytest
import ifcopenshell

from ifckit.elements.structural import PendingBeam, PendingRevolvedBeam
from ifckit.elements.building import PendingWall
from ifckit.geometry import Arc, Line, Plane, Vec
from ifckit.profiles.shapes import RectangleProfile
from ifckit.profiles.i_beam import IBeamProfile
from ifckit.builders.psets import write_psets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ifc():
    ifc = ifcopenshell.file(schema="IFC4")
    # Minimal owner history
    person = ifc.create_entity("IfcPerson", FamilyName="Test")
    org = ifc.create_entity("IfcOrganization", Name="Test")
    p_and_o = ifc.create_entity("IfcPersonAndOrganization", ThePerson=person, TheOrganization=org)
    app = ifc.create_entity("IfcApplication", ApplicationDeveloper=org,
                             Version="1", ApplicationFullName="test", ApplicationIdentifier="test")
    ifc.create_entity("IfcOwnerHistory", OwningUser=p_and_o, OwningApplication=app,
                      ChangeAction="ADDED", CreationDate=0)
    return ifc


def _fake_element(ifc):
    """Create a minimal IfcBeam entity for pset attachment."""
    return ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcBeam", name="TestBeam")


def _get_pset(ifc, element, pset_name):
    """Return dict of {name: NominalValue.wrappedValue} for a named pset on element."""
    for rel in ifc.by_type("IfcRelDefinesByProperties"):
        if element in rel.RelatedObjects:
            pdef = rel.RelatingPropertyDefinition
            if hasattr(pdef, "Name") and pdef.Name == pset_name:
                return {p.Name: p.NominalValue.wrappedValue for p in pdef.HasProperties}
    return {}


# ---------------------------------------------------------------------------
# PendingBeam — straight, with IBeamProfile (steel)
# ---------------------------------------------------------------------------

def test_beam_geometry_pset():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    profile = IBeamProfile(height=0.2, width=0.1, web_thickness=0.006, flange_thickness=0.01,
                           name="IPE200")
    beam = PendingBeam(
        axis=Line(Vec(0, 0, 0), Vec(5, 0, 0)),
        profile=profile,
        name="B-1",
    )
    write_psets(ifc, element, beam)

    geo = _get_pset(ifc, element, "EPset_IfcKit_Geometry")
    assert geo["Name"] == "B-1"
    assert abs(geo["Length"] - 5.0) < 1e-6
    assert "CrossSectionArea" in geo
    assert geo["CrossSectionArea"] > 0


def test_beam_steel_section_name():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    from ifckit.profiles.steel import SteelProfile
    profile = SteelProfile.from_name("IPE300")
    beam = PendingBeam(axis=Line(Vec(0, 0, 0), Vec(3, 0, 0)), profile=profile, name="IPE300-1")
    write_psets(ifc, element, beam)

    geo = _get_pset(ifc, element, "EPset_IfcKit_Geometry")
    assert geo.get("SteelSectionName") == "IPE300"


def test_beam_no_steel_section_for_generic_profile():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    profile = RectangleProfile(x_dim=0.1, y_dim=0.2)
    beam = PendingBeam(axis=Line(Vec(0, 0, 0), Vec(2, 0, 0)), profile=profile)
    write_psets(ifc, element, beam)

    geo = _get_pset(ifc, element, "EPset_IfcKit_Geometry")
    assert "SteelSectionName" not in geo


# ---------------------------------------------------------------------------
# PendingRevolvedBeam — arc lengths and angles
# ---------------------------------------------------------------------------

def test_revolved_beam_geometry_pset():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    radius = 2.0
    angle = math.pi / 2  # 90°
    arc = Arc(
        center=Vec(0, 0, 0),
        normal=Vec(0, 0, 1),
        start=Vec(radius, 0, 0),
        angle=angle,
    )
    profile = RectangleProfile(x_dim=0.1, y_dim=0.2)
    beam = PendingRevolvedBeam(arc=arc, profile=profile, name="Arch-1")
    write_psets(ifc, element, beam)

    geo = _get_pset(ifc, element, "EPset_IfcKit_Geometry")
    assert geo["Name"] == "Arch-1"
    assert abs(geo["ArcAngle_rad"] - angle) < 0.01   # rounded to 2 decimals
    assert abs(geo["ArcAngle_deg"] - 90.0) < 0.1      # rounded to 1 decimal
    assert abs(geo["ArcLength"] - radius * angle) < 0.001  # rounded to 3 decimals (mm)


# ---------------------------------------------------------------------------
# PendingWall — length and height
# ---------------------------------------------------------------------------

def test_wall_geometry_pset():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    wall = PendingWall(
        footprint=[Vec(0, 0, 0), Vec(4, 0, 0), Vec(4, 0.2, 0), Vec(0, 0.2, 0)],
        plane=Plane.world_xy(),
        height=3.0,
        name="W-1",
    )
    write_psets(ifc, element, wall)

    geo = _get_pset(ifc, element, "EPset_IfcKit_Geometry")
    assert geo["Name"] == "W-1"
    assert abs(geo["Height"] - 3.0) < 1e-6
    assert abs(geo["Length"] - 4.0) < 1e-6


# ---------------------------------------------------------------------------
# User properties → EPset_IfcKit
# ---------------------------------------------------------------------------

def test_user_properties_pset():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    beam = PendingBeam(
        axis=Line(Vec(0, 0, 0), Vec(1, 0, 0)),
        profile=RectangleProfile(x_dim=0.1, y_dim=0.1),
        name="B",
        properties={"Supplier": "Voortman", "Weight_kg": 42.5, "Count": 3, "Painted": True},
    )
    write_psets(ifc, element, beam)

    user = _get_pset(ifc, element, "EPset_IfcKit")
    assert user["Supplier"] == "Voortman"
    assert abs(user["Weight_kg"] - 42.5) < 1e-9
    assert user["Count"] == 3
    assert user["Painted"] is True


def test_no_user_pset_when_properties_empty():
    ifc = _make_ifc()
    element = _fake_element(ifc)

    beam = PendingBeam(
        axis=Line(Vec(0, 0, 0), Vec(1, 0, 0)),
        profile=RectangleProfile(x_dim=0.1, y_dim=0.1),
        name="B",
    )
    write_psets(ifc, element, beam)

    assert _get_pset(ifc, element, "EPset_IfcKit") == {}


# ---------------------------------------------------------------------------
# properties round-trips through to_json / from_json
# ---------------------------------------------------------------------------

def test_properties_serialization_roundtrip():
    beam = PendingBeam(
        axis=Line(Vec(0, 0, 0), Vec(1, 0, 0)),
        profile=RectangleProfile(x_dim=0.1, y_dim=0.1),
        name="B",
        properties={"Tag": "A-01", "Floor": 2},
    )
    d = beam.to_dict()
    assert d["properties"] == {"Tag": "A-01", "Floor": 2}

    beam2 = PendingBeam.from_dict(d)
    assert beam2.properties == {"Tag": "A-01", "Floor": 2}
