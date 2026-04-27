"""
ifckit.builders.revolved_beam
==============================

RevolvedBeamBuilder: PendingRevolvedBeam → IfcBeam with IfcRevolvedAreaSolid.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    get_body_context,
    local_placement,
    product_definition_shape,
    profile_from_points,
    pt3,
    dir3,
    shape_representation,
)
from ifckit.elements.structural import PendingRevolvedBeam
from ifckit.elements.base import PendingElement
from ifckit.geometry import Plane


class RevolvedBeamBuilder:
    """
    Builds an IfcBeam from a PendingRevolvedBeam via IfcRevolvedAreaSolid.

    The arc defines the sweep path.
    The profile is the cross-section, defined in 2D (YZ).

    The IFC revolve works as follows:
      - Position: placement of the profile at the arc start (frame at start)
      - Axis: the revolution axis (passes through the arc center, along arc normal)
      - Angle: the arc sweep angle (radians)
    """

    entity_type = "revolved_beam"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        assert isinstance(pending, PendingRevolvedBeam)

        arc = pending.arc

        # Frame at the start of the arc
        start_tangent = arc.tangent_at_start()
        frame = Plane.from_tangent(arc.start, start_tangent)

        # Profile points are already local 2D offsets in the YZ cross-section.
        pts_2d = [(p.x, p.y) for p in pending.profile]

        profile = profile_from_points(ifc_file, pts_2d)

        # Profile position = frame at arc start
        # The profile plane: Z = tangent (extrusion direction into sweep),
        # but IfcRevolvedAreaSolid places the profile at the start and sweeps.
        # Position: local X = radial direction from center to start
        radial = (arc.start - arc.center).normalized()
        tangent = arc.tangent_at_start()

        rev_pos = ifc_file.create_entity(
            "IfcAxis2Placement3D",
            Location=pt3(ifc_file, *arc.start.to_tuple()),
            Axis=dir3(ifc_file, *tangent.to_tuple()),  # local Z = extrusion direction
            RefDirection=dir3(ifc_file, *radial.to_tuple()),
        )

        # Revolution axis: passes through arc center, along arc normal
        rev_axis = ifc_file.create_entity(
            "IfcAxis1Placement",
            Location=pt3(ifc_file, *arc.center.to_tuple()),
            Axis=dir3(ifc_file, *arc.normal.to_tuple()),
        )

        solid = ifc_file.create_entity(
            "IfcRevolvedAreaSolid",
            SweptArea=profile,
            Position=rev_pos,
            Axis=rev_axis,
            Angle=abs(arc.angle),  # IFC expects positive angle
        )

        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, solid, rep_type="SweptSolid")
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
