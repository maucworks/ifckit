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


def test_basic_spike():
    """Basic SectionedSpine - uniform profile along straight spine."""
    print("=== Test 1: Basic Spine ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file

    # Spine: straight line 0 to 1000
    spine = Path.from_pts([Vec(0, 0, 0), Vec(0, 0, 500)])

    # Two identical profiles
    p1 = RectangleProfile(50, 70)
    p2 = RectangleProfile(50, 70)

    # Positions along spine
    pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos2 = Plane(Vec(1000, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

    pending = PendingSectionedSpine(
        spine=spine, profiles=[p1, p2], positions=[pos1, pos2], name="basic_spine"
    )

    # Build
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    shape = builder._create_geometry(ifc_file, pending, None, context)
    # shape is now IfcProductDefinitionShape

    element = ifc_file.create_entity(
        "IfcBuildingElementProxy",
        Name=pending.name,
        Representation=shape,
    )

    print(f"  Element: {element.is_a()} - {element.Name}")
    # Get the actual geometry from the representation
    geom_item = shape.Representations[0].Items[0]
    print(f"  Spine: {geom_item.is_a()}")

    model.save("output/test_sectioned_spine_basic.ifc")
    print("  Saved: output/test_sectioned_spine_basic.ifc\n")


def test_varying_profiles():
    """SectionedSpine with varying profiles along spine."""
    print("=== Test 2: Varying Profiles ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file

    # Spine: straight line
    spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0)])

    # Profile 1: base
    p1 = RectangleProfile(50, 70)

    # Profile 2: scaled 1.5x
    p2 = DerivedProfile(RectangleProfile(50, 70), scale=1.5)

    # Profile 3: scaled 2x
    p3 = DerivedProfile(RectangleProfile(50, 70), scale=2.0)

    # Positions
    pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos2 = Plane(Vec(500, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos3 = Plane(Vec(1000, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

    pending = PendingSectionedSpine(
        spine=spine,
        profiles=[p1, p2, p3],
        positions=[pos1, pos2, pos3],
        name="varying_spine",
    )

    # Build
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    shape = builder._create_geometry(ifc_file, pending, None, context)
    # shape is now IfcProductDefinitionShape

    element = ifc_file.create_entity(
        "IfcBuildingElementProxy",
        Name=pending.name,
        Representation=shape,
    )

    geom_item = shape.Representations[0].Items[0]
    print(f"  Element: {element.is_a()}")
    print(f"  Geometry: {geom_item.is_a()}")
    if geom_item.is_a() == "IfcPolygonalFaceSet":
        print(f"    Vertices: {len(geom_item.Coordinates.CoordList)}")
        print(f"    Faces: {len(geom_item.Faces)}")

    model.save("output/test_sectioned_spine_varying.ifc")
    print("  Saved: output/test_sectioned_spine_varying.ifc\n")


def test_ibeam_spike():
    """SectionedSpine with I-beam profiles."""
    print("=== Test 3: I-Beam Spine ===")

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file

    # Spine
    spine = Path.from_pts([Vec(0, 0, 0), Vec(2000, 0, 0)])

    # I-Beam profiles (start small, end larger)
    p1 = IBeamProfile(height=100, width=100, flange_thickness=10, web_thickness=6)
    p2 = IBeamProfile(height=150, width=150, flange_thickness=12, web_thickness=8)

    # Positions
    pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos2 = Plane(Vec(2000, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

    pending = PendingSectionedSpine(
        spine=spine, profiles=[p1, p2], positions=[pos1, pos2], name="ibeam_spine"
    )

    # Build
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    shape = builder._create_geometry(ifc_file, pending, None, context)
    # shape is now IfcProductDefinitionShape

    element = ifc_file.create_entity(
        "IfcBuildingElementProxy",
        Name=pending.name,
        Representation=shape,
    )

    geom_item = shape.Representations[0].Items[0]
    print(f"  Element: {element.is_a()}")
    print(f"  Geometry: {geom_item.is_a()}")
    if geom_item.is_a() == "IfcPolygonalFaceSet":
        print(f"    Vertices: {len(geom_item.Coordinates.CoordList)}")
        print(f"    Faces: {len(geom_item.Faces)}")

    model.save("output/test_sectioned_spine_ibeam.ifc")
    print("  Saved: output/test_sectioned_spine_ibeam.ifc\n")


if __name__ == "__main__":
    test_basic_spike()
    test_varying_profiles()
    test_ibeam_spike()
    print("All tests complete!")
