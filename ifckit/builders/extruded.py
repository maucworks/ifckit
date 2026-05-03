"""
ifckit.builders.extruded
=======================

ExtrudedElementBuilder: builds any IFC element by extruding a profile along
a straight axis (Line).  Used for both IfcBeam and IfcColumn — they are
structurally identical; only the IFC class name differs.

Usage::

    BeamBuilder   = ExtrudedElementBuilder("basic_beam",   "IfcBeam")
    ColumnBuilder = ExtrudedElementBuilder("basic_column", "IfcColumn")

Profile convention
------------------
Profile points are (x, y) in the cross-section plane where:
  x = horizontal (left/right relative to beam direction)
  y = vertical up

The ObjectPlacement encodes the full cross-section frame:
  local X (RefDir) = horiz  →  vert × t   (horiz × vert = t  ✓)
  local Y          = vert   →  world-Z projected perpendicular to t
  local Z (Axis)   = t      →  extrusion direction

The solid's IfcAxis2Placement3D is identity so profile coords are
interpreted directly in ObjectPlacement local space.

Clipping
--------
start_clip and end_clip are optional Planes (world space).  Each defines a
half-space whose complement is removed from the solid using
IfcBooleanClippingResult.  The plane's z_axis points toward the material
to keep.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    _arbitrary_perp,
    axis2placement3d,
    dir3,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    profile_to_ifc,
    pt3,
    shape_representation,
    storey_elevation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingBeam, PendingColumn
from ifckit.geometry import Plane, Vec


class ExtrudedElementBuilder(BaseBuilder):
    """
    Builds an extruded IFC structural element from a PendingBeam or PendingColumn.

    Args:
        entity_type: Registry key, e.g. ``"basic_beam"`` or ``"basic_column"``.
        ifc_class:   IFC entity class name, e.g. ``"IfcBeam"`` or ``"IfcColumn"``.
    """

    def __init__(self, entity_type: str, ifc_class: str) -> None:
        self.entity_type = entity_type
        self._ifc_class = ifc_class

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, 'element_type') or pending.element_type != self.entity_type:
            raise TypeError(
                f"ExtrudedElementBuilder({self.entity_type!r}) expects a matching element, "
                f"got element_type={getattr(pending, 'element_type', None)!r}"
            )

        axis = pending.axis
        length = axis.length

        # Translate start to storey-local Z
        elev = storey_elevation(container)
        local_start = Vec(axis.start.x, axis.start.y, axis.start.z - elev)

        # Cross-section frame (right-handed, Plane.z_axis = t = extrusion dir):
        #   vert  = up guide projected perpendicular to t  (profile Y = up)
        #   horiz = vert × t  →  horiz × vert = t  so Plane.z_axis = t ✓
        t = axis.direction.normalized()
        if pending.up is not None:
            world_z = pending.up.normalized()
        else:
            world_z = Vec(0.0, 0.0, 1.0)
            if abs(t @ world_z) > 0.999:
                world_z = Vec(0.0, 1.0, 0.0)
        vert = (world_z - t * (t @ world_z)).normalized()
        horiz = (vert**t).normalized()

        op_plane = Plane(local_start, horiz, vert)

        # Solid placement = identity (profile coords live in OP local space)
        solid_pos = axis2placement3d(
            ifc_file,
            Vec(0.0, 0.0, 0.0),
            Vec(0.0, 0.0, 1.0),
            Vec(1.0, 0.0, 0.0),
        )

        pts_2d = [(p.x, p.y) for p in pending.profile]
        # Use the original profile source (Profile object) when available so we
        # emit the correct native IFC type (e.g. IfcIShapeProfileDef).
        # Fall back to the already-projected 2D point list for plain Vec lists.
        profile_source = getattr(pending, "_profile_source", None)
        from ifckit.profiles.base import Profile as _Profile
        if isinstance(profile_source, _Profile):
            profile = profile_to_ifc(ifc_file, profile_source)
        else:
            profile = profile_from_points(ifc_file, pts_2d)
        solid = extrude_profile(
            ifc_file,
            profile,
            length,
            position=solid_pos,
            extrude_direction=(0.0, 0.0, 1.0),
        )

        # Apply clips — each clip plane is in world space; transform to OP local.
        geometry = solid
        for clip_plane in _iter_clips(pending):
            geometry = _apply_clip(ifc_file, geometry, clip_plane, op_plane, elev)

        rep_type = "SweptSolid" if geometry is solid else "Clipping"
        shape_rep = shape_representation(ifc_file, context, geometry, rep_type=rep_type)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        element = ifcopenshell.api.run(
            "root.create_entity",
            ifc_file,
            ifc_class=self._ifc_class,
            name=pending.name,
        )
        element.Representation = prod_rep
        element.ObjectPlacement = local_placement(
            ifc_file, op_plane, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[element],
            relating_structure=container,
        )

        return element

    def _apply_clips(
        self,
        ifc_file: ifcopenshell.file,
        entity: ifcopenshell.entity_instance,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        return entity  # Clipping handled in _create_geometry for now


# ---------------------------------------------------------------------------
# Clipping helpers (shared)
# ---------------------------------------------------------------------------


def _iter_clips(pending: PendingBeam | PendingColumn):
    """Yield (start_clip, end_clip) planes that are not None."""
    if pending.start_clip is not None:
        yield pending.start_clip
    if pending.end_clip is not None:
        yield pending.end_clip


def _apply_clip(
    ifc_file: ifcopenshell.file,
    solid: ifcopenshell.entity_instance,
    clip_plane: Plane,
    op_plane: Plane,
    elev: float,
) -> ifcopenshell.entity_instance:
    """
    Subtract the half-space on the negative side of clip_plane from solid.

    clip_plane is in world space.  It is transformed into ObjectPlacement
    local space before creating the IfcHalfSpaceSolid.

    The clip_plane's z_axis points toward the material to KEEP, so the
    half-space to remove has its agreement_flag=False (keeps the side the
    normal points away from).
    """
    # Shift clip plane origin to storey-local space (same as op_plane origin)
    world_origin = Vec(
        clip_plane.origin.x,
        clip_plane.origin.y,
        clip_plane.origin.z - elev,
    )

    # Express clip plane origin and normal in ObjectPlacement local coords
    local_origin = op_plane.to_local(world_origin)
    local_normal = Vec(
        clip_plane.z_axis @ op_plane.x_axis,
        clip_plane.z_axis @ op_plane.y_axis,
        clip_plane.z_axis @ op_plane.z_axis,
    )

    # IfcAxis2Placement3D for the half-space base surface
    # The surface normal = local_normal (= Axis of the placement)
    # We need a RefDirection perpendicular to normal; pick any.
    ref = _arbitrary_perp(local_normal)
    half_space_pos = ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=pt3(ifc_file, local_origin.x, local_origin.y, local_origin.z),
        Axis=dir3(ifc_file, local_normal.x, local_normal.y, local_normal.z),
        RefDirection=dir3(ifc_file, ref.x, ref.y, ref.z),
    )
    base_surface = ifc_file.create_entity(
        "IfcPlane",
        Position=half_space_pos,
    )
    # AgreementFlag=False → remove the side the normal points AWAY from,
    # i.e. keep the side the normal points toward. ✓
    half_space = ifc_file.create_entity(
        "IfcHalfSpaceSolid",
        BaseSurface=base_surface,
        AgreementFlag=False,
    )
    return ifc_file.create_entity(
        "IfcBooleanClippingResult",
        Operator="DIFFERENCE",
        FirstOperand=solid,
        SecondOperand=half_space,
    )
