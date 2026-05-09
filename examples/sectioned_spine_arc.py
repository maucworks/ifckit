"""
SectionedSpine with filleted corners — visual testing example.

All curved spines are built with ``Path.from_pts([...])`` followed by
``path.fillet(index, radius)`` calls.  No manual arc geometry needed.

Produces four IFC files in examples/output/:

  1. fillet_single_corner.ifc   — 90° corner, R=2000, rectangular profile
  2. fillet_line_arc_line.ifc   — straight + 90° fillet + straight, I-beam
  3. fillet_s_curve.ifc         — two opposite 90° fillets (S-shape), channel profile
  4. fillet_multi_corner.ifc    — 7-point polyline, all interior corners filleted,
                                   rectangular profile (same spine as sectioned_spine_auto.py)

Usage:
    python examples/sectioned_spine_arc.py

Visual check in Bonsai / any IFC viewer:
  - fillet_single_corner  : smooth 90° bend, rectangular cross-section.
  - fillet_line_arc_line  : two straight runs connected by a smooth arc, I-beam.
  - fillet_s_curve        : S-bend, channel cross-section.
  - fillet_multi_corner   : complex 3D path, all sharp corners rounded.
"""
from __future__ import annotations

import uuid

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import IBeamProfile, RectangleProfile
from ifckit.profiles.sections import CShapeProfile


def _guid() -> str:
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _make_storey(ifc_file: ifcopenshell.file, project) -> ifcopenshell.entity_instance:
    """Create a minimal IfcBuildingStorey at Z=0."""
    o = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    axis = ifc_file.create_entity("IfcAxis2Placement3D", Location=o, Axis=z, RefDirection=x)
    place = ifc_file.create_entity(
        "IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=axis
    )
    storey = ifc_file.create_entity(
        "IfcBuildingStorey", GlobalId=_guid(), Name="Storey", ObjectPlacement=place
    )
    ifc_file.create_entity(
        "IfcRelAggregates", GlobalId=_guid(), RelatingObject=project, RelatedObjects=[storey]
    )
    return storey


def _build_and_save(
    spine: Path,
    profile,
    starter: Plane,
    name: str,
    filename: str,
    angle_step_deg: float = 3.0,
) -> None:
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
    )
    geom = element.Representation.Representations[0].Items[0]
    print(
        f"  {name}: {len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles"
    )
    model.save(f"output/{filename}")
    print(f"  Saved: output/{filename}")


# ---------------------------------------------------------------------------
# 1. Single 90° filleted corner — rectangular profile
# ---------------------------------------------------------------------------

def build_single_corner() -> None:
    """L-shaped spine with one 90° corner filleted to R=2000.

    Spine control points:
        (0, 0, 0) → (4000, 0, 0) → (4000, 4000, 0)

    fillet(1, 2000) rounds the corner at index 1.
    Profile Y = world Z (cross-section stands upright).
    """
    pts = [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 4000, 0)]
    spine = Path.from_pts(pts)
    spine.fillet(1, 2000)

    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    profile = RectangleProfile(80, 200)

    _build_and_save(spine, profile, starter, "fillet_single_corner", "fillet_single_corner.ifc")


# ---------------------------------------------------------------------------
# 2. Line + filleted corner + line — I-beam profile
# ---------------------------------------------------------------------------

def build_line_fillet_line() -> None:
    """Straight run → 90° filleted corner → straight run, all in XY plane.

    Spine control points:
        (0, 0, 0) → (3000, 0, 0) → (3000, 4500, 0)

    fillet(1, 1500) replaces the sharp corner with a smooth R=1500 arc.
    """
    pts = [Vec(0, 0, 0), Vec(3000, 0, 0), Vec(3000, 4500, 0)]
    spine = Path.from_pts(pts)
    spine.fillet(1, 1500)

    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    profile = IBeamProfile(height=200, width=100, flange_thickness=12, web_thickness=7)

    _build_and_save(spine, profile, starter, "fillet_line_arc_line", "fillet_line_arc_line.ifc")


# ---------------------------------------------------------------------------
# 3. S-curve — two opposite filleted corners — channel profile
# ---------------------------------------------------------------------------

def build_s_curve() -> None:
    """S-shaped spine: two 90° corners in opposite directions, both filleted.

    Spine control points:
        (0, 0, 0) → (1500, 0, 0) → (1500, 3000, 0) → (3000, 3000, 0)

    fillet(1, 1000) rounds the first corner (right turn).
    fillet(3, 1000) rounds the second corner (left turn) — index 3 because
    the first fillet added one segment, shifting the second corner by +2.
    """
    pts = [Vec(0, 0, 0), Vec(1500, 0, 0), Vec(1500, 3000, 0), Vec(3000, 3000, 0)]
    spine = Path.from_pts(pts)
    spine.fillet(1, 1000)   # first corner: between seg[0] and seg[1]
    spine.fillet(3, 1000)   # second corner: shifted to seg[3] after first fillet

    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    profile = CShapeProfile(depth=150, width=60, wall_thickness=6, girth=20)

    _build_and_save(spine, profile, starter, "fillet_s_curve", "fillet_s_curve.ifc")


# ---------------------------------------------------------------------------
# 4. Complex 3D path — all interior corners filleted — rectangular profile
# ---------------------------------------------------------------------------

def build_multi_corner() -> None:
    """The 9-point 3D spine from sectioned_spine_auto.py with all 7 interior
    corners rounded to R=300.

    Spine control points (same as the auto example):
        P0 (0,    0,    0)
        P1 (2000, 0,    0)
        P2 (2000, 1000, 0)
        P3 (2000, 1000, 1000)
        P4 (2000, 0,    1000)
        P5 (3000, 0,    1000)
        P6 (4000, 1000, 1000)
        P7 (5000, 1000, 500)
        P8 (6000, 0,    0)

    Each fillet(i, R) call adds 1 segment, so the next corner's index
    increases by 2.  Starting at index 1, the pattern is:
        fillet(1) → fillet(3) → fillet(5) → ... → fillet(15)
    """
    pts = [
        Vec(0,    0,    0),
        Vec(2000, 0,    0),
        Vec(2000, 1000, 0),
        Vec(2000, 1000, 1000),
        Vec(2000, 0,    1000),
        Vec(3000, 0,    1000),
        Vec(4000, 1000, 1000),
        Vec(5000, 1000, 500),
        Vec(6000, 0,    0),
    ]
    spine = Path.from_pts(pts)

    R = 300  # fillet radius applied to all 7 interior corners
    # Interior corners: indices 1..7 in the original path.
    # Each fillet shifts subsequent indices by +2.
    for corner in range(7):
        seg_index = 1 + corner * 2
        spine.fillet(seg_index, R)

    starter = Plane(pts[0], Vec(0, 0, 1), Vec(0, -1, 0))
    profile = RectangleProfile(150, 300)

    _build_and_save(
        spine, profile, starter,
        "fillet_multi_corner", "fillet_multi_corner.ifc",
        angle_step_deg=3.0,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)

    print("=== SectionedSpine fillet examples ===\n")

    print("1. Single 90° filleted corner (RectangleProfile 80×200, R=2000):")
    build_single_corner()

    print("\n2. Line + fillet + line (IBeamProfile H200 B100, R=1500):")
    build_line_fillet_line()

    print("\n3. S-curve — two opposite fillets (CShapeProfile 150×60, R=1000):")
    build_s_curve()

    print("\n4. Complex 3D path — 7 corners filleted (RectangleProfile 150×300, R=300):")
    build_multi_corner()

    print("\nDone. Open the .ifc files in Bonsai / any IFC viewer for visual inspection.")
