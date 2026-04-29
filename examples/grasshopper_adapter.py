"""
grasshopper_adapter.py
======================

Shared conversion helpers for using ifckit from Grasshopper Python 3
Script components (Rhino 8+).

This module is NOT runnable standalone — it imports Rhino types only
available inside the Rhino process.  See ``examples/gh_scripts/`` for
ready-to-paste GH Script component code.

Integration paths
-----------------
**Option A — ifckit on PyPI (future)**
Add at the top of every GH Script component::

    # requirements: ifckit

Grasshopper will pip-install ifckit automatically.

**Option B — local install (works today)**
Add at the top of every GH Script component::

    # env: /path/to/L140-py-ifckit

Replace the path with the absolute path to the repo root on your machine.
This adds the folder to ``sys.path`` so ``import ifckit`` works.

Typical GH component workflow
------------------------------
1. **Init** component — creates ``IfcModel``, stores it in ``sc.sticky``.
2. **Element** components — convert Rhino geometry → ``PendingElement``
   objects using the helpers below, accumulate them in a list.
3. **Export** component — iterates the list, calls ``storey.add(el)`` for
   each element, then calls ``model.export(path)``.

See ``examples/gh_scripts/`` for a complete working example of each step.

Coordinate system note
-----------------------
ifckit geometry is unitless — the caller decides the unit via ``LengthUnit``
on ``IfcModel``.  Rhino's default unit is metres; make sure your model unit
matches.  ``LengthUnit.MILLIMETRE`` is the IFC convention for structural work.
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
    # Derive y_axis from z × x so the frame matches the Rhino plane orientation.
    y_axis = z_axis.cross(x_axis).normalized()
    return Plane(origin=origin, x_axis=x_axis, y_axis=y_axis)


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
