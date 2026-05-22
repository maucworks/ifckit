"""
ifckit.builders.opening
=======================

OpeningBuilder: PendingOpening → IfcOpeningElement + IfcRelVoidsElement.

Opening geometry convention (IFC spec):
  - Profile drawn in the wall-face plane:
      local X = plane.x_axis  (width direction, horizontal)
      local Y = plane.y_axis  (height direction, UP)
  - Extrusion along local Z = plane.z_axis (outward normal of host face,
    i.e. through the wall body).
  - The solid is centred on the wall face: placement is shifted by
    ``-depth/2`` along ``plane.z_axis`` so the opening penetrates equally
    on both sides of the face.
  - The ``anchor`` on ``PendingOpening`` (default ``"sw"`` = bottom-left)
    controls where the ``plane.origin`` sits relative to the opening
    bounding box.

The opening entity is placed relative to the host element
(wall/slab/roof) via ObjectPlacement.  It is NOT assigned to the storey
via spatial containment (not required by IFC spec).

IfcRelVoidsElement links the host entity to the opening element.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid
import ifcopenshell.util.unit

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    shape_representation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.geometry import Plane, Vec
from ifckit.profiles.anchor import anchor_offset


def build_opening(
    ifc_file: ifcopenshell.file,
    pending,  # PendingOpening
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """
    Create an IfcOpeningElement, link it to *host_entity* via
    IfcRelVoidsElement, and assign spatial containment.

    Args:
        ifc_file:    Open ifcopenshell file.
        pending:     A ``PendingOpening`` instance.  ``pending.opening_depth``
                     is in project units; ``None`` → default 10 m converted.
        host_entity: The IfcWall / IfcSlab / IfcRoof entity to void.
        container:   The IfcBuildingStorey entity for spatial containment.
        context:     The Body sub-context.

    Returns:
        The created ``IfcOpeningElement`` entity instance.
    """
    # ------------------------------------------------------------------
    # Resolve depth in project units
    # ------------------------------------------------------------------
    if pending.opening_depth is None:
        scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        depth = 10.0 / scale  # 10 metres → project units
    else:
        depth = pending.opening_depth

    # ------------------------------------------------------------------
    # Profile rectangle in wall-face plane (width × height).
    # anchor_offset gives (dx, dy) so that plane.origin lands at the
    # requested anchor position (default "sw" = bottom-left).
    # ------------------------------------------------------------------
    w = pending.width
    h = pending.height
    dx, dy = anchor_offset(getattr(pending, "anchor", "sw"), w, h)

    pts_2d = [
        (dx, dy),
        (dx + w, dy),
        (dx + w, dy + h),
        (dx, dy + h),
    ]

    profile = profile_from_points(ifc_file, pts_2d)

    # ------------------------------------------------------------------
    # Solid placement — expressed in the opening's LOCAL frame.
    # The opening's ObjectPlacement already encodes the wall-face
    # orientation (X=width, Y=height, Z=outward normal).  Inside that
    # frame the solid axes are therefore identity: X=(1,0,0), Z=(0,0,1).
    # We only shift the origin by -depth/2 along local Z so the solid
    # straddles the wall face symmetrically.
    # ------------------------------------------------------------------
    placement = axis2placement3d(
        ifc_file,
        Vec(0.0, 0.0, -depth / 2.0),  # centred on face in local coords
        Vec(0.0, 0.0, 1.0),  # local Z (identity)
        Vec(1.0, 0.0, 0.0),  # local X (identity)
    )
    solid = extrude_profile(
        ifc_file,
        profile,
        depth,
        position=placement,
        extrude_direction=(0.0, 0.0, 1.0),
    )

    shape_rep = shape_representation(ifc_file, context, solid, rep_type="SweptSolid")
    prod_rep = product_definition_shape(ifc_file, shape_rep)

    opening = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class="IfcOpeningElement",
        name=pending.name,
    )
    opening.Representation = prod_rep
    opening.ObjectPlacement = local_placement(
        ifc_file, pending.plane, relative_to=host_entity.ObjectPlacement
    )

    # Don't assign spatial container to opening elements —
    # IfcOpeningElement is voided into the host via IfcRelVoidsElement.
    ifc_file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=host_entity,
        RelatedOpeningElement=opening,
    )

    write_psets(ifc_file, opening, pending)
    return opening


def build_opening_from_solids(
    ifc_file: ifcopenshell.file,
    plane: Plane,
    solids: list,
    host_entity: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    name: str = "",
) -> ifcopenshell.entity_instance | None:
    """
    Create an IfcOpeningElement from pre-built IFC solids.

    Used by Model B when ``opening_nodes`` produces one or more solids.
    If *solids* is empty (all opening nodes have ``output: false``), returns
    ``None`` — no opening is created.

    Args:
        ifc_file:    Open ifcopenshell file.
        plane:       Insert plane defining the opening's local coordinate frame.
                     Origin = insert point, X = width direction, Z = outward normal.
        solids:      List of IfcExtrudedAreaSolid (or similar) entities produced
                     by ``evaluate_opening_nodes()``.
        host_entity: IfcWall / IfcSlab / IfcRoof entity to void.
        context:     Body sub-context.
        name:        Optional name for the IfcOpeningElement.

    Returns:
        The created ``IfcOpeningElement``, or ``None`` if *solids* is empty.
    """
    if not solids:
        return None

    if len(solids) == 1:
        shape_rep = shape_representation(ifc_file, context, solids[0], rep_type="SweptSolid")
    else:
        shape_rep = shape_representation(ifc_file, context, solids[0], rep_type="SweptSolid")
        for solid in solids[1:]:
            shape_rep.Items = list(shape_rep.Items) + [solid]

    prod_rep = product_definition_shape(ifc_file, shape_rep)

    opening = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class="IfcOpeningElement",
        name=name,
    )
    opening.Representation = prod_rep
    opening.ObjectPlacement = local_placement(
        ifc_file, plane, relative_to=host_entity.ObjectPlacement
    )

    ifc_file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=host_entity,
        RelatedOpeningElement=opening,
    )
    return opening


class OpeningBuilder(BaseBuilder):
    """Builder for PendingOpening elements.

    Openings require a host wall — use ``model.add_opening(pending, host, container)``.
    """

    entity_type = "basic_opening"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        raise LookupError(
            "PendingOpening requires a host wall. "
            "Use model.add_opening(pending, host=wall_handle, container=storey)."
        )
