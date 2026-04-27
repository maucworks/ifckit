"""
ifckit.builders._geom
=====================

Low-level ifcopenshell geometry helpers shared across builders.
Creates IfcCartesianPoint, IfcDirection, IfcAxis2Placement3D, etc.
"""

from __future__ import annotations

import math
from typing import List, Sequence, TYPE_CHECKING

import ifcopenshell

if TYPE_CHECKING:
    from ifckit.geometry import Plane, Vec


def pt2(f: ifcopenshell.file, x: float, y: float) -> ifcopenshell.entity_instance:
    return f.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y)])


def pt3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    return f.create_entity("IfcCartesianPoint", Coordinates=[float(x), float(y), float(z)])


def dir3(f: ifcopenshell.file, x: float, y: float, z: float) -> ifcopenshell.entity_instance:
    return f.create_entity("IfcDirection", DirectionRatios=[float(x), float(y), float(z)])


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


def profile_from_points(
    f: ifcopenshell.file,
    points_2d: Sequence[tuple[float, float]],
    profile_name: str | None = None,
) -> ifcopenshell.entity_instance:
    """
    Create IfcArbitraryClosedProfileDef from a list of (x, y) tuples.
    The list is automatically closed (first == last) if not already.
    """
    pts = list(points_2d)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    ifc_pts = [pt2(f, x, y) for x, y in pts]
    polyline = f.create_entity("IfcPolyline", Points=ifc_pts)
    return f.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=profile_name,
        OuterCurve=polyline,
    )


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


def shape_representation(
    f: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance,
    rep_type: str = "SweptSolid",
) -> ifcopenshell.entity_instance:
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
