"""
SectionedSpine with hollow (pipe) cross-section — visual testing example.

Demonstrates that HollowCircleProfile (tube / CHS) correctly produces a
closed hollow mesh: outer barrel, inner barrel, and annular end caps — no
solid-disc caps, no missing walls.

Produces three IFC files in examples/output/:

  1. pipe_straight.ifc   — straight run, DN100 pipe (Ø114.3 × 6.3 mm wall)
  2. pipe_bend.ifc       — 90° filleted corner, R=500, same pipe section
  3. pipe_s_curve.ifc    — S-bend, two 90° fillets, R=300, same section

Usage:
    python examples/sectioned_spine_pipe.py

Visual check in Bonsai / any IFC viewer:
  - Inner bore must be visible at each open end (annular cap = ring, not disc).
  - Outer and inner cylinder surfaces both present.
  - No capping artefacts at the bend.
"""
from __future__ import annotations

import uuid

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles.shapes import HollowCircleProfile


def _guid() -> str:
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


def _make_storey(ifc_file: ifcopenshell.file, project) -> ifcopenshell.entity_instance:
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
    )
    geom = element.Representation.Representations[0].Items[0]
    print(
        f"  {name}: {len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles"
    )
    model.save(f"output/{filename}")
    print(f"  Saved: output/{filename}")


# DN100 CHS: OD = 114.3 mm, wall = 6.3 mm  → radius = 57.15 mm
PIPE = HollowCircleProfile(radius=57.15, wall_thickness=6.3)


# ---------------------------------------------------------------------------
# 1. Straight run
# ---------------------------------------------------------------------------

def build_straight() -> None:
    """Simple straight pipe, 3000 mm long, running along +X."""
    pts = [Vec(0, 0, 0), Vec(3000, 0, 0)]
    spine = Path.from_pts(pts)

    # starter_plane: spine goes +X; profile Y = world Z (pipe stands upright)
    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    _build_and_save(spine, PIPE, starter, "pipe_straight", "pipe_straight.ifc")


# ---------------------------------------------------------------------------
# 2. 90° bend — single filleted corner
# ---------------------------------------------------------------------------

def build_bend() -> None:
    """Pipe making a 90° turn in the XY plane, R=500 mm fillet."""
    pts = [Vec(0, 0, 0), Vec(2000, 0, 0), Vec(2000, 2000, 0)]
    spine = Path.from_pts(pts)
    spine.fillet(1, 500)

    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    _build_and_save(spine, PIPE, starter, "pipe_bend", "pipe_bend.ifc")


# ---------------------------------------------------------------------------
# 3. S-curve — two opposite 90° fillets
# ---------------------------------------------------------------------------

def build_s_curve() -> None:
    """S-shaped pipe: two 90° turns in opposite directions, R=300 mm fillet."""
    pts = [Vec(0, 0, 0), Vec(1500, 0, 0), Vec(1500, 3000, 0), Vec(3000, 3000, 0)]
    spine = Path.from_pts(pts)
    spine.fillet(1, 300)
    spine.fillet(3, 300)  # index 3 after first fillet added 1 segment

    starter = Plane(pts[0], Vec(1, 0, 0), Vec(0, 0, 1))
    _build_and_save(spine, PIPE, starter, "pipe_s_curve", "pipe_s_curve.ifc")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)

    print("=== SectionedSpine pipe (hollow) examples ===\n")
    print("Profile: DN100 CHS  OD=114.3 mm  wall=6.3 mm\n")

    print("1. Straight run (3000 mm):")
    build_straight()

    print("\n2. 90° bend (R=500 mm):")
    build_bend()

    print("\n3. S-curve (two 90° fillets, R=300 mm):")
    build_s_curve()

    print(
        "\nDone. Open the .ifc files in Bonsai / any IFC viewer."
        "\nInner bore should be visible at each open end."
    )
