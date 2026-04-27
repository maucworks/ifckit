"""
grasshopper_adapter.py
======================

Shows how to use ifckit from a Grasshopper Python component (GHPython).

This file is NOT runnable standalone — it uses Rhino/Grasshopper types
(``rg.Point3d``, ``rg.LineCurve``, ``rg.Arc``, ``rg.Polyline``) that only
exist inside Rhino.  Read it as annotated pseudocode.

Pattern
-------
The adapter is a thin translation layer.  It converts Rhino geometry objects
to ifckit primitives, builds a ``PendingElement``, validates it, and hands it
to a shared ``IfcModel``.  The model is kept in the GH script's ``sticky``
dictionary so it persists across GH solver runs.

Typical GH component workflow
------------------------------
1.  One "Init" component creates the IfcModel and stores it in sticky.
2.  Per-element components (Wall, Beam, …) convert Rhino geometry → ifckit
    pending elements → stored in a list.
3.  A "Build" component calls builders on all pending elements and saves.

Usage inside a GHPython component::

    # Component inputs:
    #   wall_curves  : list of rg.Curve  (closed planar footprints)
    #   height       : float
    #   run          : bool  (button to trigger export)

    import scriptcontext as sc
    import Rhino.Geometry as rg

    # sys.path must include the ifckit package directory — set via GH Python path
    from examples.grasshopper_adapter import (
        rhino_point_to_vec,
        rhino_polyline_to_footprint,
        rhino_line_to_axis,
        make_wall,
        make_beam,
    )
    from ifckit import IfcModel, IfcSchema
    from ifckit.geometry import Plane

    if "ifc_model" not in sc.sticky:
        sc.sticky["ifc_model"] = IfcModel("GH Project", IfcSchema.IFC4, "GH")
        site = sc.sticky["ifc_model"].add_site("Site")
        bldg = sc.sticky["ifc_model"].add_building(site, "Building")
        sc.sticky["storey"] = sc.sticky["ifc_model"].add_storey(bldg, "L0")

    model  = sc.sticky["ifc_model"]
    storey = sc.sticky["storey"]

    pending_walls = [
        make_wall(crv, height=height)
        for crv in wall_curves
        if crv is not None
    ]

    if run:
        from ifckit.builders import default_registry
        from ifckit.builders._geom import get_body_context
        reg = default_registry()
        ctx = get_body_context(model.ifc_file)
        for pw in pending_walls:
            reg.get("basic_wall").build(model.ifc_file, pw, storey.entity, ctx)
        model.save(r"C:\\output\\gh_export.ifc")
        print("Exported!")
"""

from __future__ import annotations

from typing import List, Optional

# ifckit imports — these work in plain Python and in GHPython
from ifckit import PendingWall, PendingBeam, PendingColumn, validate
from ifckit.geometry import Vec, Plane, Line


# ---------------------------------------------------------------------------
# Primitive converters  (Rhino → ifckit)
# ---------------------------------------------------------------------------

def rhino_point_to_vec(pt) -> Vec:
    """
    Convert a ``Rhino.Geometry.Point3d`` to an ifckit ``Vec``.

    Args:
        pt:  Rhino.Geometry.Point3d

    Returns:
        Vec(pt.X, pt.Y, pt.Z)
    """
    return Vec(pt.X, pt.Y, pt.Z)


def rhino_vector_to_vec(v) -> Vec:
    """
    Convert a ``Rhino.Geometry.Vector3d`` to an ifckit ``Vec``.
    """
    return Vec(v.X, v.Y, v.Z)


