"""
SectionedSpine with closed (looped) paths — visual testing example.

All spines are closed rectangles built from ``Path.from_pts(pts, closed=True)``.
The seam closes naturally via midpoint-padding — no end caps, no degenerate
barrels, all four corners properly miter-scaled.

Produces three IFC files in examples/output/:

  1. closed_rect_ibeam.ifc      — I-beam (H200) on a flat rectangle
  2. closed_rect_channel.ifc    — channel section on a flat square
  3. closed_3d_ibeam.ifc        — I-beam on a 3D frame, P6 filleted (R=400)
  4. closed_3d_filleted.ifc     — I-beam on a 3D frame, all 6 corners filleted

Usage:
    python examples/closed_polyline_ibeam.py

Visual check in Bonsai / any IFC viewer:
  - All four corners show proper miter scaling.
  - No end caps (the loop is closed).
  - Seam (at segment 0 midpoint) is invisible.
"""

from __future__ import annotations

import uuid

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import IBeamProfile
from ifckit.profiles.sections import CShapeProfile


def _guid() -> str:
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _make_storey(ifc_file: ifcopenshell.file, project) -> ifcopenshell.entity_instance:
    o = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    axis = ifc_file.create_entity("IfcAxis2Placement3D", Location=o, Axis=z, RefDirection=x)
    place = ifc_file.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=axis)
    storey = ifc_file.create_entity(
        "IfcBuildingStorey", GlobalId=_guid(), Name="Storey", ObjectPlacement=place
    )
    ifc_file.create_entity(
        "IfcRelAggregates", GlobalId=_guid(), RelatingObject=project, RelatedObjects=[storey]
    )
    return storey


def _build_and_save(spine, profile, starter, name, filename, angle_step_deg=3.0):
    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    storey = _make_storey(model.ifc_file, model._project)
    ctx = get_body_context(model.ifc_file)

    element = SectionedSpineBuilder().build_from_spine(
        model.ifc_file,
        spine=spine,
        profile=profile,
        starter_plane=starter,
        storey=storey,
        context=ctx,
        name=name,
        angle_step_deg=angle_step_deg,
        profile_segments=32,
    )
    geom = element.Representation.Representations[0].Items[0]
    print(
        f"  {name}: {len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles, "
        f"Closed={geom.Closed}"
    )
    model.save(f"output/{filename}")
    print(f"  Saved: output/{filename}")


# ---------------------------------------------------------------------------
# 1. Flat rectangle — I-beam
# ---------------------------------------------------------------------------


def build_rect_ibeam() -> None:
    """I-beam profile on a 4 m x 3 m flat rectangle in the XY plane."""
    pts = [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 3000, 0), Vec(0, 3000, 0)]
    spine = Path.from_pts(pts, closed=True)
    starter = Plane(Vec(0, 1500, 0), Vec(1, 0, 0), Vec(0, 0, 1))
    profile = IBeamProfile(height=200, width=100, flange_thickness=12, web_thickness=7)
    _build_and_save(spine, profile, starter, "closed_rect_ibeam", "closed_rect_ibeam.ifc")


# ---------------------------------------------------------------------------
# 2. Flat rectangle — channel
# ---------------------------------------------------------------------------


def build_rect_channel() -> None:
    """Channel profile on a 2 m x 2 m square."""
    pts = [Vec(0, 0, 0), Vec(2000, 0, 0), Vec(2000, 2000, 0), Vec(0, 2000, 0)]
    spine = Path.from_pts(pts, closed=True)
    starter = Plane(Vec(0, 1000, 0), Vec(1, 0, 0), Vec(0, 0, 1))
    profile = CShapeProfile(depth=150, width=60, wall_thickness=6, girth=20)
    _build_and_save(spine, profile, starter, "closed_rect_channel", "closed_rect_channel.ifc")


# ---------------------------------------------------------------------------
# 3. 3D rectangular frame — I-beam
# ---------------------------------------------------------------------------


def build_3d_ibeam() -> None:
    """I-beam on a 3D frame: rises in Z at two corners, filleted at P6."""
    pts = [
        Vec(0, 0, 0),
        Vec(4000, 0, 0),
        Vec(4000, 0, 2000),
        Vec(4000, 3000, 2000),
        Vec(4000, 3000, 3000),
        Vec(0, 3000, 3000),
        Vec(0, 3000, 0),
        Vec(0, 0, 0),
    ]
    pts = pts[:-1]
    spine = Path.from_pts(pts, closed=True)
    spine.fillet(6, 400)  # P6: corner between P5→P6 (-Z) and P6→P0 (-Y)
    mid = (pts[0] + pts[1]) * 0.5
    starter = Plane(mid, Vec(1, 0, 0), Vec(0, 0, 1))
    profile = IBeamProfile(height=200, width=100, flange_thickness=12, web_thickness=7)
    _build_and_save(spine, profile, starter, "closed_3d_ibeam", "closed_3d_ibeam.ifc")


# ---------------------------------------------------------------------------
# 4. 3D frame — all corners filleted
# ---------------------------------------------------------------------------


def build_3d_all_filleted() -> None:
    """I-beam on a 3D frame with R=400 fillets on all 6 addressable corners.

    The wrap-around corner at P0 (closing seg → seg[0]) stays sharp —
    it cannot be addressed by index in a closed path.
    """
    pts = [
        Vec(0, 0, 0),
        Vec(4000, 0, 0),
        Vec(4000, 0, 2000),
        Vec(4000, 3000, 2000),
        Vec(4000, 3000, 3000),
        Vec(0, 3000, 3000),
        Vec(0, 3000, 0),
        Vec(0, 0, 0),
    ]
    pts = pts[:-1]
    spine = Path.from_pts(pts, closed=True)
    # Fillet from highest index down — earlier indices stay valid
    for idx in range(6, 0, -1):
        spine.fillet(idx, 400)
    mid = (pts[0] + pts[1]) * 0.5
    starter = Plane(mid, Vec(1, 0, 0), Vec(0, 0, 1))
    profile = IBeamProfile(height=200, width=100, flange_thickness=12, web_thickness=7)
    _build_and_save(spine, profile, starter, "closed_3d_filleted", "closed_3d_filleted.ifc")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)

    print("=== SectionedSpine closed-loop examples ===\n")

    print("1. Flat rectangle — IBeamProfile H200 (4 m x 3 m):")
    build_rect_ibeam()

    print("\n2. Flat square — CShapeProfile 150x60 (2 m x 2 m):")
    build_rect_channel()

    print("\n3. 3D frame — IBeamProfile H200:")
    build_3d_ibeam()

    print("\n4. 3D frame — all 6 corners filleted (R=400):")
    build_3d_all_filleted()

    print(
        "\nDone. Open the .ifc files in Bonsai / any IFC viewer."
        "\nAll four corners should show miter scaling; no end caps."
    )
