"""
ifckit.builders._geom
====================

Low-level ifcopenshell geometry helpers shared across builders.
Creates IfcCartesianPoint, IfcDirection, IfcAxis2Placement3D, etc.

Coordinate Precision
-------------------
By default, coordinates are rounded to 4 decimal places (0.1mm precision).
Since ifckit uses millimeters as its internal unit, 4 decimal places in
the IFC output (meters) = 0.1mm precision.

Adjust precision with set_precision()::

    from ifckit.builders import set_precision

    set_precision(3)  # 3 decimals = 1mm precision
    set_precision(4)  # 4 decimals = 0.1mm precision (default)
    set_precision(6)  # 6 decimals = 1μm precision
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List, Sequence

import ifcopenshell

if TYPE_CHECKING:
    from ifckit.geometry import Arc, Line, Path, Plane, Vec


# Coordinate precision: decimal places in IFC output (meters)
# 4 = 0.1mm precision (default for mm-based projects)
_PRECISION = 4


def set_precision(decimals: int) -> None:
    """
    Set coordinate output precision.

    Args:
        decimals: Number of decimal places (0-10). Higher = more precision.
                 3 = 1mm, 4 = 0.1mm, 6 = 1μm.

    Raises:
        ValueError: If decimals is not in range 0-10.
    """
    global _PRECISION
    if not isinstance(decimals, int):
        raise TypeError(f"decimals must be int, got {type(decimals).__name__}")
    if decimals < 0 or decimals > 10:
        raise ValueError(f"decimals must be 0-10, got {decimals}")
    _PRECISION = decimals


def get_precision() -> int:
    """Return current coordinate precision (decimal places)."""
    return _PRECISION


def _round_coord(value: float) -> float:
    """Round a coordinate value to current precision."""
    return float(round(value, _PRECISION))


def pt2(f: ifcopenshell.file, x: float, y: float) -> ifcopenshell.entity_instance:
    return f.create_entity("IfcCartesianPoint", Coordinates=[_round_coord(x), _round_coord(y)])


def pt3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    return f.create_entity(
        "IfcCartesianPoint",
        Coordinates=[_round_coord(x), _round_coord(y), _round_coord(z)],
    )


def dir3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    return f.create_entity(
        "IfcDirection",
        DirectionRatios=[_round_coord(x), _round_coord(y), _round_coord(z)],
    )


def axis2placement3d(
    f: ifcopenshell.file,
    origin: "Vec",
    z_axis: "Vec",
    x_axis: "Vec",
) -> ifcopenshell.entity_instance:
    """Create IfcAxis2Placement3D from ifckit Vec objects."""
    return f.create_entity(
        "IfcAxis2Placement3D",
        Location=pt3(f, origin.x, origin.y, origin.z),
        Axis=dir3(f, z_axis.x, z_axis.y, z_axis.z),
        RefDirection=dir3(f, x_axis.x, x_axis.y, x_axis.z),
    )


def local_placement(
    f: ifcopenshell.file,
    plane: "Plane",
    relative_to: ifcopenshell.entity_instance | None = None,
) -> ifcopenshell.entity_instance:
    """Create IfcLocalPlacement from a Plane."""
    ax = axis2placement3d(f, plane.origin, plane.z_axis, plane.x_axis)
    return f.create_entity("IfcLocalPlacement", PlacementRelTo=relative_to, RelativePlacement=ax)


def shift_plane_elevation(plane: "Plane", elev: float) -> "Plane":
    """Return a copy of *plane* with its origin shifted by ``-elev`` in Z.

    Used by builders to convert a world-space plane to storey-local coordinates
    (subtract the storey elevation from the origin Z component).
    """
    from ifckit.geometry import Vec

    local_origin = Vec(plane.origin.x, plane.origin.y, plane.origin.z - elev)
    return plane.__class__(local_origin, plane.x_axis, plane.y_axis)


def _signed_area_2d(points: Sequence[tuple[float, float]]) -> float:
    """Compute signed area of a polygon (shoelace formula). Positive = CCW."""
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return area / 2.0


def _pts_to_polyline(
    f: ifcopenshell.file,
    pts_2d: list,
    ensure_ccw: bool,
    reverse_for_hole: bool = False,
) -> "ifcopenshell.entity_instance":
    """Build a closed IfcPolyline from a list of (x,y) tuples.

    Args:
        f:               IFC file.
        pts_2d:          List of (x, y) tuples (not yet closed).
        ensure_ccw:      If True and the outer winding is CW, reverse to CCW.
        reverse_for_hole: If True, reverse winding (IFC inner curves must be CW).
    """
    # Round to 0.001mm precision to avoid floating-point artifacts
    _ROUND = 1000.0
    pts = [(round(p[0] * _ROUND) / _ROUND, round(p[1] * _ROUND) / _ROUND) for p in pts_2d]
    _EPS = 1e-9
    if not (abs(pts[0][0] - pts[-1][0]) < _EPS and abs(pts[0][1] - pts[-1][1]) < _EPS):
        pts.append(pts[0])
    area = _signed_area_2d(pts)
    if ensure_ccw and not reverse_for_hole and area < 0:
        pts = list(reversed(pts[:-1]))
        pts.append(pts[0])
    elif reverse_for_hole and area > 0:
        # Inner curves must be CW (negative area)
        pts = list(reversed(pts[:-1]))
        pts.append(pts[0])
    ifc_pts = [pt2(f, x, y) for x, y in pts]
    return f.create_entity("IfcPolyline", Points=ifc_pts)


def profile_from_points(
    f: ifcopenshell.file,
    points_2d_or_path: Any,
    profile_name: str | None = None,
    ensure_ccw: bool = True,
) -> ifcopenshell.entity_instance:
    """
    Create an IFC profile from a list of (x, y) tuples or a Path.

    - ``IfcArbitraryClosedProfileDef`` when the input has no holes.
    - ``IfcArbitraryProfileDefWithVoids`` when the input is a ``Path``
      that carries one or more holes (set via ``Path.with_hole()``).

    Accepts:
      - A list of (x, y) tuples.
      - A Path instance (calls to_profile_points(); holes are also converted).
      - Any object with to_profile_points() method.
    The list is automatically closed (first == last) if not already.
    If ensure_ccw=True, outer curve is forced CCW; inner curves are forced CW.
    """
    from ifckit.geometry import Path

    holes: list = []
    if isinstance(points_2d_or_path, Path):
        holes = points_2d_or_path.holes  # list of Path
        points_2d_or_path = points_2d_or_path.to_profile_points()
    elif hasattr(points_2d_or_path, "to_profile_points"):
        points_2d_or_path = points_2d_or_path.to_profile_points()

    outer_polyline = _pts_to_polyline(f, list(points_2d_or_path), ensure_ccw=ensure_ccw)

    if not holes:
        return f.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            ProfileName=profile_name,
            OuterCurve=outer_polyline,
        )

    # Build inner curve polylines (CW winding for IFC voids)
    inner_polylines = []
    for hole in holes:
        if isinstance(hole, Path):
            hole_pts = hole.to_profile_points()
        elif hasattr(hole, "to_profile_points"):
            hole_pts = hole.to_profile_points()
        else:
            hole_pts = list(hole)
        inner_polylines.append(
            _pts_to_polyline(f, hole_pts, ensure_ccw=False, reverse_for_hole=True)
        )

    return f.create_entity(
        "IfcArbitraryProfileDefWithVoids",
        ProfileType="AREA",
        ProfileName=profile_name,
        OuterCurve=outer_polyline,
        InnerCurves=inner_polylines,
    )


def profile_to_ifc(
    f: ifcopenshell.file,
    profile_source: Any,
    profile_name: str | None = None,
    ensure_ccw: bool = True,
) -> ifcopenshell.entity_instance:
    """
    Convert a profile source to an IfcProfileDef entity.

    Accepts:
      - A ``Profile`` subclass instance (calls ``profile.to_ifc(f)``).
      - Any object with ``get_profile_points()`` (legacy duck-typing).
      - A sequence of (x, y) tuples (calls ``profile_from_points()``).

    This is the unified entry-point for all builders.
    """
    # Profile ABC or duck-typed object with to_ifc()
    if hasattr(profile_source, "to_ifc"):
        return profile_source.to_ifc(f)
    # Legacy duck-typed objects without to_ifc but with get_profile_points()
    if hasattr(profile_source, "get_profile_points"):
        pts = profile_source.get_profile_points()
        return profile_from_points(f, pts, profile_name=profile_name, ensure_ccw=ensure_ccw)
    # Plain sequence of (x, y) tuples
    return profile_from_points(f, profile_source, profile_name=profile_name, ensure_ccw=ensure_ccw)


def extrude_profile(
    f: ifcopenshell.file,
    profile: ifcopenshell.entity_instance,
    depth: float,
    position: ifcopenshell.entity_instance | None = None,
    extrude_direction: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> ifcopenshell.entity_instance:
    """Create IfcExtrudedAreaSolid."""
    if position is None:
        from ifckit.geometry import Vec

        _o = Vec(0, 0, 0)
        _z = Vec(0, 0, 1)
        _x = Vec(1, 0, 0)
        position = axis2placement3d(f, _o, _z, _x)
    ed = dir3(f, *extrude_direction)
    return f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=position,
        ExtrudedDirection=ed,
        Depth=float(depth),
    )


def mapped_item(
    f: ifcopenshell.file,
    representation_map: ifcopenshell.entity_instance,
    mapping_target: ifcopenshell.entity_instance | None = None,
) -> ifcopenshell.entity_instance:
    """Create IfcMappedItem referencing a RepresentationMap."""
    if mapping_target is None:
        mapping_target = axis2placement3d(
            f,
            Vec(0, 0, 0),
            Vec(0, 0, 1),
            Vec(1, 0, 0),
        )
    return f.create_entity(
        "IfcMappedItem",
        MappingSource=representation_map,
        MappingTarget=mapping_target,
    )


def representation_map(
    f: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance,
    placement: ifcopenshell.entity_instance | None = None,
    rep_type: str = "SweptSolid",
) -> ifcopenshell.entity_instance:
    """Create IfcRepresentationMap with ShapeRepresentation.

    Use this to create a reusable geometry definition that can be
    referenced via IfcMappedItem. This avoids issues with representation
    rebuilding in viewers (e.g., TAB cycling in Bonsai).
    """
    if placement is None:
        placement = axis2placement3d(
            f,
            Vec(0, 0, 0),
            Vec(0, 0, 1),
            Vec(1, 0, 0),
        )
    shape_rep = f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType=rep_type,
        Items=[solid],
    )
    return f.create_entity(
        "IfcRepresentationMap",
        MappingOrigin=placement,
        MappedRepresentation=shape_rep,
    )


def shape_representation(
    f: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance,
    rep_type: str = "SweptSolid",
) -> ifcopenshell.entity_instance:
    valid_types = (
        "SweptSolid",
        "SectionedSpine",
        "Brep",
        "Tessellation",
        "MappedRepresentation",
        "Clipping",
    )
    if rep_type not in valid_types:
        raise ValueError(f"Invalid rep_type '{rep_type}'. Must be one of: {valid_types}")
    return f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType=rep_type,
        Items=[solid],
    )


def product_definition_shape(
    f: ifcopenshell.file,
    shape_rep: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    return f.create_entity(
        "IfcProductDefinitionShape",
        Representations=[shape_rep],
    )


def project_profile_to_plane(
    points: List["Vec"],
    plane: "Plane",
) -> List[tuple[float, float]]:
    """
    Project a list of 3D Vec points to 2D (u, v) in a plane's local coordinates.
    """
    result = []
    for p in points:
        local = plane.to_local(p)
        result.append((local.x, local.y))
    return result


def project_2d_to_plane(
    points_2d: list[tuple[float, float]],
    target_plane: "Plane",
) -> list["Vec"]:
    """Project 2D profile points onto a target plane.

    Takes a list of 2D (u, v) coordinates (in world XY frame)
    and projects them onto a target plane which may be rotated/tilted.

    This allows you to:
    - Define profiles with clean 90° angles in XY
    - Then project them onto a skewed plane (e.g., sloped sill at 15°)

    The resulting points lie on a plane parallel to the target plane,
    at the target's origin.

    Args:
        points_2d: List of (u, v) coordinates in world XY
        target_plane: Target plane (may be rotated/tilted)

    Returns:
        List of Vec points in 3D, on the target plane
    """
    origin = target_plane.origin
    x_axis = target_plane.x_axis
    y_axis = target_plane.y_axis

    result = []
    for u, v in points_2d:
        # (U, V) in world coords → world position on target plane
        # local (0,0,0) → origin
        # local (U,0,0) → origin + U * x_axis
        # local (0,V,0) → origin + V * y_axis
        point = origin + x_axis * u + y_axis * v
        result.append(point)

    return result


def storey_elevation(container: ifcopenshell.entity_instance) -> float:
    """
    Extract the Z-elevation from a storey's ObjectPlacement.

    Returns 0.0 if the storey has no ObjectPlacement (backward-compat).
    """
    try:
        coords = container.ObjectPlacement.RelativePlacement.Location.Coordinates
        return float(coords[2]) if len(coords) > 2 else 0.0
    except AttributeError:
        return 0.0


def directrix_from_line(
    f: ifcopenshell.file,
    line: "Line",
) -> ifcopenshell.entity_instance:
    """Create an IfcPolyline (2-point) directrix from a Line segment."""
    return f.create_entity(
        "IfcPolyline",
        Points=[
            pt3(f, line.start.x, line.start.y, line.start.z),
            pt3(f, line.end.x, line.end.y, line.end.z),
        ],
    )


def directrix_from_arc(
    f: ifcopenshell.file,
    arc: "Arc",
) -> ifcopenshell.entity_instance:
    """
    Create an IfcTrimmedCurve directrix from an Arc.

    The underlying IfcCircle is placed so that:
      - Axis       = arc.normal   (rotation axis)
      - RefDirection = (arc.start - arc.center).normalized()  (0° reference)

    Trim parameters are in degrees (IFC4 default).
    CCW arc (angle > 0): SenseAgreement=True,  Trim1=0°, Trim2=|angle|°
    CW  arc (angle < 0): SenseAgreement=False, Trim1=0°, Trim2=|angle|°
    """
    radial = (arc.start - arc.center).normalized()
    placement = axis2placement3d(f, arc.center, arc.normal, radial)
    circle = f.create_entity(
        "IfcCircle",
        Position=placement,
        Radius=float(arc.radius),
    )
    angle_deg = abs(math.degrees(arc.angle))
    trim1 = f.create_entity("IfcParameterValue", wrappedValue=0.0)
    trim2 = f.create_entity("IfcParameterValue", wrappedValue=angle_deg)
    sense = arc.angle >= 0
    return f.create_entity(
        "IfcTrimmedCurve",
        BasisCurve=circle,
        Trim1=[trim1],
        Trim2=[trim2],
        SenseAgreement=sense,
        MasterRepresentation="PARAMETER",
    )


def directrix_from_path(
    f: ifcopenshell.file,
    path: "Path",
) -> ifcopenshell.entity_instance:
    """
    Create an IfcCompositeCurve directrix from a mixed Line/Arc Path.

    Each segment becomes one IfcCompositeCurveSegment.
    Interior transitions use CONTSAMEGRADIENT; the last uses DISCONTINUOUS.
    """
    from ifckit.geometry import Arc as _Arc

    segments = path.segments
    ifc_segments = []
    for i, seg in enumerate(segments):
        is_last = i == len(segments) - 1
        transition = "DISCONTINUOUS" if is_last else "CONTSAMEGRADIENT"
        if isinstance(seg, _Arc):
            curve = directrix_from_arc(f, seg)
        else:
            curve = directrix_from_line(f, seg)
        ifc_segments.append(
            f.create_entity(
                "IfcCompositeCurveSegment",
                Transition=transition,
                SameSense=True,
                ParentCurve=curve,
            )
        )
    return f.create_entity(
        "IfcCompositeCurve",
        Segments=ifc_segments,
        SelfIntersect=False,
    )


def _triangulate_polygon(
    pts: list[tuple[float, float]],
) -> list[tuple[int, int, int]]:
    """Triangulate a simple polygon using ear-clipping (port of mapbox/earcut).

    Args:
        pts: List of (x, y) tuples (not closed). CCW outer curve.

    Returns:
        List of (i, j, k) index tuples forming CCW triangles.
    """
    n = len(pts)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]

    def _area(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def _point_in_triangle(a, b, c, p):
        return (
            (c[0] - p[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (c[1] - p[1]) >= 0
            and (a[0] - p[0]) * (b[1] - p[1]) - (b[0] - p[0]) * (a[1] - p[1]) >= 0
            and (b[0] - p[0]) * (c[1] - p[1]) - (c[0] - p[0]) * (b[1] - p[1]) >= 0
        )

    # Build circular doubly-linked list
    class Node:
        __slots__ = ("i", "x", "y", "prev", "next")

        def __init__(self, i, x, y):
            self.i = i
            self.x = x
            self.y = y
            self.prev = None
            self.next = None

    first = None
    prev_node = None
    for i, (x, y) in enumerate(pts):
        node = Node(i, x, y)
        if prev_node is None:
            first = node
        else:
            prev_node.next = node
            node.prev = prev_node
        prev_node = node
    first.prev = prev_node
    prev_node.next = first

    triangles = []
    ear = first
    while ear is not None:
        a, b, c = ear.prev, ear, ear.next
        if a is c:
            break

        # Reflex vertex? (CCW: area < 0 means reflex)
        if _area((a.x, a.y), (b.x, b.y), (c.x, c.y)) < 0:
            ear = ear.next
            if ear is first:
                break
            continue

        # Any reflex vertex inside the ear triangle?
        bad = False
        p = c.next
        while p is not a:
            if not _point_in_triangle((a.x, a.y), (b.x, b.y), (c.x, c.y), (p.x, p.y)):
                p = p.next
                continue
            # Only block if p is reflex (CCW: area < 0)
            if _area((p.prev.x, p.prev.y), (p.x, p.y), (p.next.x, p.next.y)) < 0:
                bad = True
                break
            p = p.next

        if bad:
            ear = ear.next
            if ear is first:
                break
            continue

        # Valid ear — cut it
        triangles.append((a.i, b.i, c.i))
        a.next = c
        c.prev = a
        ear = c
        if ear is first:
            break

    return triangles


def _profile_def_to_pts(
    prof_def: "ifcopenshell.entity_instance",
    segments: int = 8,
) -> list[tuple[float, float]]:
    """Extract 2D outline points from any IfcProfileDef entity.

    Handles Rectangle, Circle, IShape, Derived (with full Scale/Scale2
    support), ArbitraryClosedProfileDef (Polyline and CompositeCurve),
    and IfcArbitraryProfileDefWithVoids (outer curve only).

    Args:
        prof_def: Any IfcProfileDef entity instance.
        segments: Circle/curve discretisation count.

    Returns:
        List of (x, y) tuples forming the CCW outer boundary (open ring,
        last point ≠ first point).

    Raises:
        ValueError: If the profile type is not supported and no fallback
        can be applied without silently corrupting geometry.
    """
    import math as _math

    import numpy as np

    ifc_class = prof_def.is_a()

    if ifc_class == "IfcRectangleProfileDef":
        hw = prof_def.XDim / 2
        hh = prof_def.YDim / 2
        return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]

    if ifc_class == "IfcCircleProfileDef":
        r = prof_def.Radius
        return [
            (r * np.cos(2 * np.pi * i / segments), r * np.sin(2 * np.pi * i / segments))
            for i in range(segments)
        ]

    if ifc_class == "IfcIShapeProfileDef":
        hw = prof_def.OverallWidth / 2
        hh = prof_def.OverallDepth / 2
        htw = prof_def.WebThickness / 2
        tf = prof_def.FlangeThickness
        # 12-vertex CCW outline
        return [
            (-hw, -hh),
            (hw, -hh),
            (hw, -hh + tf),
            (htw, -hh + tf),
            (htw, hh - tf),
            (hw, hh - tf),
            (hw, hh),
            (-hw, hh),
            (-hw, hh - tf),
            (-htw, hh - tf),
            (-htw, -hh + tf),
            (-hw, -hh + tf),
        ]

    if ifc_class == "IfcDerivedProfileDef":
        # Recursively extract parent points
        pts = _profile_def_to_pts(prof_def.ParentProfile, segments=segments)

        op = prof_def.Operator
        if op and op.is_a() in (
            "IfcCartesianTransformationOperator2D",
            "IfcCartesianTransformationOperator2DnonUniform",
        ):
            origin = op.LocalOrigin.Coordinates if op.LocalOrigin else (0.0, 0.0)
            a1 = op.Axis1.DirectionRatios if op.Axis1 else (1.0, 0.0)
            a2 = op.Axis2.DirectionRatios if op.Axis2 else (0.0, 1.0)
            # Uniform scale on both axes by default
            sx = getattr(op, "Scale", None) or 1.0
            # Non-uniform: Scale applies to Axis1, Scale2 applies to Axis2
            sy = getattr(op, "Scale2", None)
            if sy is None:
                sy = sx
            transformed = []
            for u, v in pts:
                x = origin[0] + sx * a1[0] * u + sy * a2[0] * v
                y = origin[1] + sx * a1[1] * u + sy * a2[1] * v
                transformed.append((x, y))
            pts = transformed

        return pts

    if ifc_class in ("IfcArbitraryClosedProfileDef", "IfcArbitraryProfileDefWithVoids"):
        outer = prof_def.OuterCurve
        if outer.is_a() == "IfcPolyline":
            pts = [(pt.Coordinates[0], pt.Coordinates[1]) for pt in outer.Points]
            # Remove closing point if present (last == first)
            if (
                len(pts) > 1
                and abs(pts[0][0] - pts[-1][0]) < 1e-6
                and abs(pts[0][1] - pts[-1][1]) < 1e-6
            ):
                pts = pts[:-1]
            return pts
        if outer.is_a() == "IfcCompositeCurve":
            # Collect points from each segment
            pts = []
            for seg in outer.Segments:
                curve = seg.ParentCurve
                if curve.is_a() == "IfcPolyline":
                    for pt in curve.Points:
                        p = (pt.Coordinates[0], pt.Coordinates[1])
                        # Avoid duplicating join points between segments
                        if (
                            not pts
                            or abs(pts[-1][0] - p[0]) > 1e-6
                            or abs(pts[-1][1] - p[1]) > 1e-6
                        ):
                            pts.append(p)
                elif curve.is_a() == "IfcTrimmedCurve":
                    # Discretise trimmed curves (arcs)
                    basis = curve.BasisCurve
                    if basis.is_a() == "IfcCircle":
                        r = basis.Radius
                        c = basis.Position
                        cx = c.Location.Coordinates[0] if c and c.Location else 0.0
                        cy = c.Location.Coordinates[1] if c and c.Location else 0.0
                        t1 = curve.Trim1[0] if curve.Trim1 else 0.0
                        t2 = curve.Trim2[0] if curve.Trim2 else _math.pi * 2
                        # Trim values may be in degrees (IfcParameterValue)
                        # IFC spec: parameter for IfcCircle is in radians
                        n = max(4, segments)
                        for k in range(n + 1):
                            angle = t1 + (t2 - t1) * k / n
                            p = (cx + r * _math.cos(angle), cy + r * _math.sin(angle))
                            if (
                                not pts
                                or abs(pts[-1][0] - p[0]) > 1e-6
                                or abs(pts[-1][1] - p[1]) > 1e-6
                            ):
                                pts.append(p)
            # Remove closing point
            if (
                len(pts) > 1
                and abs(pts[0][0] - pts[-1][0]) < 1e-6
                and abs(pts[0][1] - pts[-1][1]) < 1e-6
            ):
                pts = pts[:-1]
            if pts:
                return pts
        raise ValueError(
            f"Unsupported outer curve type {outer.is_a()!r} in {ifc_class}. "
            "Only IfcPolyline and IfcCompositeCurve are supported."
        )

    if ifc_class == "IfcLShapeProfileDef":
        d = prof_def.Depth
        w = prof_def.Width
        t = prof_def.Thickness
        pts = [
            (0.0, 0.0),
            (w, 0.0),
            (w, t),
            (t, t),
            (t, d),
            (0.0, d),
        ]
        return pts

    if ifc_class == "IfcTShapeProfileDef":
        d = prof_def.Depth
        fw = prof_def.FlangeWidth
        tw = prof_def.WebThickness
        tf = prof_def.FlangeThickness
        hw = fw / 2
        htw = tw / 2
        pts = [
            (-htw, 0.0),
            (htw, 0.0),
            (htw, d - tf),
            (hw, d - tf),
            (hw, d),
            (-hw, d),
            (-hw, d - tf),
            (-htw, d - tf),
        ]
        return pts

    if ifc_class == "IfcZShapeProfileDef":
        d = prof_def.Depth
        fw = prof_def.FlangeWidth
        tw = prof_def.WebThickness
        tf = prof_def.FlangeThickness
        htw = tw / 2
        hd = d / 2
        pts = [
            (-htw, -hd),
            (fw - htw, -hd),
            (fw - htw, -hd + tf),
            (htw, -hd + tf),
            (htw, hd - tf),
            (htw - fw, hd - tf),
            (htw - fw, hd),
            (-htw, hd),
        ]
        return pts

    if ifc_class == "IfcCShapeProfileDef":
        d = prof_def.Depth
        w = prof_def.Width
        t = prof_def.WallThickness
        g = prof_def.Girth or 0.0
        hd = d / 2
        if g > 0:
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w, -hd + g),
                (w - t, -hd + g),
                (w - t, -hd + t),
                (t, -hd + t),
                (t, hd - t),
                (w - t, hd - t),
                (w - t, hd - g),
                (w, hd - g),
                (w, hd),
                (0.0, hd),
            ]
        else:
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w, -hd + t),
                (t, -hd + t),
                (t, hd - t),
                (w, hd - t),
                (w, hd),
                (0.0, hd),
            ]
        return pts

    if ifc_class == "IfcTrapeziumProfileDef":
        hb = prof_def.BottomXDim / 2
        ht = prof_def.TopXDim / 2
        y = prof_def.YDim
        ox = prof_def.TopXOffset
        pts = [
            (-hb, 0.0),
            (hb, 0.0),
            (ox + ht, y),
            (ox - ht, y),
        ]
        return pts

    if ifc_class == "IfcCompositeProfileDef":
        pts = []
        for child in prof_def.Profiles:
            pts.extend(_profile_def_to_pts(child, segments=segments))
        return pts

    raise ValueError(
        f"Unsupported IfcProfileDef type {ifc_class!r}. "
        "Supported: IfcRectangleProfileDef, IfcCircleProfileDef, IfcIShapeProfileDef, "
        "IfcDerivedProfileDef, IfcArbitraryClosedProfileDef, IfcArbitraryProfileDefWithVoids, "
        "IfcTShapeProfileDef, IfcZShapeProfileDef, IfcCShapeProfileDef, "
        "IfcTrapeziumProfileDef, IfcLShapeProfileDef, IfcCompositeProfileDef."
    )


def _resample_ring(ring: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    """Resample a 2D polygon ring to exactly *n* evenly-spaced vertices.

    Walks the ring perimeter by arc-length and interpolates new vertices.
    Preserves the closed-ring topology (result has exactly *n* points,
    last ≠ first).
    """
    import math as _math

    if len(ring) == n:
        return ring

    # Build cumulative arc-length table (closed ring: wrap last→first)
    cum = [0.0]
    for i in range(len(ring)):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % len(ring)]
        seg_len = _math.hypot(x1 - x0, y1 - y0)
        cum.append(cum[-1] + seg_len)
    total = cum[-1]
    if total < 1e-12:
        return ring[:n] if len(ring) >= n else ring + [ring[-1]] * (n - len(ring))

    # Sample at evenly spaced arc-length positions
    resampled = []
    seg_i = 0
    for k in range(n):
        target = total * k / n
        # Advance segment pointer
        while seg_i < len(ring) - 1 and cum[seg_i + 1] < target - 1e-12:
            seg_i += 1
        t = 0.0
        seg_len = cum[seg_i + 1] - cum[seg_i]
        if seg_len > 1e-12:
            t = (target - cum[seg_i]) / seg_len
        x0, y0 = ring[seg_i % len(ring)]
        x1, y1 = ring[(seg_i + 1) % len(ring)]
        resampled.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))

    return resampled


def _tessellate_sectioned_spine(
    cross_sections: list["ifcopenshell.entity_instance"],
    positions: list["ifcopenshell.entity_instance"],
    segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Tessellate IfcSectionedSpine data to vertices and face indices.

    Converts the mathematical definition of a sectioned spine into a mesh.
    Returns vertices (3D points) and face indices (triangles/quads).

    Adjacent sections with different vertex counts are handled by resampling
    both rings to ``lcm(n_prev, n_curr)`` vertices so every vertex is stitched
    without gaps.

    Args:
        cross_sections: List of IfcProfileDef
        positions: List of IfcAxis2Placement3D
        segments: Number of segments per profile (for circles/curves)

    Returns:
        Tuple of (vertices: list of (x, y, z), faces: list of index tuples)
    """
    import math as _math

    from ifckit.geometry import Vec

    # Build axis frames at each position
    axis_frames = []
    for axis in positions:
        origin = axis.Location.Coordinates
        z_axis = axis.Axis.DirectionRatios if axis.Axis else (0, 0, 1)
        x_axis = axis.RefDirection.DirectionRatios if axis.RefDirection else (1, 0, 0)

        z_vec = Vec(*z_axis).normalized()
        x_vec = Vec(*x_axis).normalized()
        y_vec = z_vec.cross(x_vec).normalized()

        axis_frames.append(
            {
                "origin": Vec(*origin),
                "x": x_vec,
                "y": y_vec,
                "z": z_vec,
            }
        )

    # Extract and normalise profile rings to CCW
    profile_rings: list[list[tuple[float, float]]] = []
    for prof_def in cross_sections:
        pts = _profile_def_to_pts(prof_def, segments=segments)
        # Ensure CCW winding
        area = (
            sum(
                pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                for i in range(len(pts))
            )
            / 2.0
        )
        if area < 0:
            pts = list(reversed(pts))
        profile_rings.append(pts)

    # Build mesh vertices and faces
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    section_vertex_offsets: list[int] = []

    for section_idx in range(len(positions)):
        frame = axis_frames[section_idx]
        profile_pts = profile_rings[section_idx]

        section_vertex_offsets.append(len(vertices))

        # Transform 2D profile to 3D at this position.
        # The plane's Z-axis is the extrusion direction (spine tangent);
        # the profile lies in the plane spanned by X and Y.
        for x2d, y2d in profile_pts:
            pt_3d = frame["origin"] + frame["x"] * x2d + frame["y"] * y2d
            vertices.append((pt_3d.x, pt_3d.y, pt_3d.z))

        # Stitch to previous section
        if section_idx > 0:
            prev_idx = section_idx - 1
            prev_start = section_vertex_offsets[prev_idx]
            curr_start = section_vertex_offsets[section_idx]
            prev_ring = profile_rings[prev_idx]
            curr_ring = profile_pts

            n_prev = len(prev_ring)
            n_curr = len(curr_ring)

            if n_prev == n_curr:
                # Same count — straight quad strip
                n = n_prev
                for i in range(n):
                    i_next = (i + 1) % n
                    faces.append(
                        (
                            prev_start + i,
                            prev_start + i_next,
                            curr_start + i_next,
                            curr_start + i,
                        )
                    )
            else:
                # Different counts — resample both rings to lcm(n_prev, n_curr)
                # and add virtual (interpolated) vertices for the stitching rows.
                n_stitch = (n_prev * n_curr) // _math.gcd(n_prev, n_curr)
                prev_resampled = _resample_ring(prev_ring, n_stitch)
                curr_resampled = _resample_ring(curr_ring, n_stitch)

                # Emit interpolated vertices for prev and curr resampled rings
                prev_frame = axis_frames[prev_idx]
                prev_stitch_start = len(vertices)
                for x2d, y2d in prev_resampled:
                    pt_3d = prev_frame["origin"] + prev_frame["y"] * x2d + prev_frame["z"] * y2d
                    vertices.append((pt_3d.x, pt_3d.y, pt_3d.z))

                curr_stitch_start = len(vertices)
                for x2d, y2d in curr_resampled:
                    pt_3d = frame["origin"] + frame["y"] * x2d + frame["z"] * y2d
                    vertices.append((pt_3d.x, pt_3d.y, pt_3d.z))

                for i in range(n_stitch):
                    i_next = (i + 1) % n_stitch
                    faces.append(
                        (
                            prev_stitch_start + i,
                            prev_stitch_start + i_next,
                            curr_stitch_start + i_next,
                            curr_stitch_start + i,
                        )
                    )

    # End caps: first and last section rings
    if len(section_vertex_offsets) >= 2:
        for is_first in (True, False):
            if is_first:
                start = section_vertex_offsets[0]
                pts = profile_rings[0]
            else:
                last = len(section_vertex_offsets) - 1
                start = section_vertex_offsets[last]
                pts = profile_rings[last]

            n = len(pts)
            if n == 4:
                # Single quad cap
                if is_first:
                    faces.append((start, start + 3, start + 2, start + 1))
                else:
                    faces.append((start, start + 1, start + 2, start + 3))
            else:
                tris = _triangulate_polygon(pts)
                for tri in tris:
                    if is_first:
                        faces.append((start + tri[2], start + tri[1], start + tri[0]))
                    else:
                        faces.append((start + tri[0], start + tri[1], start + tri[2]))

    return vertices, faces


