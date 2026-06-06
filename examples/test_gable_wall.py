#!/usr/bin/env python3
"""
Gable wall test — trace exact wall graph geometry from user's world_xz() path.

Generates an IFC file and prints the 3D coordinates of the resulting solid
so we can verify the profile orientation.
"""

import os
import sys

import ifcopenshell

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context, profile_from_points
from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.geometry import Path, Plane, Vec


def inspect_profile_coords(ifc_file, profile_entity, label):
    """Walk an IfcProfileDef and print the 2D contour points."""
    if profile_entity.is_a("IfcArbitraryClosedProfileDef"):
        curves = [profile_entity.OuterCurve]
    elif profile_entity.is_a("IfcArbitraryProfileDefWithVoids"):
        curves = [profile_entity.OuterCurve] + list(profile_entity.InnerCurves)
    else:
        print(f"  Unknown profile type: {profile_entity.is_a()}")
        return

    for ci, curve in enumerate(curves):
        tag = "outer" if ci == 0 else f"hole-{ci}"
        if curve.is_a("IfcCompositeCurve"):
            for seg in curve.Segments:
                parent = seg.ParentCurve
                if parent.is_a("IfcPolyline"):
                    for pt in parent.Points:
                        c = pt.Coordinates
                        print(f"    {tag}: ({c[0]:.4f}, {c[1]:.4f})")
                elif parent.is_a("IfcTrimmedCurve"):
                    circle = parent.BasisCurve
                    pos = circle.Position
                    loc = pos.Location.Coordinates
                    print(f"    {tag}: arc center=({loc[0]:.4f}, {loc[1]:.4f}) r={circle.Radius:.4f}")
        elif curve.is_a("IfcPolyline"):
            for pt in curve.Points:
                c = pt.Coordinates
                print(f"    {tag}: ({c[0]:.4f}, {c[1]:.4f})")


def inspect_extruded_solid(ifc_file, label):
    """Find the IfcExtrudedAreaSolid and report its full details."""
    solids = list(ifc_file.by_type("IfcExtrudedAreaSolid"))
    if not solids:
        print(f"\n  [{label}] No IfcExtrudedAreaSolid found!")
        return

    for i, solid in enumerate(solids):
        print(f"\n[{label}] IfcExtrudedAreaSolid #{i}:")
        pos = solid.Position
        loc = pos.Location.Coordinates
        axis = pos.Axis.DirectionRatios if pos.Axis else "N/A"
        ref = pos.RefDirection.DirectionRatios if pos.RefDirection else "N/A"
        ed = solid.ExtrudedDirection.DirectionRatios
        print(f"  Position Location: ({loc[0]:.4f}, {loc[1]:.4f}, {loc[2]:.4f})")
        print(f"  Position Axis (Z): {[round(a,4) for a in axis]}")
        print(f"  Position RefDir(X): {[round(r,4) for r in ref]}")
        print(f"  ExtrudedDirection:  {[round(d,4) for d in ed]}")
        print(f"  Depth:              {solid.Depth:.4f}")

        profile_entity = solid.SweptArea
        print(f"  ProfileType:  {profile_entity.is_a()}")
        inspect_profile_coords(ifc_file, profile_entity, label)


def main():
    os.makedirs("output", exist_ok=True)

    # ── Params (model: 1 unit = 1 m) ─────────────────────────────────
    breedte = 4.0
    diepte = 8.0
    radius = 1.0
    hoogte = 3.0
    nok_hoogte = 4.0
    dikte = 0.3

    # ── Build path ───────────────────────────────────────────────────
    plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
    pts = [
        Vec(0, 0, 0),
        Vec(breedte, 0, 0),
        Vec(breedte, hoogte, 0),
        Vec(0.5 * breedte, nok_hoogte, 0),
        Vec(0, hoogte, 0),
    ]
    outer = Path.from_pts(pts, plane=plane, closed=True)
    outer.fillet([0, 1, 2, 3, 4], radius)

    print("=== Path vertex world coords (after from_pts + fillet) ===")
    for i, seg in enumerate(outer._segments):
        print(f"  seg[{i}]: {seg}")

    print(f"\nPath plane: x={outer._plane.x_axis} y={outer._plane.y_axis}")
    print(f"  -> z_axis = x × y = {outer._plane.z_axis}")

    print(f"\nPath offset(-{dikte}) = outer edge:")
    offset_outer = outer.offset(-dikte)
    for i, seg in enumerate(offset_outer._segments):
        print(f"  seg[{i}]: {seg}")

    # ── Build wall graph ─────────────────────────────────────────────
    muur = PendingWallGraph(
        path=outer,
        offset_right=0,
        offset_left=dikte,
        height=diepte,
        name="Arc_wall",
        angle_step_deg=5.0,
    )

    # ── Generate IFC ─────────────────────────────────────────────────
    model = IfcModel(unit=LengthUnit.METRE)
    site = model.add_site(name="Site")
    building = model.add_building(site, name="Building")
    storey = model.add_storey(building, name="Storey", elevation=0.0)
    ctx = get_body_context(model.ifc_file)

    handle = model.add(muur, storey)
    filename = "test_gable_wall.ifc"
    model.save(f"output/{filename}")
    print(f"\nSaved: {filename}")

    # ── Inspect ──────────────────────────────────────────────────────
    inspect_extruded_solid(model.ifc_file, "gable-wall")

    # ── Also test with world_xy() for comparison ─────────────────────
    print("\n" + "=" * 60)
    print("Comparing with world_xy() (path in XY plane)")
    plane_xy = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pts_xy = [
        Vec(0, 0, 0),
        Vec(breedte, 0, 0),
        Vec(breedte, hoogte, 0),
        Vec(0.5 * breedte, nok_hoogte, 0),
        Vec(0, hoogte, 0),
    ]
    outer_xy = Path.from_pts(pts_xy, plane=plane_xy, closed=True)

    print(f"\nPathXY plane: x={outer_xy._plane.x_axis} y={outer_xy._plane.y_axis}")
    print(f"  -> z_axis = {outer_xy._plane.z_axis}")

    muur_xy = PendingWallGraph(
        path=outer_xy,
        offset_right=0,
        offset_left=dikte,
        height=diepte,
        name="Arc_wall_xy",
        angle_step_deg=5.0,
    )

    model2 = IfcModel(unit=LengthUnit.METRE)
    site2 = model2.add_site(name="Site")
    building2 = model2.add_building(site2, name="Building")
    storey2 = model2.add_storey(building2, name="Storey", elevation=0.0)
    ctx2 = get_body_context(model2.ifc_file)

    handle2 = model2.add(muur_xy, storey2)
    filename2 = "test_gable_wall_xy.ifc"
    model2.save(f"output/{filename2}")
    print(f"Saved: {filename2}")

    inspect_extruded_solid(model2.ifc_file, "gable-wall-xy")


if __name__ == "__main__":
    main()