def rhino_polyline_to_footprint(polyline) -> List[Vec]:
    """
    Convert a ``Rhino.Geometry.Polyline`` or a closed ``NurbsCurve``
    to a list of ifckit ``Vec`` points (the footprint).

    The last point is dropped if it duplicates the first (closed polyline).

    Args:
        polyline:  Rhino.Geometry.Polyline or .PolylineCurve

    Returns:
        List of Vec — at least 3 points, no closing duplicate.
    """
    # Support both Polyline and PolylineCurve
    if hasattr(polyline, "ToPolyline"):
        polyline = polyline.ToPolyline()

    pts = [rhino_point_to_vec(p) for p in polyline]

    # Drop the closing repeat if present
    if len(pts) > 1:
        first, last = pts[0], pts[-1]
        if abs(first.x - last.x) < 1e-6 and abs(first.y - last.y) < 1e-6:
            pts = pts[:-1]

    return pts


def rhino_line_to_axis(line) -> Line:
    """
    Convert a ``Rhino.Geometry.Line`` to an ifckit ``Line``.

    Args:
        line:  Rhino.Geometry.Line

    Returns:
        ifckit.Line(start, end)
    """
    return Line(
        start=rhino_point_to_vec(line.From),
        end=rhino_point_to_vec(line.To),
    )


def rhino_plane_to_plane(rg_plane) -> Plane:
    """
    Convert a ``Rhino.Geometry.Plane`` to an ifckit ``Plane``.
    """
    origin = rhino_point_to_vec(rg_plane.Origin)
    x_axis = rhino_vector_to_vec(rg_plane.XAxis)
    z_axis = rhino_vector_to_vec(rg_plane.ZAxis)
    return Plane(origin=origin, x_axis=x_axis, z_axis=z_axis)


# ---------------------------------------------------------------------------
# Element factories
# ---------------------------------------------------------------------------

def make_wall(
    footprint_curve,
    height: float,
    name: str = "",
    plane=None,
) -> PendingWall:
    """
    Create a validated ``PendingWall`` from a Rhino closed curve footprint.

    Args:
        footprint_curve:  Rhino.Geometry.Polyline or PolylineCurve
                          representing the wall's base footprint.
        height:           Wall height in metres.
        name:             Optional element name.
        plane:            Rhino.Geometry.Plane for placement;
                          defaults to world XY.

    Returns:
        PendingWall  (validated — raises AssertionError if invalid)
    """
    footprint = rhino_polyline_to_footprint(footprint_curve)
    ifc_plane = rhino_plane_to_plane(plane) if plane is not None else Plane.world_xy()

    wall = PendingWall(
        footprint=footprint,
        plane=ifc_plane,
        height=float(height),
        name=name,
    )

    result = validate(wall)
    assert result.ok, f"PendingWall '{name}' invalid: {result.errors}"
    for w in result.warnings:
        print(f"[WARN] PendingWall '{name}': {w}")

    return wall


def make_beam(
    line,
    profile_curve,
    name: str = "",
) -> PendingBeam:
    """
    Create a validated ``PendingBeam`` from a Rhino line axis and a profile
    polyline (cross-section, typically in the local YZ plane).

    Args:
        line:           Rhino.Geometry.Line — the beam axis.
        profile_curve:  Rhino.Geometry.Polyline — cross-section outline.
        name:           Optional element name.

    Returns:
        PendingBeam  (validated)
    """
    axis = rhino_line_to_axis(line)
    profile = rhino_polyline_to_footprint(profile_curve)

    beam = PendingBeam(axis=axis, profile=profile, name=name)

    result = validate(beam)
    assert result.ok, f"PendingBeam '{name}' invalid: {result.errors}"
    for w in result.warnings:
        print(f"[WARN] PendingBeam '{name}': {w}")

    return beam


def make_column(
    line,
    profile_curve,
    name: str = "",
) -> PendingColumn:
    """
    Create a validated ``PendingColumn`` from a Rhino line axis and a profile
    polyline.
    """
    axis = rhino_line_to_axis(line)
    profile = rhino_polyline_to_footprint(profile_curve)

    col = PendingColumn(axis=axis, profile=profile, name=name)

    result = validate(col)
    assert result.ok, f"PendingColumn '{name}' invalid: {result.errors}"
    for w in result.warnings:
        print(f"[WARN] PendingColumn '{name}': {w}")

    return col
