"""
ifckit.builders.tapered
=======================

TaperedExtrusionBuilder: PendingTaperedExtrusion → IfcExtrudedAreaSolidTapered.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    dir3,
    local_placement,
    product_definition_shape,
    profile_from_points,
    shape_representation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingTaperedExtrusion
from ifckit.geometry import Vec


class TaperedExtrusionBuilder(BaseBuilder):
    """
    Builds an IFC element from a PendingTaperedExtrusion.

    Creates ``IfcExtrudedAreaSolidTapered`` with ``IfcArbitraryClosedProfileDef``
    for both start and end profiles.
    """

    entity_type = "tapered_extrusion"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not isinstance(pending, PendingTaperedExtrusion):
            raise TypeError(
                f"TaperedExtrusionBuilder expects PendingTaperedExtrusion, "
                f"got {type(pending).__name__}"
            )

        plane = pending.plane
        start_2d = pending._resolve_pts(pending._start_src, plane)
        end_2d = pending._resolve_pts(pending._end_src, plane)

        start_profile = profile_from_points(ifc_file, start_2d)
        end_profile = profile_from_points(ifc_file, end_2d)

        # Solid: extrude along element-local Z using identity placement.
        # The plane orientation is encoded solely in ObjectPlacement below
        # to avoid a double rotation for non-XY planes.
        placement = axis2placement3d(ifc_file, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0))
        direction = dir3(ifc_file, 0, 0, 1)

        solid = ifc_file.create_entity(
            "IfcExtrudedAreaSolidTapered",
            SweptArea=start_profile,
            Position=placement,
            ExtrudedDirection=direction,
            Depth=float(pending.height),
            EndSweptArea=end_profile,
        )

        shape_rep = shape_representation(ifc_file, context, solid, rep_type="SweptSolid")
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        element = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcBuildingElementProxy", name=pending.name
        )
        element.Representation = prod_rep
        element.ObjectPlacement = local_placement(
            ifc_file, plane, relative_to=container.ObjectPlacement
        )

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[element],
            relating_structure=container,
        )

        write_psets(ifc_file, element, pending)
        return element
