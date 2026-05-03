"""
ifckit.builders.door_window
===========================

build_door / build_window: create fill elements inside an opening.

Each function:
  1. Creates IfcDoor / IfcWindow with geometry (flat rectangular solid).
  2. Creates IfcRelFillsElement linking opening → fill.
  3. Assigns spatial containment in the storey.
  4. Optionally assigns IfcRelDefinesByType (occurrence → type entity).

Geometry: the door/window solid inherits the opening's placement plane.
The fill occupies the full opening width/height with a minimal depth
(FILL_DEPTH) so it is geometrically present but non-intrusive.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    product_definition_shape,
    profile_from_points,
    shape_representation,
)
from ifckit.builders.psets import write_psets

# Depth of the fill solid (thin panel occupying the opening).
_FILL_DEPTH = 0.1  # metres


def _build_fill(
    ifc_file: ifcopenshell.file,
    ifc_class: str,  # "IfcDoor" or "IfcWindow"
    name: str,
    overall_width: float,
    overall_height: float,
    pending,  # PendingDoor or PendingWindow
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,  # Optional IfcDoorType / IfcWindowType
) -> ifcopenshell.entity_instance:
    """
    Shared implementation for door and window fill creation.
    """
    # Derive placement from the opening's own placement.
    # The fill shares the opening's local frame exactly — same origin,
    # same axes — so the door/window sits flush inside the void.
    opening_placement = opening_entity.ObjectPlacement

    # Build a thin rectangular profile for the fill solid.
    w2 = overall_width / 2.0
    pts_2d = [
        (-w2, 0.0),
        (w2, 0.0),
        (w2, _FILL_DEPTH),
        (-w2, _FILL_DEPTH),
    ]
    profile = profile_from_points(ifc_file, pts_2d)

    # Extrude upward (solid local Z = opening Z = height direction).
    from ifckit.geometry import Vec

    _o = Vec(0, 0, 0)
    _z = Vec(0, 0, 1)
    _x = Vec(1, 0, 0)
    identity_placement = axis2placement3d(ifc_file, _o, _z, _x)
    solid = extrude_profile(
        ifc_file,
        profile,
        overall_height,
        position=identity_placement,
        extrude_direction=(0.0, 0.0, 1.0),
    )

    shape_rep = shape_representation(ifc_file, context, solid, rep_type="SweptSolid")
    prod_rep = product_definition_shape(ifc_file, shape_rep)

    fill = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class=ifc_class,
        name=name,
    )
    fill.Representation = prod_rep

    # IFC requires OverallWidth / OverallHeight attributes on IfcDoor / IfcWindow.
    fill.OverallWidth = overall_width
    fill.OverallHeight = overall_height

    # Fill placement is relative to the opening placement (which is already
    # storey-relative), so chain: fill → opening placement.
    # We use the identity relative placement so the fill coincides with the opening.
    fill.ObjectPlacement = (
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            ifc_file,
            product=fill,
        )
        if False
        else _relative_to_opening(ifc_file, opening_placement)
    )

    # Spatial containment.
    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc_file,
        products=[fill],
        relating_structure=container,
    )

    # Link fill → opening via IfcRelFillsElement.
    ifc_file.create_entity(
        "IfcRelFillsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingOpeningElement=opening_entity,
        RelatedBuildingElement=fill,
    )

    # Optionally assign type.
    if type_entity is not None:
        _assign_type(ifc_file, fill, type_entity)

    write_psets(ifc_file, fill, pending)
    return fill


def _relative_to_opening(
    ifc_file: ifcopenshell.file,
    opening_placement: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """Create an identity IfcLocalPlacement relative to the opening's placement."""
    from ifckit.geometry import Vec

    _o = Vec(0, 0, 0)
    _z = Vec(0, 0, 1)
    _x = Vec(1, 0, 0)
    ax = axis2placement3d(ifc_file, _o, _z, _x)
    return ifc_file.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=opening_placement,
        RelativePlacement=ax,
    )