def sectioned_spine(
    f: ifcopenshell.file,
    spine_curve: ifcopenshell.entity_instance,
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    """Tessellate a sectioned spine to IfcTriangulatedFaceSet.

    Creates a solid by sweeping cross-sectional profiles along a spine.
    Since IfcOpenShell/Bonsai does not support native IfcSectionedSpine
    rendering, this tessellates to an explicit triangle mesh.

    The ``spine_curve`` argument is accepted for API symmetry with the IFC
    schema but the tessellation is driven by the ``positions`` axis frames,
    which are authoritative for vertex placement.

    Args:
        spine_curve: IfcCompositeCurve — kept for schema symmetry, not used
            in tessellation.
        cross_sections: List of IfcProfileDef (one per position).
        positions: List of IfcAxis2Placement3D (one per cross-section).

    Returns:
        IfcTriangulatedFaceSet entity.
    """
    if len(cross_sections) != len(positions):
        raise ValueError(
            f"CrossSections ({len(cross_sections)}) must have same length "
            f"as CrossSectionPositions ({len(positions)})"
        )
    if len(cross_sections) < 2:
        raise ValueError("At least 2 cross-sections are required")

    # Tessellate to mesh (spine_curve not used — positions are authoritative)
    vertices, faces = _tessellate_sectioned_spine(cross_sections, positions)

    # CoordList expects [[x1, y1, z1], [x2, y2, z2], ...]
    coord_list = [[_round_coord(v[0]), _round_coord(v[1]), _round_coord(v[2])] for v in vertices]

    # Convert all faces to triangles (split quads)
    tris = []
    for face_indices in faces:
        if len(face_indices) == 4:
            tris.append((face_indices[0], face_indices[1], face_indices[2]))
            tris.append((face_indices[0], face_indices[2], face_indices[3]))
        elif len(face_indices) == 3:
            tris.append(face_indices)

    # Use IfcTriangulatedFaceSet — explicit triangles prevent viewer re-triangulation
    # CoordIndex is a 1-based list of triangle index triples
    return f.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=f.create_entity("IfcCartesianPointList3D", CoordList=coord_list),
        Closed=False,
        CoordIndex=[[idx + 1 for idx in tri] for tri in tris],
    )


