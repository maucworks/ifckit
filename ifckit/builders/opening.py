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
  - The ``anchor`` on ``PendingOpening`` (default ``"s"`` = bottom-centre)
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
from ifckit.builders.psets import write_psets
from ifckit.geometry import Vec
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
    # requested anchor position (default "s" = bottom-centre).
    # ------------------------------------------------------------------
    w = pending.width
    h = pending.height
    dx, dy = anchor_offset(getattr(pending, "anchor", "s"), w, h)

    pts_2d = [
        (dx, dy),
        (dx + w, dy),
        (dx + w, dy + h),
        (dx, dy + h),
    ]

    profile = profile_from_points(ifc_file, pts_2d)

    # ------------------------------------------------------------------
    # Solid orientation:
    #   local X = plane.x_axis  (width)
    #   local Y = plane.y_axis  (height / UP)
    #   local Z = plane.z_axis  (outward normal → extrusion through wall)
    # Extrude along local +Z for `depth`.
    # Placement: shift origin by -depth/2 along z_axis so the solid
    # straddles the wall face symmetrically.
    # ------------------------------------------------------------------
    placement = axis2placement3d(
        ifc_file,
        Vec(0.0, 0.0, -depth / 2.0),  # centred on face
        pending.plane.z_axis,  # local Z = extrusion direction
        pending.plane.x_axis,  # local X = width
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