def _assign_type(
    ifc_file: ifcopenshell.file,
    occurrence: ifcopenshell.entity_instance,
    type_entity: ifcopenshell.entity_instance,
) -> None:
    """
    Assign a type object to an occurrence via IfcRelDefinesByType.

    If the type object already has a IfcRelDefinesByType relation, the
    occurrence is appended to its RelatedObjects list.  Otherwise a new
    relation is created.
    """
    # Search existing IfcRelDefinesByType for this type.
    for rel in ifc_file.by_type("IfcRelDefinesByType"):
        if rel.RelatingType == type_entity:
            # Append to existing relation.
            existing = list(rel.RelatedObjects)
            existing.append(occurrence)
            rel.RelatedObjects = existing
            return
    # Create new relation.
    ifc_file.create_entity(
        "IfcRelDefinesByType",
        GlobalId=ifcopenshell.guid.new(),
        RelatingType=type_entity,
        RelatedObjects=[occurrence],
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_door(
    ifc_file: ifcopenshell.file,
    pending,  # PendingDoor
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,
) -> ifcopenshell.entity_instance:
    """
    Create an IfcDoor fill element inside *opening_entity*.

    Args:
        ifc_file:       Open ifcopenshell file.
        pending:        A ``PendingDoor`` instance.
        opening_entity: The IfcOpeningElement this door fills.
        container:      The IfcBuildingStorey for containment.
        context:        The Body sub-context.
        type_entity:    Optional IfcDoorType entity to assign.

    Returns:
        The created ``IfcDoor`` entity.
    """
    door = _build_fill(
        ifc_file=ifc_file,
        ifc_class="IfcDoor",
        name=pending.name,
        overall_width=pending.overall_width,
        overall_height=pending.overall_height,
        pending=pending,
        opening_entity=opening_entity,
        container=container,
        context=context,
        type_entity=type_entity,
    )
    # Set PredefinedType / OperationType where the schema supports it.
    _set_door_operation(ifc_file, door, pending.operation_type)
    return door


def build_window(
    ifc_file: ifcopenshell.file,
    pending,  # PendingWindow
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,
) -> ifcopenshell.entity_instance:
    """
    Create an IfcWindow fill element inside *opening_entity*.

    Args:
        ifc_file:       Open ifcopenshell file.
        pending:        A ``PendingWindow`` instance.
        opening_entity: The IfcOpeningElement this window fills.
        container:      The IfcBuildingStorey for containment.
        context:        The Body sub-context.
        type_entity:    Optional IfcWindowType entity to assign.

    Returns:
        The created ``IfcWindow`` entity.
    """
    window = _build_fill(
        ifc_file=ifc_file,
        ifc_class="IfcWindow",
        name=pending.name,
        overall_width=pending.overall_width,
        overall_height=pending.overall_height,
        pending=pending,
        opening_entity=opening_entity,
        container=container,
        context=context,
        type_entity=type_entity,
    )
    _set_window_type_attr(ifc_file, window, pending.window_type)
    return window


# ---------------------------------------------------------------------------
# Schema-conditional attribute setters
# ---------------------------------------------------------------------------


def _set_door_operation(
    ifc_file: ifcopenshell.file,
    door: ifcopenshell.entity_instance,
    operation_type: str,
) -> None:
    """Set OperationType on IfcDoor where the schema supports it."""
    # IFC4: IfcDoor has OperationType attribute.
    # IFC2X3: IfcDoor does not have OperationType; it lives on IfcDoorStyle.
    schema = ifc_file.schema
    if schema in ("IFC4", "IFC4X3"):
        try:
            door.OperationType = operation_type
        except (AttributeError, RuntimeError):
            # Attribute absent in this schema variant — safe to skip.
            pass
    # IFC2X3: skip; operation type is on the type object (IfcDoorStyle), set in type builder.


def _set_window_type_attr(
    ifc_file: ifcopenshell.file,
    window: ifcopenshell.entity_instance,
    window_type: str,
) -> None:
    """Set PredefinedType on IfcWindow where the schema supports it."""
    schema = ifc_file.schema
    if schema in ("IFC4", "IFC4X3"):
        try:
            window.PredefinedType = window_type
        except (AttributeError, RuntimeError):
            # Attribute absent in this schema variant — safe to skip.
            pass
