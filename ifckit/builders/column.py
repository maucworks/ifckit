"""
ifckit.builders.column
======================

ColumnBuilder: PendingColumn → IfcColumn with extruded solid along an axis.

Profile convention
------------------
Profile points are (x, y) in the cross-section plane where:
  x = horizontal right
  y = vertical up

The ObjectPlacement of the column encodes the full cross-section frame:
  local X (RefDir) = horiz  (profile X → world)
  local Y          = vert   (profile Y → world)
  local Z (Axis)   = t      (extrusion direction)

The solid's own IfcAxis2Placement3D is kept at identity so that profile
coordinates are interpreted directly in ObjectPlacement local space.
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
from ifckit.elements.structural import PendingColumn
from ifckit.elements.base import PendingElement
from ifckit.geometry import Plane, Vec


class ColumnBuilder:
    """Builds an IfcColumn from a PendingColumn."""

    entity_type = "basic_column"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not isinstance(pending, PendingColumn):
            raise TypeError(
                f"ColumnBuilder expects PendingColumn, got {type(pending).__name__}"
            )

        axis = pending.axis
        length = axis.length

        # Translate start to storey-local Z
        elev = storey_elevation(container)
        local_start = Vec(axis.start.x, axis.start.y, axis.start.z - elev)

        # Cross-section frame:
        #   t     = column tangent (extrusion direction)
        #   horiz = horizontal right  (world-Y projected perpendicular to t)
        #   vert  = vertical up       = t × horiz
        t = axis.direction.normalized()
        world_y = Vec(0.0, 1.0, 0.0)
        if abs(t @ world_y) > 0.999:
            world_y = Vec(1.0, 0.0, 0.0)
        horiz = (world_y - t * (t @ world_y)).normalized()
        vert  = t ** horiz

        # ObjectPlacement encodes the full frame:
        #   RefDir (local X) = horiz
        #   local Y          = vert
        #   Axis   (local Z) = t
        # Profile (x, y) → world: x*horiz + y*vert  ✓
        op_plane = Plane(local_start, horiz, vert)

        # Solid placement = identity (profile coords are in OP local space)
        solid_pos = axis2placement3d(
            ifc_file,
            Vec(0.0, 0.0, 0.0),
            Vec(0.0, 0.0, 1.0),  # local Z
            Vec(1.0, 0.0, 0.0),  # local X
        )

        # Profile and solid
        pts_2d = [(p.x, p.y) for p in pending.profile]
        profile = profile_from_points(ifc_file, pts_2d)
        solid = extrude_profile(
            ifc_file, profile, length, position=solid_pos,
            extrude_direction=(0.0, 0.0, 1.0),
        )

        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        column = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcColumn", name=pending.name
        )
        column.Representation = prod_rep
        column.ObjectPlacement = local_placement(
            ifc_file, op_plane, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[column],
            relating_structure=container,
        )

        return column
