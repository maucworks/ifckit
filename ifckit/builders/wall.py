"""
ifckit.builders.wall
===================

WallBuilder: PendingWall → IfcWall with extruded solid geometry.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    project_profile_to_plane,
    shape_representation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.extruded import _apply_clip, _iter_clips
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.geometry import Vec


class WallBuilder(BaseBuilder):
    """
    Builds an IfcWall from a PendingWall.

    The footprint points are projected to the wall's local XY plane,
    then extruded along the local Z axis by `height`.
    Optional clip planes are applied as IfcBooleanClippingResult.
    """

    entity_type = "basic_wall"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, "element_type") or pending.element_type != "basic_wall":
            raise TypeError(f"WallBuilder expects PendingWall, got {type(pending).__name__}")

        # Project footprint to local 2D
        pts_2d = project_profile_to_plane(pending.footprint, pending.plane)
        profile = profile_from_points(ifc_file, pts_2d)

        # Solid: extrude along element-local Z using identity placement.
        # The plane orientation is encoded solely in ObjectPlacement below,
        # matching the WallGraphBuilder pattern to avoid a double rotation.
        placement = axis2placement3d(
            ifc_file,
            Vec(0.0, 0.0, 0.0),
            Vec(0.0, 0.0, 1.0),
            Vec(1.0, 0.0, 0.0),
        )
        solid = extrude_profile(ifc_file, profile, pending.height, position=placement)

        # Apply clip planes
        geometry = solid
        for clip_plane in _iter_clips(pending):
            geometry = _apply_clip(ifc_file, geometry, clip_plane, pending.plane, 0.0)

        rep_type = "SweptSolid" if geometry is solid else "Clipping"
        shape_rep = shape_representation(ifc_file, context, geometry, rep_type=rep_type)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # Entity
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
        )
        wall.Representation = prod_rep
        wall.ObjectPlacement = local_placement(
            ifc_file, pending.plane, relative_to=container.ObjectPlacement
        )

        # Contain
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[wall],
            relating_structure=container,
        )

        write_psets(ifc_file, wall, pending)
        return wall
