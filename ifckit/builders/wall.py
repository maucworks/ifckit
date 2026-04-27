"""
ifckit.builders.wall
====================

WallBuilder: PendingWall → IfcWall with extruded solid geometry.
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
    project_profile_to_plane,
    shape_representation,
)
from ifckit.elements.building import PendingWall
from ifckit.elements.base import PendingElement
from ifckit.geometry import Plane


class WallBuilder:
    """
    Builds an IfcWall from a PendingWall.

    The footprint points are projected to the wall's local XY plane,
    then extruded along the local Z axis by `height`.
    """

    entity_type = "basic_wall"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        assert isinstance(pending, PendingWall)

        # Project footprint to local 2D
        pts_2d = project_profile_to_plane(pending.footprint, pending.plane)
        profile = profile_from_points(ifc_file, pts_2d)

        # Solid: extrude in local Z
        placement = axis2placement3d(
            ifc_file,
            pending.plane.origin,
            pending.plane.z_axis,
            pending.plane.x_axis,
        )
        solid = extrude_profile(ifc_file, profile, pending.height, position=placement)

        # Representation
        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # Entity
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
        )
        wall.Representation = prod_rep
        wall.ObjectPlacement = local_placement(ifc_file, pending.plane)

        # Contain
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[wall],
            relating_structure=container,
        )

        return wall
