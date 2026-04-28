"""
ifckit.builders.column
======================

ColumnBuilder: PendingColumn → IfcColumn with extruded solid along an axis.
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
from ifckit.geometry import Plane


class ColumnBuilder:
    """
    Builds an IfcColumn from a PendingColumn.

    Profile in local YZ, extruded along local X (axis direction).
    """

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
        elev = storey_elevation(container)
        from ifckit.geometry import Vec
        local_start = Vec(axis.start.x, axis.start.y, axis.start.z - elev)
        frame = Plane.from_tangent(local_start, axis.direction)

        # Profile points are (x, y) in cross-section XY plane:
        # profile-X = horizontal right, profile-Y = vertical up.
        pts_2d = [(p.x, p.y) for p in pending.profile]

        profile = profile_from_points(ifc_file, pts_2d)

        # cross-section horizontal = world-Y projected perpendicular to tangent
        t = axis.direction.normalized()
        world_y = Vec(0.0, 1.0, 0.0)
        if abs(t @ world_y) > 0.999:
            world_y = Vec(1.0, 0.0, 0.0)
        horiz = (world_y - t * (t @ world_y)).normalized()

        placement = axis2placement3d(
            ifc_file,
            frame.origin,
            t,      # Axis = extrusion direction
            horiz,  # RefDirection = profile X = horizontal
        )
        solid = extrude_profile(
            ifc_file, profile, length, position=placement,
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
            ifc_file, frame, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[column],
            relating_structure=container,
        )

        return column
