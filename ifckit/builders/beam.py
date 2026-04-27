"""
ifckit.builders.beam
====================

BeamBuilder: PendingBeam → IfcBeam with extruded solid along an axis.
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
from ifckit.elements.structural import PendingBeam
from ifckit.elements.base import PendingElement
from ifckit.geometry import Plane


class BeamBuilder:
    """
    Builds an IfcBeam from a PendingBeam.

    The profile is defined in the local YZ cross-section plane.
    The extrusion runs along the beam's local X axis (= axis direction).
    """

    entity_type = "basic_beam"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not isinstance(pending, PendingBeam):
            raise TypeError(
                f"BeamBuilder expects PendingBeam, got {type(pending).__name__}"
            )

        # Derive placement frame from axis
        axis = pending.axis
        length = axis.length
        frame = Plane.from_tangent(axis.start, axis.direction)

        # Profile points are already local 2D offsets in the local cross-section plane.
        # Treat each Vec as (local u, local v) coordinates — z is ignored.
        pts_2d = [(p.x, p.y) for p in pending.profile]

        profile = profile_from_points(ifc_file, pts_2d)

        # Extrude along local X = axis direction
        placement = axis2placement3d(
            ifc_file,
            frame.origin,
            frame.x_axis,   # extrusion = local X (= tangent)
            frame.y_axis,
        )
        solid = extrude_profile(
            ifc_file, profile, length, position=placement,
            extrude_direction=(0.0, 0.0, 1.0),  # local Z in placement = extrusion direction
        )

        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, solid)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        beam = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcBeam", name=pending.name
        )
        beam.Representation = prod_rep
        beam.ObjectPlacement = local_placement(ifc_file, frame)

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[beam],
            relating_structure=container,
        )

        return beam
