"""
SectionedSpine auto — one-shot builder API.

The user supplies only:
  1. Spine control points (the path)
  2. A starter plane (initial cross-section orientation)
  3. A base profile (single instance)

``SectionedSpineBuilder.build_from_spine()`` handles everything:
  - Parallel-transport frames
  - Miter scaling at corners (via DerivedProfile)
  - Product creation with spatial containment

Usage:
    python examples/sectioned_spine_auto.py
"""

import uuid

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.geometry import Path, Plane, Vec, transport_frames
from ifckit.profiles import RectangleProfile, IBeamProfile
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.builders._geom import get_body_context


def _guid():
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _make_storey(ifc_file, project):
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


def main():
    print("=== SectionedSpine auto: build_from_spine() ===\n")

    # ---- Only these three inputs needed -----------------------------------
    pts = [
        Vec(0, 0, 0),
        Vec(2000, 0, 0),
        Vec(2000, 1000, 0),
        Vec(2000, 1000, 1000),
        Vec(2000, 0, 1000),
        Vec(3000, 0, 1000),
    ]
    spine = Path.from_pts(pts)

    # The starter plane provides the initial cross-section orientation.
    # Its .x_axis is used as the reference direction for parallel transport.
    starter = Plane(pts[0], Vec(0, 1, 0), Vec(0, 0, 1))

    profile = RectangleProfile(150, 300)  # single profile, cloned + scaled

    # ---- One call ----------------------------------------------------------
    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)
    context = get_body_context(ifc_file)

    builder = SectionedSpineBuilder()
    element = builder.build_from_spine(
        ifc_file,
        spine=spine,
        profile=profile,
        starter_plane=starter,
        storey=storey,
        context=context,
        name="auto_rect",
    )

    geom = element.Representation.Representations[0].Items[0]
    print(
        f"  RectangleProfile → {geom.is_a()}: "
        f"{len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles"
    )
    model.save("output/sectioned_spine_auto_rect.ifc")
    print("  Saved: output/sectioned_spine_auto_rect.ifc\n")

    # ---- I-Beam variant ----------------------------------------------------
    profile = IBeamProfile(height=200, width=100, flange_thickness=10, web_thickness=6)

    model2 = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file2 = model2.ifc_file
    storey2 = _make_storey(ifc_file2, model2._project)
    context2 = get_body_context(ifc_file2)

    builder = SectionedSpineBuilder()
    element2 = builder.build_from_spine(
        ifc_file2,
        spine=spine,
        profile=profile,
        starter_plane=starter,
        storey=storey2,
        context=context2,
        name="auto_ibeam",
    )

    geom2 = element2.Representation.Representations[0].Items[0]
    print(
        f"  IBeamProfile → {geom2.is_a()}: "
        f"{len(geom2.Coordinates.CoordList)} vertices, "
        f"{len(geom2.CoordIndex)} triangles"
    )
    model2.save("output/sectioned_spine_auto_ibeam.ifc")
    print("  Saved: output/sectioned_spine_auto_ibeam.ifc\n")

    # ---- Show what was auto-generated --------------------------------------
    field = transport_frames(pts, starter.x_axis)
    print("  Miter scaling (interior corners):")
    for i, (s, a) in enumerate(field.scales):
        if s > 1.0:
            print(f"    P{i}: scale {a} by {s:.3f}")


if __name__ == "__main__":
    main()
    print("Done.")
