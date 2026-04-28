"""
ifckit.builders.extruded
========================

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
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    get_body_context,
    local_placement,
    product_definition_shape,
    profile_from_points,
    shape_representation,
    storey_elevation,
)
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingBeam, PendingColumn
from ifckit.geometry import Plane, Vec


class ExtrudedElementBuilder:
    """
    Builds an extruded IFC structural element from a PendingBeam or PendingColumn.

    Args:
        entity_type: Registry key, e.g. ``"basic_beam"`` or ``"basic_column"``.
        ifc_class:   IFC entity class name, e.g. ``"IfcBeam"`` or ``"IfcColumn"``.
    """

    def __init__(self, entity_type: str, ifc_class: str) -> None:
        self.entity_type = entity_type
        self._ifc_class = ifc_class

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not isinstance(pending, (PendingBeam, PendingColumn)):
            raise TypeError(
                f"ExtrudedElementBuilder expects PendingBeam or PendingColumn, "
                f"got {type(pending).__name__}"
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
        vert  = (world_z - t * (t @ world_z)).normalized()
        horiz = (vert ** t).normalized()

        op_plane = Plane(local_start, horiz, vert)

        # Solid placement = identity (profile coords live in OP local space)
        solid_pos = axis2placement3d(
            ifc_file,
            Vec(0.0, 0.0, 0.0),
            Vec(0.0, 0.0, 1.0),
            Vec(1.0, 0.0, 0.0),
        )

        pts_2d = [(p.x, p.y) for p in pending.profile]
        profile = profile_from_points(ifc_file, pts_2d)
        solid = extrude_profile(
            ifc_file, profile, length, position=solid_pos,
            extrude_direction=(0.0, 0.0, 1.0),
        )

        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        element = ifcopenshell.api.run(
            "root.create_entity", ifc_file,
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
