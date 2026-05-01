"""
ifckit.builders.wall
====================

WallBuilder: PendingWall → IfcWall with extruded solid geometry.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    apply_style,
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    project_profile_to_plane,
    shape_representation,
    shift_plane_elevation,
    storey_elevation,
)
from ifckit.elements.base import PendingElement
from ifckit.elements.building import PendingWall


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
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, 'element_type') or pending.element_type != 'basic_wall':
            raise TypeError(
                f"WallBuilder expects PendingWall, got {type(pending).__name__}"
            )

        # Project footprint to local 2D
        pts_2d = project_profile_to_plane(pending.footprint, pending.plane)
        profile = profile_from_points(ifc_file, pts_2d)

        # Translate plane origin to storey-local coordinates (subtract elevation Z).
        elev = storey_elevation(container)
        local_plane = shift_plane_elevation(pending.plane, elev)

        # Solid: extrude in local Z
        placement = axis2placement3d(
            ifc_file,
            local_plane.origin,
            local_plane.z_axis,
            local_plane.x_axis,
        )
        solid = extrude_profile(ifc_file, profile, pending.height, position=placement)

        # Representation
        shape_rep = shape_representation(ifc_file, context, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # Entity
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
        )
        wall.Representation = prod_rep
        wall.ObjectPlacement = local_placement(
            ifc_file, local_plane, relative_to=container.ObjectPlacement
        )

        # Contain
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[wall],
            relating_structure=container,
        )

        apply_style(ifc_file, wall, pending.style)
        return wall
