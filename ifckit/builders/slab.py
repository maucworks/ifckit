"""
ifckit.builders.slab
====================

SlabBuilder: PendingSlab → IfcSlab with extruded solid geometry.
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
    storey_elevation,
)
from ifckit.elements.base import PendingElement
from ifckit.elements.building import PendingSlab


class SlabBuilder:
    """
    Builds an IfcSlab from a PendingSlab.

    The footprint is projected to the slab's local XY plane,
    then extruded along local Z by `thickness`.
    """

    entity_type = "basic_slab"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, 'element_type') or pending.element_type != 'basic_slab':
            raise TypeError(
                f"SlabBuilder expects PendingSlab, got {type(pending).__name__}"
            )

        pts_2d = project_profile_to_plane(pending.footprint, pending.plane)
        profile = profile_from_points(ifc_file, pts_2d)

        elev = storey_elevation(container)
        from ifckit.geometry import Vec
        local_origin = Vec(
            pending.plane.origin.x,
            pending.plane.origin.y,
            pending.plane.origin.z - elev,
        )
        local_plane = pending.plane.__class__(
            local_origin, pending.plane.x_axis, pending.plane.y_axis
        )

        placement = axis2placement3d(
            ifc_file,
            local_plane.origin,
            local_plane.z_axis,
            local_plane.x_axis,
        )
        solid = extrude_profile(ifc_file, profile, pending.thickness, position=placement)

        shape_rep = shape_representation(ifc_file, context, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        slab = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcSlab", name=pending.name
        )
        slab.Representation = prod_rep
        slab.ObjectPlacement = local_placement(
            ifc_file, local_plane, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[slab],
            relating_structure=container,
        )

        apply_style(ifc_file, slab, pending.style)
        return slab
