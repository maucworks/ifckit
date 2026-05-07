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


def _tessellate_sectioned_spine(
    spine_curve: ifcopenshell.entity_instance,
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
    segments: int = 8,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Tessellate IfcSectionedSpine data to vertices and face indices.

    Converts the mathematical definition of a sectioned spine into a mesh.
    Returns vertices (3D points) and face indices (triangles/quads).

    Args:
        spine_curve: IfcCompositeCurve (must have resolvable points)
        cross_sections: List of IfcProfileDef
        positions: List of IfcAxis2Placement3D
        segments: Number of segments per profile (for roundness)

    Returns:
        Tuple of (vertices: list of (x, y, z), faces: list of index tuples)
    """
    import numpy as np

    from ifckit.geometry import Vec

    # Build axis frames at each position and extract spine points from origins
    axis_frames = []
    spine_points = []
    for axis in positions:
        origin = axis.Location.Coordinates
        z_axis = axis.Axis.DirectionRatios if axis.Axis else (0, 0, 1)
        x_axis = axis.RefDirection.DirectionRatios if axis.RefDirection else (1, 0, 0)

        # Normalize
        z_vec = Vec(*z_axis).normalized()
        x_vec = Vec(*x_axis).normalized()
        y_vec = z_vec.cross(x_vec).normalized()  # cross product

        origin_vec = Vec(*origin)
        axis_frames.append(
            {
                "origin": origin_vec,
                "x": x_vec,
                "y": y_vec,
                "z": z_vec,
            }
        )
        spine_points.append((origin_vec.x, origin_vec.y, origin_vec.z))

    # Extract profile points
    profile_rings = []
    for prof_def in cross_sections:
        if prof_def.is_a() == "IfcRectangleProfileDef":
            x_dim = prof_def.XDim
            y_dim = prof_def.YDim
            # Create rectangle outline
            pts = [
                (-x_dim / 2, -y_dim / 2),
                (x_dim / 2, -y_dim / 2),
                (x_dim / 2, y_dim / 2),
                (-x_dim / 2, y_dim / 2),
            ]
            profile_rings.append(pts)
        elif prof_def.is_a() == "IfcCircleProfileDef":
            r = prof_def.Radius
            pts = [
                (r * np.cos(2 * np.pi * i / segments), r * np.sin(2 * np.pi * i / segments))
                for i in range(segments)
            ]
            profile_rings.append(pts)
        elif prof_def.is_a() == "IfcIShapeProfileDef":
            w = prof_def.OverallWidth
            h = prof_def.OverallDepth
            tw = prof_def.WebThickness
            tf = prof_def.FlangeThickness
            # I-shape: 12 vertices (H-shape outline)
            hw = w / 2
            hh = h / 2
            htw = tw / 2
            pts = [
                (-hw, -hh),  # bottom-left
                (hw, -hh),  # bottom-right
                (hw, -hh + tf),  # bottom flange top-right
                (htw, -hh + tf),  # web bottom-right
                (htw, hh - tf),  # web top-right
                (hw, hh - tf),  # top flange bottom-right
                (hw, hh),  # top-right
                (-hw, hh),  # top-left
                (-hw, hh - tf),  # top flange bottom-left
                (-htw, hh - tf),  # web top-left
                (-htw, -hh + tf),  # web bottom-left
                (-hw, -hh + tf),  # bottom flange top-left
            ]
            profile_rings.append(pts)
        elif prof_def.is_a() == "IfcDerivedProfileDef":
            # Extract parent profile points and apply transformation
            parent = prof_def.ParentProfile
            # Recursively extract parent profile points
            if parent.is_a() == "IfcRectangleProfileDef":
                x_dim = parent.XDim
                y_dim = parent.YDim
                pts = [
                    (-x_dim / 2, -y_dim / 2),
                    (x_dim / 2, -y_dim / 2),
                    (x_dim / 2, y_dim / 2),
                    (-x_dim / 2, y_dim / 2),
                ]
            elif parent.is_a() == "IfcCircleProfileDef":
                r = parent.Radius
                pts = [
                    (
                        r * np.cos(2 * np.pi * i / segments),
                        r * np.sin(2 * np.pi * i / segments),
                    )
                    for i in range(segments)
                ]
            else:
                pts = [(0, 0), (1, 0), (1, 1), (0, 1)]

            # Apply transformation operator
            op = prof_def.Operator
            if op and op.is_a() == "IfcCartesianTransformationOperator2D":
                # Axis1 and Axis2 define scale/rotation
                # LocalOrigin defines offset
                origin = op.LocalOrigin.Coordinates
                # Default Axis1=(1,0), Axis2=(0,1) if not specified
                a1 = op.Axis1.DirectionRatios if op.Axis1 else (1, 0)
                a2 = op.Axis2.DirectionRatios if op.Axis2 else (0, 1)
                # Scale factor
                scale = getattr(op, "Scale", None) or 1.0
                transformed = []
                for u, v in pts:
                    x = origin[0] + scale * (a1[0] * u + a2[0] * v)
                    y = origin[1] + scale * (a1[1] * u + a2[1] * v)
                    transformed.append((x, y))
                pts = transformed

            profile_rings.append(pts)
        elif prof_def.is_a() in (
            "IfcArbitraryClosedProfileDef",
            "IfcArbitraryProfileDefWithVoids",
        ):
            # Extract outer curve points
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
                profile_rings.append(pts)
            else:
                profile_rings.append([(0, 0), (1, 0), (1, 1), (0, 1)])
        else:
            # Fallback: use arbitrary small profile
            profile_rings.append([(0, 0), (1, 0), (1, 1), (0, 1)])

    # Build mesh vertices and faces
    vertices = []
    faces = []
    section_vertex_offsets = []  # Track starting index of each section

    for section_idx in range(len(positions)):
        frame = axis_frames[section_idx]
        profile_pts = profile_rings[section_idx]

        # Record starting index for this section
        section_vertex_offsets.append(len(vertices))

        # Transform 2D profile to 3D at this position
        # Profile sits in YZ plane (perpendicular to spine direction Z)
        for x2d, y2d in profile_pts:
            y_comp = frame["y"] * x2d
            z_comp = frame["z"] * y2d
            pt_3d = frame["origin"] + y_comp + z_comp
            vertices.append((pt_3d.x, pt_3d.y, pt_3d.z))

        # Connect to previous section
        if section_idx > 0:
            prev_start = section_vertex_offsets[section_idx - 1]
            curr_start = section_vertex_offsets[section_idx]
            prev_ring_size = len(profile_rings[section_idx - 1])
            curr_ring_size = len(profile_pts)

            # Create quad faces linking previous and current section
            for i in range(min(prev_ring_size, curr_ring_size)):
                i_next = (i + 1) % min(prev_ring_size, curr_ring_size)

                v_prev = prev_start + i
                v_prev_next = prev_start + i_next
                v_curr = curr_start + i
                v_curr_next = curr_start + i_next

                # Quad face (ensure correct winding)
                faces.append((v_prev, v_prev_next, v_curr_next, v_curr))

    # Add end caps (first and last section rings)
    if len(section_vertex_offsets) >= 2:
        first_start = section_vertex_offsets[0]
        first_ring_size = len(profile_rings[0])
        last_section = len(section_vertex_offsets) - 1
        last_start = section_vertex_offsets[last_section]
        last_ring_size = len(profile_rings[last_section])

        if first_ring_size == 4:
            # Quad cap — single face
            # Front: reversed winding so normal points backward
            faces.append(
                (
                    first_start,
                    first_start + 3,
                    first_start + 2,
                    first_start + 1,
                )
            )
            # Back: normal winding so normal points forward
            faces.append(
                (
                    last_start,
                    last_start + 1,
                    last_start + 2,
                    last_start + 3,
                )
            )
        else:
            # Fan triangulation for non-rectangular profiles
            for i in range(1, first_ring_size - 1):
                faces.append((first_start, first_start + i + 1, first_start + i))
            for i in range(1, last_ring_size - 1):
                faces.append((last_start, last_start + i, last_start + i + 1))

    return vertices, faces


def sectioned_spine(
    f: ifcopenshell.file,
    spine_curve: ifcopenshell.entity_instance,
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    """Create IfcSectionedSpine or IfcPolygonalFaceSet fallback.

    Creates a solid by sweeping cross-sectional profiles along a spine curve.
    Since IfcOpenShell doesn't support IfcSectionedSpine rendering, this
    tessellates to IfcPolygonalFaceSet for Bonsai compatibility.

    Args:
        spine_curve: IfcCompositeCurve (3D curve/boog)
        cross_sections: LIST of IfcProfileDef (profielen op elke positie)
        positions: LIST of IfcAxis2Placement3D (posities langs curve)

    Returns:
        IfcPolygonalFaceSet entity
    """
    if len(cross_sections) != len(positions):
        raise ValueError(
            f"CrossSections ({len(cross_sections)}) must have same length "
            f"as CrossSectionPositions ({len(positions)})"
        )
    if len(cross_sections) < 2:
        raise ValueError("At least 2 cross-sections are required")

    # Tessellate to mesh
    vertices, faces = _tessellate_sectioned_spine(spine_curve, cross_sections, positions)

    # Convert to IFC IfcPolygonalFaceSet
    # CoordList expects [[x1, y1, z1], [x2, y2, z2], ...]
    coord_list = [[_round_coord(v[0]), _round_coord(v[1]), _round_coord(v[2])] for v in vertices]

    # Build IfcIndexedPolygonalFace entities from face indices
    ifc_faces = []
    for face_indices in faces:
        # IfcIndexedPolygonalFace uses 1-based indexing
        ifc_face = f.create_entity(
            "IfcIndexedPolygonalFace",
            CoordIndex=[idx + 1 for idx in face_indices],
        )
        ifc_faces.append(ifc_face)

    # Create the IfcPolygonalFaceSet
    return f.create_entity(
        "IfcPolygonalFaceSet",
        Coordinates=f.create_entity("IfcCartesianPointList3D", CoordList=coord_list),
        Closed=True,
        Faces=ifc_faces,
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
