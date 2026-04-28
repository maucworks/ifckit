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
    storey_elevation,
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

        # Derive placement frame from axis; translate to storey-local Z.
        axis = pending.axis
        length = axis.length
        elev = storey_elevation(container)
        from ifckit.geometry import Vec
        local_start = Vec(axis.start.x, axis.start.y, axis.start.z - elev)
        frame = Plane.from_tangent(local_start, axis.direction)

        # Profile points are (x, y) in the cross-section XY plane,
        # where profile-X = horizontal (world Y direction in the cross-section)
        # and profile-Y = vertical (world Z direction in the cross-section).
        pts_2d = [(p.x, p.y) for p in pending.profile]

        profile = profile_from_points(ifc_file, pts_2d)

        # Build solid placement:
        #   Axis        = beam tangent (= extrusion direction = local Z of solid)
        #   RefDirection = cross-section local X = horizontal right in cross-section
        #
        # For a beam along tangent T, the cross-section horizontal is the
        # component of world-Y perpendicular to T (normalised).
        t = axis.direction.normalized()
        world_y = Vec(0.0, 1.0, 0.0)
        # fallback if beam runs along Y
        if abs(t @ world_y) > 0.999:
            world_y = Vec(1.0, 0.0, 0.0)
        horiz = (world_y - t * (t @ world_y)).normalized()  # profile X = right

        placement = axis2placement3d(
            ifc_file,
            frame.origin,
            t,      # Axis = extrusion direction (local Z of solid)
            horiz,  # RefDirection = profile X = horizontal in cross-section
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
        beam.ObjectPlacement = local_placement(
            ifc_file, frame, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[beam],
            relating_structure=container,
        )

        return beam
