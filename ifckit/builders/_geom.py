"""
ifckit.builders._geom
=====================

Core ifcopenshell geometry helpers: points, directions, placements,
extrusions, shape representations, and directrix creation.

For coordinate precision helpers see ``_precision.py``.
For profile manipulation see ``_profile.py``.
For tessellation see ``_tessellate.py``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List

import ifcopenshell

from ifckit.builders._precision import get_precision, set_precision  # noqa: F401
from ifckit.builders._precision import round_coord as _round_coord
from ifckit.builders._profile import (  # noqa: F401
    _apply_axis2placement2d,
    _profile_def_to_pts,
    _profile_def_to_rings,
    _pts_to_polyline,
    _resample_ring,
    _signed_area_2d,
    _stitch_annulus,
    _triangulate_polygon,
    profile_from_points,
    profile_to_ifc,
    pt2,
    shapely_polygon_to_ifc_profile,
)
from ifckit.builders._tessellate import _tessellate_sectioned_spine, sectioned_spine  # noqa: F401

if TYPE_CHECKING:
    from ifckit.geometry import Arc, Line, Path, Plane, Vec

# Coordinate precision: decimal places in IFC output (meters)
# 4 = 0.1mm precision (default for mm-based projects)


def pt3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    """Create a 3D point."""
    return f.create_entity(
        "IfcCartesianPoint",
        Coordinates=[_round_coord(x), _round_coord(y), _round_coord(z)],
    )


def dir3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    """Create a 3D direction vector for IFC."""
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


def plane_from_local_placement(
    placement: ifcopenshell.entity_instance,
) -> "Plane":
    """Reconstruct a Plane from an IfcLocalPlacement / IfcAxis2Placement3D.

    Handles optional Axis (default +Z) and RefDirection (default +X) per IFC spec.
    """
    from ifckit.geometry import Plane, Vec

    rp = placement.RelativePlacement
    origin = Vec(*[float(c) for c in rp.Location.Coordinates])
    if rp.Axis:
        z_axis = Vec(*[float(d) for d in rp.Axis.DirectionRatios])
    else:
        z_axis = Vec(0, 0, 1)
    if rp.RefDirection:
        x_axis = Vec(*[float(d) for d in rp.RefDirection.DirectionRatios])
    else:
        x_axis = Vec(1, 0, 0)
    y_axis = z_axis.cross(x_axis)
    return Plane(origin, x_axis, y_axis)


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
        from ifckit.geometry import Vec

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
        from ifckit.geometry import Vec

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
    """Create an IFC shape representation."""
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
    """Create an IFC product definition shape."""
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


def get_or_create_footprint_context(
    ifc_file: ifcopenshell.file,
) -> ifcopenshell.entity_instance:
    """
    Return an existing 'FootPrint' sub-context or create one.

    Uses ``ContextIdentifier="FootPrint"`` and ``ContextType="Model"``
    matching FreeCAD/Bonsai convention for toggleable plan-view
    footprint curves on building elements.
    """
    for ctx in ifc_file.by_type("IfcGeometricRepresentationSubContext"):
        if ctx.ContextIdentifier == "FootPrint":
            return ctx
    parent = None
    for ctx in ifc_file.by_type("IfcGeometricRepresentationContext"):
        if ctx.ContextType == "Model":
            parent = ctx
            break
    if parent is None:
        raise RuntimeError("No Model context found. Call IfcModel() first.")
    return ifc_file.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="FootPrint",
        ContextType="Model",
        ParentContext=parent,
        TargetView="MODEL_VIEW",
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
