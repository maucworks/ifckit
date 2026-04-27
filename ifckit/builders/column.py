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
        assert isinstance(pending, PendingColumn)

        axis = pending.axis
        length = axis.length
        frame = Plane.from_tangent(axis.start, axis.direction)

        pts_2d = []
        for p in pending.profile:
            local = frame.to_local(p + axis.start)
            pts_2d.append((local.y, local.z))

        profile = profile_from_points(ifc_file, pts_2d)

        placement = axis2placement3d(
            ifc_file,
            frame.origin,
            frame.x_axis,
            frame.y_axis,
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
        column.ObjectPlacement = local_placement(ifc_file, frame)

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[column],
            relating_structure=container,
        )

        return column
