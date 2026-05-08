"""
SectionedSpine MVP Example

Test script for IfcSectionedSpine builder.
Generates IFC files with SectionedSpine geometry.

Usage:
    python3 examples/test_sectioned_spine.py
"""

from ifckit import IfcModel, LengthUnit
from ifckit.elements import PendingSectionedSpine
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile, DerivedProfile, IBeamProfile
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.builders._geom import get_body_context
import ifcopenshell
import uuid, math


def _guid():
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _make_storey(ifc_file, project):
    """Create a basic storey and return it."""
    o = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    axis = ifc_file.create_entity(
        "IfcAxis2Placement3D", Location=o, Axis=z, RefDirection=x
    )
    place = ifc_file.create_entity(
        "IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=axis
    )
    storey = ifc_file.create_entity(
        "IfcBuildingStorey",
        GlobalId=_guid(),
        Name="Storey",
        ObjectPlacement=place,
    )
    ifc_file.create_entity(
        "IfcRelAggregates",
        GlobalId=_guid(),
        RelatingObject=project,
        RelatedObjects=[storey],
    )
    return storey


def test_basic_spike():
    """Basic SectionedSpine - uniform profile along straight spine."""
    print("=== Test 1: Basic Spine ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)

    # Spine: straight line along Z
    spine = Path.from_pts([Vec(0, 0, 0), Vec(0, 0, 500)])

    # Two identical profiles
    p1 = RectangleProfile(50, 70)
    p2 = RectangleProfile(50, 70)

    # Positions must match spine endpoints
    # Z-axis points along spine direction (+Z), X-axis is the profile "width" axis
    pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos2 = Plane(Vec(0, 0, 500), Vec(1, 0, 0), Vec(0, 1, 0))

    pending = PendingSectionedSpine(
        spine=spine, profiles=[p1, p2], positions=[pos1, pos2], name="basic_spine"
    )

    # Build via registry API
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    element = builder.build(ifc_file, pending, storey, context)

    print(f"  Element: {element.is_a()} - {element.Name}")
    geom_item = element.Representation.Representations[0].Items[0]
    print(f"  Geometry: {geom_item.is_a()}")

    model.save("output/test_sectioned_spine_basic.ifc")
    print("  Saved: output/test_sectioned_spine_basic.ifc\n")


def test_varying_profiles():
    """SectionedSpine with varying profiles along spine."""
    print("=== Test 2: Varying Profiles ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)

    # Spine: straight line along X
    spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0)])

    # Profile 1: base
    p1 = RectangleProfile(50, 70)

    # Profile 2: scaled 1.5x
    p2 = DerivedProfile(RectangleProfile(50, 70), scale=1.5)

    # Profile 3: scaled 2x
    p3 = DerivedProfile(RectangleProfile(50, 70), scale=2.0)

    # Positions: Z-axis must point along spine direction (+X).
    # Profile plane = YZ plane (X=spine tangent is the normal).
    pos1 = Plane(Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))  # z_axis = +X
    pos2 = Plane(Vec(500, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))
    pos3 = Plane(Vec(1000, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))

    pending = PendingSectionedSpine(
        spine=spine,
        profiles=[p1, p2, p3],
        positions=[pos1, pos2, pos3],
        name="varying_spine",
    )

    # Build via registry API
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    element = builder.build(ifc_file, pending, storey, context)

    geom_item = element.Representation.Representations[0].Items[0]
    print(f"  Element: {element.is_a()}")
    print(f"  Geometry: {geom_item.is_a()}")
    if geom_item.is_a() == "IfcTriangulatedFaceSet":
        print(f"    Vertices: {len(geom_item.Coordinates.CoordList)}")
        print(f"    Triangles: {len(geom_item.CoordIndex)}")

    model.save("output/test_sectioned_spine_varying.ifc")
    print("  Saved: output/test_sectioned_spine_varying.ifc\n")


def test_ibeam_spine():
    """SectionedSpine with I-beam profiles along a 3D path."""
    print("=== Test 3: I-Beam Spine ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)

    # Four control points a, b, c, d
    a = Vec(0, 0, 0)
    b = a + Vec(2000, 0, 0)
    c = b + Vec(1000, 0, 1000)
    d = c + Vec(500, -1000, 0)
    b_angle = (a - b).angle_to(c - b)
    b_cross = (a - b) ** (c - b)
    c_angle = (b - c).angle_to(d - c)
    c_cross = (b - c) ** (d - c)

    spine = Path.from_pts([a, b, c, d])

    # I-Beam profiles at each control point
    p1 = IBeamProfile(height=200, width=100, flange_thickness=10, web_thickness=6)
    p2 = IBeamProfile(
        height=200 / math.sin(b_angle / 2),
        width=100,
        flange_thickness=12,
        web_thickness=8,
    )
    p3 = IBeamProfile(
        height=200,
        width=100 / math.sin(c_angle / 2),
        flange_thickness=12,
        web_thickness=8,
    )
    p4 = IBeamProfile(height=200, width=100, flange_thickness=12, web_thickness=8)

    # Positions: plane Z-axis = spine tangent at that point (extrusion direction).
    # Plane X and Y span the cross-section (profile lies in this plane).
    #
    # Use a fixed ref_direction so the cross-section X-axis stays consistent
    # (no flipping as tangent changes).  World Z = "up" for the profile:
    # the profile's X-axis will be the projection of (0,0,1) onto the
    # cross-section plane; the Y-axis follows from Z×X.
    ref_up = Vec(0, 1, 0)

    # At a: tangent ≈ +X (seg a→b)
    tan_a = (b - a).normalized()
    pos1 = Plane.from_origin_and_normal(a, tan_a, ref_direction=Vec(0, 1, 0))

    # At b: tangent in ≈ +X, tangent out ≈ +Z → average
    tan_b = ((b - a).normalized() + (c - b).normalized()).normalized()
    pos2 = Plane.from_origin_and_normal(b, tan_b, ref_direction=b_cross)

    # At c: tangent in ≈ +Z, tangent out ≈ -Y → average
    tan_c = ((c - b).normalized() + (d - c).normalized()).normalized()
    ref_x_c = -((b - c).normalized() + (d - c).normalized()).normalized()
    pos3 = Plane(c, ref_x_c, c_cross)

    # At d: tangent ≈ -Y (seg c→d)
    tan_d = (d - c).normalized()
    pos4 = Plane.from_origin_and_normal(d, tan_d, ref_direction=b_cross**c_cross)

    pending = PendingSectionedSpine(
        spine=spine,
        profiles=[p1, p2, p3, p4],
        positions=[pos1, pos2, pos3, pos4],
        name="ibeam_spine",
    )

    # Build via registry API
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    element = builder.build(ifc_file, pending, storey, context)

    geom_item = element.Representation.Representations[0].Items[0]
    print(f"  Element: {element.is_a()}")
    print(f"  Geometry: {geom_item.is_a()}")
    if geom_item.is_a() == "IfcTriangulatedFaceSet":
        print(f"    Vertices: {len(geom_item.Coordinates.CoordList)}")
        print(f"    Triangles: {len(geom_item.CoordIndex)}")

    model.save("output/test_sectioned_spine_ibeam.ifc")
    print("  Saved: output/test_sectioned_spine_ibeam.ifc\n")


if __name__ == "__main__":
    test_basic_spike()
    test_varying_profiles()
    test_ibeam_spine()
    print("All tests complete!")