def get_body_context(
    ifc_file: ifcopenshell.file,
) -> ifcopenshell.entity_instance:
    """
    Return the 'Body' sub-context if it exists, otherwise the first
    Model context, otherwise raise.
    """
    for ctx in ifc_file.by_type("IfcGeometricRepresentationSubContext"):
        if ctx.ContextIdentifier == "Body":
            return ctx
    for ctx in ifc_file.by_type("IfcGeometricRepresentationContext"):
        if ctx.ContextType == "Model":
            return ctx
    raise RuntimeError(
        "No suitable geometric representation context found. "
        "Call IfcModel() first, which creates a Model context."
    )


def _arbitrary_perp(v: "Vec") -> "Vec":
    """Return an arbitrary unit vector perpendicular to v."""
    from ifckit.geometry import Vec as _Vec

    n = v.normalized()
    candidate = _Vec(1.0, 0.0, 0.0) if abs(n @ _Vec(1, 0, 0)) < 0.9 else _Vec(0.0, 1.0, 0.0)
    return (candidate - n * (n @ candidate)).normalized()


def apply_style(ifc_file: Any, product: Any, style: Any) -> None:
    """Assign a RenderStyle to an IFC product via IfcStyledItem.

    Creates the minimal IFC style graph::

        IfcShapeRepresentation.Items[0]
            ← IfcStyledItem
                → IfcSurfaceStyle
                    → IfcSurfaceStyleRendering
                        → IfcColourRgb
                        .Transparency

    If the product has no body representation or no items, this is a no-op.

    Args:
        ifc_file: An ``ifcopenshell.file`` instance.
        product:  An IFC product entity (IfcWall, IfcSlab, …).
        style:    A :class:`ifckit.elements.style.RenderStyle` instance.
    """
    if style is None:
        return

    rep = getattr(product, "Representation", None)
    if rep is None:
        return

    # Find the body representation
    body_rep = None
    for shape_rep in rep.Representations or []:
        if getattr(shape_rep, "RepresentationIdentifier", None) == "Body":
            body_rep = shape_rep
            break
    if body_rep is None:
        return

    items = list(body_rep.Items or [])
    if not items:
        return

    colour_rgb = ifc_file.create_entity(
        "IfcColourRgb",
        Name=None,
        Red=style.r,
        Green=style.g,
        Blue=style.b,
    )
    rendering = ifc_file.create_entity(
        "IfcSurfaceStyleRendering",
        SurfaceColour=colour_rgb,
        Transparency=style.transparency,
        ReflectanceMethod="FLAT",
    )
    surface_style = ifc_file.create_entity(
        "IfcSurfaceStyle",
        Name=None,
        Side="BOTH",
        Styles=[rendering],
    )

    # IFC2X3: IfcStyledItem.Styles must be SET OF IfcPresentationStyleAssignment.
    # IFC4+:  IfcStyledItem.Styles can contain IfcPresentationStyle directly.
    if ifc_file.schema == "IFC2X3":
        style_entry = ifc_file.create_entity(
            "IfcPresentationStyleAssignment",
            Styles=[surface_style],
        )
    else:
        style_entry = surface_style

    ifc_file.create_entity(
        "IfcStyledItem",
        Item=items[0],
        Styles=[style_entry],
        Name=None,
    )
