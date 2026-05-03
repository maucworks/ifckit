"""
ifckit.builders.space
=====================

SpaceBuilder: PendingSpace → IfcSpace with FootPrint + Body representations.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    local_placement,
    profile_from_points,
    pt2,
    storey_elevation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.elements.base import PendingElement


class SpaceBuilder(BaseBuilder):
    """
    Builds an ``IfcSpace`` from a ``PendingSpace``.

    Creates two shape representations:

    * **FootPrint** — a 2-D ``IfcPolyline`` in the XY plane of the storey,
      used by floor-plan views and area calculations.
    * **Body** — an ``IfcExtrudedAreaSolid`` extruded by ``pending.height``
      along the storey Z axis, used by 3-D views.

    The space is associated with its storey via ``IfcRelAggregates``
    (``aggregate.assign_object``), which is the correct IFC relationship for
    spaces — they *decompose* a storey rather than being *contained* by it.
    """

    entity_type = "basic_space"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not hasattr(pending, "element_type") or pending.element_type != "basic_space":
            raise TypeError(f"SpaceBuilder expects PendingSpace, got {type(pending).__name__}")

        elev = storey_elevation(container)  # noqa: F841

        # ------------------------------------------------------------------
        # 2-D footprint points (world XY → storey-local XY; Z irrelevant)
        # ------------------------------------------------------------------
        pts_2d = [(v.x, v.y) for v in pending.footprint]

        # ------------------------------------------------------------------
        # FootPrint representation
        # ------------------------------------------------------------------
        # Build a closed IfcPolyline at Z=0 (storey floor level).
        fp_pts = [pt2(ifc_file, x, y) for x, y in pts_2d]
        if fp_pts and fp_pts[0] != fp_pts[-1]:
            fp_pts.append(fp_pts[0])  # close
        fp_polyline = ifc_file.create_entity("IfcPolyline", Points=fp_pts)

        # The FootPrint context must use the same parent context but with
        # identifier "FootPrint".  We re-use the Body context's parent and
        # create a temporary representation — most viewers accept Body context
        # for FootPrint too, so we share the context object here.
        fp_rep = ifc_file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="FootPrint",
            RepresentationType="Curve2D",
            Items=[fp_polyline],
        )

        # ------------------------------------------------------------------
        # Body representation — extruded solid
        # ------------------------------------------------------------------
        profile = profile_from_points(ifc_file, pts_2d)

        from ifckit.geometry import Vec

        origin = Vec(0.0, 0.0, 0.0)
        z_axis = Vec(0.0, 0.0, 1.0)
        x_axis = Vec(1.0, 0.0, 0.0)
        placement = axis2placement3d(ifc_file, origin, z_axis, x_axis)
        solid = extrude_profile(ifc_file, profile, pending.height, position=placement)

        body_rep = ifc_file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid],
        )

        # ------------------------------------------------------------------
        # IfcProductDefinitionShape — both representations
        # ------------------------------------------------------------------
        prod_rep = ifc_file.create_entity(
            "IfcProductDefinitionShape",
            Representations=[fp_rep, body_rep],
        )

        # ------------------------------------------------------------------
        # IfcSpace entity
        # ------------------------------------------------------------------
        space = ifcopenshell.api.run(
            "root.create_entity",
            ifc_file,
            ifc_class="IfcSpace",
            name=pending.name,
        )
        if pending.long_name:
            space.LongName = pending.long_name

        # PredefinedType — IFC4+ only; skip for IFC2X3
        schema = ifc_file.schema.upper()
        if schema != "IFC2X3":
            try:
                space.PredefinedType = pending.predefined_type
            except Exception:
                pass  # attribute not available in this schema version

        space.Representation = prod_rep

        # Placement: space sits at storey origin (floor level = 0 in local Z).
        from ifckit.geometry import Plane

        space_plane = Plane(Vec(0.0, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0))
        space.ObjectPlacement = local_placement(
            ifc_file, space_plane, relative_to=container.ObjectPlacement
        )

        # ------------------------------------------------------------------
        # Aggregate space under storey (IfcRelAggregates)
        # ------------------------------------------------------------------
        ifcopenshell.api.run(
            "aggregate.assign_object",
            ifc_file,
            products=[space],
            relating_object=container,
        )

        return space
