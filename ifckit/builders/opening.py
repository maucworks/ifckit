"""
ifckit.builders.opening
=======================

OpeningBuilder: PendingOpening → IfcOpeningElement + IfcRelVoidsElement.

The opening geometry is a box defined by the insert plane's axes:
  - Width  along plane.x_axis
  - Height along plane.z_axis  (= outward normal of host face, repurposed here
    as the opening's height direction)
  - Depth  along plane.y_axis  (into the host body; default 10, overridable)

The opening entity is placed with ObjectPlacement relative to the host
element (wall/slab), centred on the insert plane origin. It is NOT
assigned to the storey via spatial containment (not required by IFC spec).

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
        pending:    A ``PendingOpening`` instance. Uses ``pending.opening_depth``
                    (in project units, default 10.0).
        host_entity: The IfcWall / IfcSlab / IfcRoof entity to void.
        container:  The IfcBuildingStorey entity for spatial containment.
        context:     The Body sub-context.

    Returns:
        The created ``IfcOpeningElement`` entity instance.
    """
    # opening_depth: if None, convert 10m default to project units; otherwise use as-is.
    if pending.opening_depth is None:
        scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        depth = 10.0 / scale  # 10 metres -> project units
    else:
        depth = pending.opening_depth

    # Opening footprint: rectangle centred on origin in local XY.
    # X = width axis, Y = depth axis (into the host).
    # The extrusion is along local Z (= plane.z_axis = outward normal).
    # We offset the profile so origin is at bottom-centre of the opening,
    # and extrude `depth` in -Y (into the host) starting from
    # -depth/2 behind the face, so the opening penetrates both sides.

    w2 = pending.width / 2.0
    pts_2d = [
        (-w2, -depth / 2.0),
        (w2, -depth / 2.0),
        (w2, depth / 2.0),
        (-w2, depth / 2.0),
    ]

    profile = profile_from_points(ifc_file, pts_2d)

    # Placement: origin is at bottom-centre of opening; extrude upward (local Z)
    # Local Z of the opening solid = plane.z_axis (host face outward normal) — but
    # the extrusion direction is plane.y_axis (into/out of face is X of our local frame;
    # we want height to go in the plane's Z direction so we orient accordingly).
    #
    # Convention: opening solid is oriented so that:
    #   solid local X = plane.x_axis (width)
    #   solid local Y = plane.y_axis (depth into wall)
    #   solid local Z = plane.z_axis (outward normal → opening height direction)
    # Extrude along solid local +Z for `height`.

    placement = axis2placement3d(
        ifc_file,
        Vec(0.0, 0.0, 0.0),
        pending.plane.z_axis,  # solid Z = height direction
        pending.plane.x_axis,  # solid X = width direction
    )
    solid = extrude_profile(
        ifc_file,
        profile,
        pending.height,
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

    # Don't assign spatial container to opening elements.
    # IfcOpeningElement is voided into the host via IfcRelVoidsElement,
    # and doesn't need spatial containment per IFC spec.

    # Void the host element.
    ifc_file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=host_entity,
        RelatedOpeningElement=opening,
    )

    write_psets(ifc_file, opening, pending)
    return opening
