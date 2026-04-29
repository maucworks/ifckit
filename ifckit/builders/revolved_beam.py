"""
ifckit.builders.revolved_beam
==============================

RevolvedBeamBuilder: PendingRevolvedBeam → IfcBeam with IfcRevolvedAreaSolid.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    apply_style,
    dir3,
    local_placement,
    product_definition_shape,
    profile_from_points,
    pt3,
    shape_representation,
    storey_elevation,
)
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingRevolvedBeam
from ifckit.geometry import Plane


class RevolvedBeamBuilder:
    """
    Builds an IfcBeam from a PendingRevolvedBeam via IfcRevolvedAreaSolid.

    The arc defines the sweep path.
    The profile is the cross-section, defined in 2D (local u,v).

    The IFC revolve works as follows:
      - Position: placement of the profile at the arc start (frame at start)
      - Axis: the revolution axis (passes through the arc center, along arc normal)
      - Angle: the arc sweep angle (radians). Positive = CCW, negative = CW.
        Note: Negative angles (CW arcs) are converted to positive by taking abs();
        the placement frame determines the actual solid orientation.
    """

    entity_type = "revolved_beam"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, 'element_type') or pending.element_type != 'revolved_beam':
            raise TypeError(
                f"RevolvedBeamBuilder expects PendingRevolvedBeam, got {type(pending).__name__}"
            )

        arc = pending.arc
        elev = storey_elevation(container)
        from ifckit.geometry import Vec

        def _local_pt(v):
            return Vec(v.x, v.y, v.z - elev)

        # Frame at the start of the arc (storey-local coords)
        start_tangent = arc.tangent_at_start()
        local_start = _local_pt(arc.start)
        frame = Plane.from_tangent(local_start, start_tangent)

        # Profile points are already local 2D offsets in the YZ cross-section.
        pts_2d = [(p.x, p.y) for p in pending.profile]

        profile = profile_from_points(ifc_file, pts_2d)

        # Profile position = frame at arc start
        # The profile plane: Z = tangent (extrusion direction into sweep),
        # but IfcRevolvedAreaSolid places the profile at the start and sweeps.
        # Position: local X = radial direction from center to start
        radial = (arc.start - arc.center).normalized()

        local_arc_start = _local_pt(arc.start)
        local_arc_center = _local_pt(arc.center)

        rev_pos = ifc_file.create_entity(
            "IfcAxis2Placement3D",
            Location=pt3(ifc_file, *local_arc_start.to_tuple()),
            Axis=dir3(ifc_file, *start_tangent.to_tuple()),  # local Z = extrusion direction
            RefDirection=dir3(ifc_file, *radial.to_tuple()),
        )

        # Revolution axis: passes through arc center, along arc normal
        rev_axis = ifc_file.create_entity(
            "IfcAxis1Placement",
            Location=pt3(ifc_file, *local_arc_center.to_tuple()),
            Axis=dir3(ifc_file, *arc.normal.to_tuple()),
        )

        solid = ifc_file.create_entity(
            "IfcRevolvedAreaSolid",
            SweptArea=profile,
            Position=rev_pos,
            Axis=rev_axis,
            Angle=abs(arc.angle),  # IFC expects positive angle
        )

        body_ctx = context
        shape_rep = shape_representation(ifc_file, body_ctx, solid, rep_type="SweptSolid")
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

        apply_style(ifc_file, beam, pending.style)
        return beam
