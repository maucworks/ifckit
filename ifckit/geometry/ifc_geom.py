from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ifckit.builders._precision import round_coord as _round_coord

if TYPE_CHECKING:
    from typing import List

    import ifcopenshell

    from ifckit.geometry import Arc, Line, Path, Plane, Vec


def pt3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    """Create an IfcCartesianPoint."""
    return f.create_entity(
        "IfcCartesianPoint",
        Coordinates=[_round_coord(x), _round_coord(y), _round_coord(z)],
    )


def dir3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    """Create an IfcDirection."""
    return f.create_entity(
        "IfcDirection",
        DirectionRatios=[_round_coord(x), _round_coord(y), _round_coord(z)],
    )


def axis2placement3d(
    f: ifcopenshell.file,
    origin: Vec,
    z_axis: Vec,
    x_axis: Vec,
) -> ifcopenshell.entity_instance:
    """Create IfcAxis2Placement3D from ifckit Vec objects."""
    return f.create_entity(
        "IfcAxis2Placement3D",
        Location=pt3(f, origin.x, origin.y, origin.z),
        Axis=dir3(f, z_axis.x, z_axis.y, z_axis.z),
        RefDirection=dir3(f, x_axis.x, x_axis.y, x_axis.z),
    )


def project_profile_to_plane(
    points: List[Vec],
    plane: Plane,
) -> List[tuple[float, float]]:
    """Project 3D Vec points to 2D (u, v) in a plane's local coordinates."""
    result = []
    for p in points:
        local = plane.to_local(p)
        result.append((local.x, local.y))
    return result


def directrix_from_line(
    f: ifcopenshell.file,
    line: Line,
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
    arc: Arc,
) -> ifcopenshell.entity_instance:
    """Create an IfcTrimmedCurve directrix from an Arc."""
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
    path: Path,
) -> ifcopenshell.entity_instance:
    """Create an IfcCompositeCurve directrix from a mixed Line/Arc Path."""
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
