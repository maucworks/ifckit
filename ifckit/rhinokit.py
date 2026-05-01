"""
ifckit.rhino_kit
================

Convert Rhino geometry to ifckit geometry types.

Used in Grasshopper scripts to convert Rhino curves to ifckit pending elements.

Usage::

    from ifckit import rhinnokit as rk

    # Polyline → list of Vec
    vecs = rk.polyline_to_vecs(rhino_curve)

    # Rhino Line → ifckit Line
    line = rk.line_to_line(rhino_line)

    # Rhino Arc → ifckit Arc
    arc = rk.arc_to_arc(rhino_arc)
"""

from __future__ import annotations

import math
from typing import Any, List

from ifckit.geometry import Arc, Line, Vec, Path
import Rhino.Geometry


def pt_to_vec(pt: Any) -> Vec:
    """Rhino Point3d → Vec."""
    return Vec(pt.X, pt.Y, pt.Z)


def vec_to_pt3d(vec: Vec) -> Any:
    """Vec → Rhino Point3d."""
    return Rhino.Geometry.Point3d(vec.x, vec.y, vec.z)


def pts_to_vecs(pts: Any) -> List[Vec]:
    """List of Rhino Point3d objects → list of Vec.

    Handles both open and closed point lists. If the last point equals
    the first (within tolerance), it's treated as closed and the
    duplicate endpoint is removed.
    """
    vecs = [pt_to_vec(p) for p in pts]
    if len(vecs) > 1:
        first, last = vecs[0], vecs[-1]
        if abs(first.x - last.x) < 1e-6 and abs(first.y - last.y) < 1e-6:
            vecs = vecs[:-1]
    return vecs


def polyline_to_footprint(crv: Any) -> List[Vec]:
    """Alias for polyline_to_vecs."""
    return polyline_to_vecs(crv)


def polyline_to_vecs(crv: Any) -> List[Vec]:
    """Rhino curve (Polyline/PolylineCurve) → list of Vec.

    Handles both open and closed polylines. If the polyline's last point
    equals the first (within tolerance), it's treated as closed and the
    duplicate endpoint is removed.
    """
    pl = crv.ToPolyline() if hasattr(crv, "ToPolyline") else crv
    pts = [pt_to_vec(p) for p in pl]

    if len(pts) > 1:
        first, last = pts[0], pts[-1]
        if abs(first.x - last.x) < 1e-6 and abs(first.y - last.y) < 1e-6:
            pts = pts[:-1]

    return pts


def line_to_line(rhino_line: Any) -> Line:
    """Rhino LineCurve → ifckit Line."""
    pt_a = rhino_line.PointAtStart
    pt_b = rhino_line.PointAtEnd
    return Line(pt_to_vec(pt_a), pt_to_vec(pt_b))


def arc_to_arc(rhino_arc: Any) -> Arc:
    """Rhino Arc or ArcCurve → ifckit Arc.

    Handles both Rhino Arc (primitive) and ArcCurve (geometry with curve methods).
    Uses .Arc property if available (ArcCurve), otherwise assumes it's already an Arc.

    """
    try:
        arc = rhino_arc.Arc
    except AttributeError:
        arc = rhino_arc

    rh_center = arc.Center
    rh_start = arc.StartPoint
    rh_end = arc.EndPoint
    rh_plane = arc.Plane
    rh_normal = rh_plane.Normal
    angle_rad = arc.Angle  # Rhino Arc.Angle is already in radians

    normal = Vec(rh_normal.X, rh_normal.Y, rh_normal.Z)

    return Arc(
        center=pt_to_vec(rh_center),
        normal=normal,
        start=pt_to_vec(rh_start),
        angle=angle_rad,
    )


def curve_to_segments(crv: Any) -> List[Any]:
    """Rhino curve → list of curve segments.

    For polycurves, explodes into individual segments.
    For single curves, returns a list with one element.
    """
    if hasattr(crv, "Explode"):
        segments = crv.Explode()
        if segments and len(segments) > 1:
            return list(segments)

    return [crv]


def curves_to_path(curves: Any) -> Path:
    """Convert a Rhino curve or iterable of Rhino curves into an ifckit Path.

    Handles single curves, lists/tuples of curves, and polycurves (exploded).
    Each segment is converted to an ifckit Line or Arc and appended to a Path.
    """
    # Normalize to an iterable
    if curves is None:
        return Path()
    if not hasattr(curves, "__iter__") or isinstance(curves, (str, bytes)):
        curves = [curves]

    p = Path()
    for crv in curves:
        if crv is None:
            continue
        segs = curve_to_segments(crv)
        for s in segs:
            # Rhino ArcCurve has Radius attribute; LineCurve does not
            if hasattr(s, "Radius") and getattr(s, "Radius", 0) > 0:
                arc = arc_to_arc(s)
                p.add_arc(arc.center, arc.normal, arc.start, arc.angle)
            else:
                line = line_to_line(s)
                p.add_line(line.start, line.end)

    return p
