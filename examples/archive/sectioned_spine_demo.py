"""
SectionedSpine demo — transport frames + miter compensation.

Shows how to build a swept solid along a 3D polyline path using
core ifckit functions.  Profiles are automatically scaled at corners
so the extrusion fills correctly (miter compensation).

Usage:
    python examples/sectioned_spine_demo.py
"""

from __future__ import annotations

import math
import uuid

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.elements import PendingSectionedSpine
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


def _print_table(pts, frames, scales):
    """Print a vertex-by-vertex table of frame info."""
    print("  Vertex |  Z (tangent/bisector)          | θ°int | scale | axis")
    print("  -------+--------------------------------+-------+-------+------")
    for i, (p, pl, (s, a)) in enumerate(zip(pts, frames, scales)):
        z = pl.z_axis
        if i == 0 or i == len(pts) - 1:
            print(
                f"  P{i}     | ({z.x:.3f},{z.y:.3f},{z.z:.3f})              |  —    | 1.000 |"
            )
        else:
            ba = pts[i - 1] - pts[i]
            bc = pts[i + 1] - pts[i]
            ang = math.degrees(ba.angle_to(bc))
            print(
                f"  P{i}     | ({z.x:.3f},{z.y:.3f},{z.z:.3f})              | {ang:3.0f}°  | {s:.3f} | {a}"
            )


# ---------------------------------------------------------------------------
# Demo: RectangleProfile
# ---------------------------------------------------------------------------


def main():
    print("=== SectionedSpine demo: transport frames + miter compensation ===\n")

    pts = [
        Vec(0, 0, 0),
        Vec(2000, 0, 0),
        Vec(2500, 1000, 0),
        Vec(3000, 1000, 1000),
    ]
    spine = Path.from_pts(pts)
    ref = Vec(0, 1, 0)

    # transport_frames returns FrameField with .frames and .scales
    field = transport_frames(pts, ref)
    _print_table(pts, field.frames, field.scales)

    # Build profiles — scales from the FrameField
    base_w, base_h = 150, 300
    profiles = []
    for s, a in field.scales:
        if s == 1.0:
            profiles.append(RectangleProfile(base_w, base_h))
        elif a == "y":
            # rotation around Y → miter along X → scale X (x_dim)
            profiles.append(RectangleProfile(base_w * s, base_h))
        else:
            # rotation around X → miter along Y → scale Y (y_dim)
            profiles.append(RectangleProfile(base_w, base_h * s))

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)
    pending = PendingSectionedSpine(
        spine=spine,
        profiles=profiles,
        positions=field.frames,
        name="miter_demo",
    )
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    element = builder.build(ifc_file, pending, storey, context)

    geom = element.Representation.Representations[0].Items[0]
    print(
        f"\n  IfcTriangulatedFaceSet: {len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles"
    )
    out = "output/sectioned_spine_demo.ifc"
    model.save(out)
    print(f"  Saved: {out}\n")


# ---------------------------------------------------------------------------
# Demo: IBeamProfile
# ---------------------------------------------------------------------------


def main_ibeam():
    """Same path with IBeamProfile (web = profile Y, flange = profile X)."""
    print("--- I-Beam variant ---\n")

    pts = [
        Vec(0, 0, 0),
        Vec(2000, 0, 0),
        Vec(2500, 1000, 0),
        Vec(3000, 1000, 1000),
    ]
    spine = Path.from_pts(pts)
    ref = Vec(0, 1, 0)
    field = transport_frames(pts, ref)

    base_h, base_w = 200, 100
    profiles = []
    for i, (s, a) in enumerate(field.scales):
        if s == 1.0:
            profiles.append(
                IBeamProfile(
                    height=base_h, width=base_w, flange_thickness=10, web_thickness=6
                )
            )
        elif a == "y":
            # rotation around Y → miter along X → scale X (width/flange)
            profiles.append(
                IBeamProfile(
                    height=base_h,
                    width=base_w * s,
                    flange_thickness=10,
                    web_thickness=6,
                )
            )
        else:
            # rotation around X → miter along Y → scale Y (height/web)
            profiles.append(
                IBeamProfile(
                    height=base_h * s,
                    width=base_w,
                    flange_thickness=10,
                    web_thickness=6,
                )
            )
        print(
            f"  P{i}: scale {a} by {s:.3f}  →  "
            f"IBeamProfile(height={base_h * s if a == 'y' else base_h:.1f}, "
            f"width={base_w * s if a == 'x' else base_w:.1f})"
        )

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    ifc_file = model.ifc_file
    storey = _make_storey(ifc_file, model._project)
    pending = PendingSectionedSpine(
        spine=spine,
        profiles=profiles,
        positions=field.frames,
        name="miter_demo_ibeam",
    )
    context = get_body_context(ifc_file)
    builder = SectionedSpineBuilder()
    element = builder.build(ifc_file, pending, storey, context)

    geom = element.Representation.Representations[0].Items[0]
    print(
        f"\n  IfcTriangulatedFaceSet: {len(geom.Coordinates.CoordList)} vertices, "
        f"{len(geom.CoordIndex)} triangles"
    )
    out = "output/sectioned_spine_demo_ibeam.ifc"
    model.save(out)
    print(f"  Saved: {out}\n")


if __name__ == "__main__":
    main()
    main_ibeam()
    print("Done.")
