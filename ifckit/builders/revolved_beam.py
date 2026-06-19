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
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.extruded import _apply_clip, _iter_clips
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.geometry import Plane


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
        # elev = storey_elevation(container)  # noqa: F841

        # 90° pre-rotation: IFC spec for IfcRevolvedAreaSolid orients the
        # profile differently than IfcExtrudedAreaSolid — swap axes to
        # compensate.
        pts_2d = [(-p.y, -p.x) for p in pending.profile]

        if arc.angle < 0:
            arc = arc.reverse()
            pts_2d = [(-x, y) for (x, y) in pts_2d]

        profile = profile_from_points(ifc_file, pts_2d)

        # Position = CP at arc center
        # CP origin = arc center
        # CP local X = radial direction (from center toward start)
        # CP local Y = arc normal (perpendicular to arc plane)
        # Position's local XY = radial-normal plane = CP

        cpo = arc.start
        cpx = (arc.start - arc.center).normalized()
        cpn = -arc.tangent_at_start().normalized()
        rev_pos = ifc_file.create_entity(
            "IfcAxis2Placement3D",
            Location=pt3(ifc_file, *cpo.to_tuple()),
            Axis=dir3(ifc_file, *cpn.to_tuple()),
            RefDirection=dir3(ifc_file, *cpx.to_tuple()),
        )

        # Axis of revolution - at arc center, direction = arc normal
        # IfcAxis1Placement is in the local frame of rev_pos, where local Y = arc normal (cpy).
        # So (0,1,0) in that local frame correctly resolves to arc.normal in world space.
        rev_axis = ifc_file.create_entity(
            "IfcAxis1Placement",
            Location=pt3(ifc_file, -arc.radius, 0, 0),
            Axis=dir3(ifc_file, 0.0, 1.0, 0.0),
        )

        # Create revolved solid - negative angle for CW sweep
        solid = ifc_file.create_entity(
            "IfcRevolvedAreaSolid",
            SweptArea=profile,
            Position=rev_pos,
            Axis=rev_axis,
            Angle=arc.angle,
        )

        # Apply clips — op_plane is identity (beam_placement at origin).
        geometry = solid
        for clip_plane in _iter_clips(pending):
            geometry = _apply_clip(ifc_file, geometry, clip_plane, Plane.world_xy(), 0.0)

        rep_type = "SweptSolid" if geometry is solid else "Clipping"
        body_ctx = context
        shape_rep = shape_representation(ifc_file, body_ctx, geometry, rep_type=rep_type)
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
