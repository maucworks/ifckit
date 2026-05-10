"""
ifckit.builders.wall_graph
==========================

WallGraphBuilder: PendingWallGraph -> IfcWall with 3D boolean-union'd
extruded segments.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    shape_representation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.geometry import Vec
from ifckit.profiles.shapes import RectangleProfile


class WallGraphBuilder(BaseBuilder):
    """Builds an IfcWall from a PendingWallGraph.

    Each edge in the graph is extruded as a RectangleProfile(thickness,
    segment_length) positioned at the segment midpoint and aligned
    with the segment direction.  All extruded solids are boolean-union'd
    into a single IfcBooleanResult tree.
    """

    entity_type = "wall_graph"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not hasattr(pending, "element_type") or pending.element_type != "wall_graph":
            raise TypeError(
                f"WallGraphBuilder expects PendingWallGraph, got {type(pending).__name__}"
            )

        thickness = pending.thickness
        height = pending.height
        plane = pending.plane

        # Extrude each segment as a RectangleProfile
        solids = []
        for vi, vj in pending.edges:
            p0 = pending.vertices[vi]
            p1 = pending.vertices[vj]
            seg_dir = (p1 - p0).normalized()
            seg_len = (p1 - p0).length()
            if seg_len < 1e-6:
                continue
            mid = (p0 + p1) * 0.5

            # X-axis = perpendicular to segment in XY, Y-axis = segment direction
            perp = seg_dir ** Vec(0, 0, 1)  # cross(dir, up) gives perpendicular

            # Profile: thickness × segment_length
            profile = RectangleProfile(thickness, seg_len)
            prof_def = profile.to_ifc(ifc_file)

            pos = axis2placement3d(
                ifc_file,
                origin=mid,
                z_axis=plane.z_axis,
                x_axis=perp,
            )
            solid = extrude_profile(ifc_file, prof_def, height, position=pos)
            solids.append(solid)

        if not solids:
            raise ValueError("WallGraph: no valid segments to build.")

        # Boolean union of all extruded solids
        if len(solids) == 1:
            geometry = solids[0]
            rep_type = "SweptSolid"
        else:
            geometry = solids[0]
            for solid in solids[1:]:
                geometry = ifc_file.create_entity(
                    "IfcBooleanResult",
                    Operator="UNION",
                    FirstOperand=geometry,
                    SecondOperand=solid,
                )
            rep_type = "Brep"

        shape_rep = shape_representation(ifc_file, context, geometry, rep_type=rep_type)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # Entity
        wall = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
        )
        wall.Representation = prod_rep
        wall.ObjectPlacement = local_placement(
            ifc_file, plane, relative_to=container.ObjectPlacement
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
