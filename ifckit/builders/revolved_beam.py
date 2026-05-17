"""
ifckit.builders.revolved_beam
============================

RevolvedBeamBuilder: PendingRevolvedBeam → IfcBeam with IfcRevolvedAreaSolid.

Implementation based on Construction Plane (CP) concept:
- Position = CP at arc center with local X = radial, local Y = arc normal
- Profile drawn in CP's local XY, offset by +radius to arc start
- Axis = arc normal at arc center, in world coordinates

Reference: IFC4 IfcRevolvedAreaSolid spec
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    dir3,
    product_definition_shape,
    profile_from_points,
    pt3,
    shape_representation,
    storey_elevation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement


class RevolvedBeamBuilder(BaseBuilder):
    entity_type = "revolved_beam"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not hasattr(pending, "element_type") or pending.element_type != "revolved_beam":
            raise TypeError(
                f"RevolvedBeamBuilder expects PendingRevolvedBeam, got {type(pending).__name__}"
            )

        arc = pending.arc
        elev = storey_elevation(container)  # noqa: F841

        # Determine flip reference normal — plane.z_axis or cp_normal
        has_plane = getattr(pending, "plane", None) is not None
        if has_plane:
            ref_n = pending.plane.z_axis.normalized()
        else:
            cp_normal = pending.cp_normal
            ref_n = cp_normal.normalized() if cp_normal is not None else None

        if ref_n is not None:
            arc_n = arc.normal.normalized()
            needs_flip = arc_n.dot(ref_n) < 0
        else:
            needs_flip = False

        # Profile points — offset by -radius in local X to the arc start
        radius = arc.radius
        axis_dist = -radius
        if needs_flip:
            pts_2d = [(p.x, p.y) for p in pending.profile]
        else:
            pts_2d = [(-p.x, -p.y) for p in pending.profile]
        profile = profile_from_points(ifc_file, pts_2d)

        # rev_pos frame at arc start — local X=radial, Z=-tangent, Y=arc.normal
        cpo = arc.start
        cpx = (arc.start - arc.center).normalized()
        cpn = -arc.tangent_at_start().normalized()
        local_y = (cpn**cpx).normalized()  # = arc.normal

        if has_plane:
            # Revolution axis = plane.z_axis (constant for all arcs)
            pz = pending.plane.z_axis.normalized()
            axis_dir = dir3(
                ifc_file,
                pz @ cpx,
                pz @ local_y,
                pz @ cpn,
            )
        else:
            # Revolution axis = local Y → arc.normal
            axis_dir = dir3(ifc_file, 0.0, 1.0, 0.0)

        rev_pos = ifc_file.create_entity(
            "IfcAxis2Placement3D",
            Location=pt3(ifc_file, *cpo.to_tuple()),
            Axis=dir3(ifc_file, *cpn.to_tuple()),
            RefDirection=dir3(ifc_file, *cpx.to_tuple()),
        )

        rev_axis = ifc_file.create_entity(
            "IfcAxis1Placement",
            Location=pt3(ifc_file, axis_dist, 0, 0),
            Axis=axis_dir,
        )

        # Create revolved solid - negative angle for CW sweep
        solid = ifc_file.create_entity(
            "IfcRevolvedAreaSolid",
            SweptArea=profile,
            Position=rev_pos,
            Axis=rev_axis,
            Angle=arc.angle,
        )

        body_ctx = context
        shape_rep = shape_representation(ifc_file, body_ctx, solid, rep_type="SweptSolid")
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # Beam placement - at origin, solid already correctly positioned
        beam_placement = ifc_file.create_entity(
            "IfcAxis2Placement3D",
            Location=pt3(ifc_file, 0.0, 0.0, 0.0),
            Axis=dir3(ifc_file, 0.0, 0.0, 1.0),
            RefDirection=dir3(ifc_file, 1.0, 0.0, 0.0),
        )
        beam_plac = ifc_file.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=container.ObjectPlacement,
            RelativePlacement=beam_placement,
        )

        beam = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcBeam", name=pending.name
        )
        beam.Representation = prod_rep
        beam.ObjectPlacement = beam_plac

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[beam],
            relating_structure=container,
        )

        write_psets(ifc_file, beam, pending)
        return beam
