"""
ifckit.builders.door_window
===========================

build_door / build_window: create fill elements inside an opening.

Each function:
  1. Creates IfcDoor / IfcWindow with geometry (rectangular solid or hollow frame).
  2. Creates IfcRelFillsElement linking opening → fill.
  3. Assigns spatial containment in the storey.
  4. Optionally assigns IfcRelDefinesByType (occurrence → type entity).

Geometry convention (matching the opening builder):
  - Profile drawn in the wall-face plane: local X = width, local Y = height.
  - Extrusion along local Z = lining_depth (or FILL_DEPTH for the fallback).
  - The fill inherits the opening's local frame via an identity relative placement.
  - Anchor shift from the opening is applied to the profile rectangle so that
    the fill sits flush inside the opening void.
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
from ifckit.profiles.anchor import anchor_offset

# Depth of the fallback fill solid (thin panel, in metres).
_FILL_DEPTH = 0.1

# Default window lining fallback values (used when no type entity provided).
_DEFAULT_WINDOW_LINING_DEPTH = 0.070  # 70 mm
_DEFAULT_WINDOW_LINING_THICKNESS = 0.055  # 55 mm
_DEFAULT_WINDOW_PANEL_DEPTH = 0.006  # 6 mm


def _extract_window_lining_properties(
    type_entity,
) -> tuple[float, float, float] | None:
    """
    Extract lining properties from IfcWindowType or IfcWindowStyle.

    The properties are stored in an IfcPropertySet linked via
    IfcRelDefinesByProperties with name ``"IfcWindowLiningProperties"``.

    Returns:
        ``(lining_depth, lining_thickness, panel_depth)`` in project units,
        or ``None`` if not found / dimensions are invalid.
    """
    if type_entity is None:
        return None

    ifc_file = type_entity.file
    for rel in ifc_file.by_type("IfcRelDefinesByProperties"):
        if type_entity in rel.RelatedObjects:
            pset = rel.RelatingPropertyDefinition
            if pset.is_a("IfcPropertySet") and pset.Name == "IfcWindowLiningProperties":
                props = {p.Name: p for p in pset.HasProperties}
                ld = props.get("LiningDepth")
                lt = props.get("LiningThickness")
                if ld and lt:
                    ld = ld.NominalValue.wrappedValue
                    lt = lt.NominalValue.wrappedValue
                    if lt < ld / 2.0:  # sanity check: must leave room for inner void
                        return (ld, lt, _DEFAULT_WINDOW_PANEL_DEPTH)
    return None


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
    opening_anchor: str = "s",  # anchor from the parent PendingOpening
) -> ifcopenshell.entity_instance:
    """
    Shared implementation for door and window fill creation.

    Profile convention:
      - local X = width direction, local Y = height (UP), local Z = extrusion through wall.
      - ``opening_anchor`` shifts the profile rectangle so the origin sits at the
        correct anchor point (matching the opening void geometry).
    """
    from ifckit.geometry import Vec

    # Identity placement: fill shares the opening's local frame exactly.
    identity_placement = axis2placement3d(ifc_file, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0))

    # Anchor shift (same as the opening void profile).
    w = overall_width
    h = overall_height
    dx, dy = anchor_offset(opening_anchor, w, h)

    is_window = ifc_class == "IfcWindow"
    lining_props = None
    if is_window and type_entity is not None:
        lining_props = _extract_window_lining_properties(type_entity)

    if is_window and lining_props:
        lining_depth, lining_thickness, _panel_depth = lining_props
        t = lining_thickness

        # Outer rectangle: full opening width × height, extruded lining_depth.
        outer_pts = [
            (dx, dy),
            (dx + w, dy),
            (dx + w, dy + h),
            (dx, dy + h),
        ]
        outer_profile = profile_from_points(ifc_file, outer_pts)
        outer_solid = extrude_profile(
            ifc_file,
            outer_profile,
            lining_depth,
            position=identity_placement,
            extrude_direction=(0.0, 0.0, 1.0),
        )

        # Inner void: inset by lining_thickness on all four sides.
        inner_pts = [
            (dx + t, dy + t),
            (dx + w - t, dy + t),
            (dx + w - t, dy + h - t),
            (dx + t, dy + h - t),
        ]
        inner_profile = profile_from_points(ifc_file, inner_pts)
        inner_void = extrude_profile(
            ifc_file,
            inner_profile,
            lining_depth,
            position=identity_placement,
            extrude_direction=(0.0, 0.0, 1.0),
        )

        # Boolean difference → hollow frame.
        solid = ifc_file.create_entity(
            "IfcBooleanResult",
            Operator="DIFFERENCE",
            FirstOperand=outer_solid,
            SecondOperand=inner_void,
        )
    else:
        # Fallback: simple thin slab (door, or window without valid lining props).
        fill_depth = _FILL_DEPTH
        pts = [
            (dx, dy),
            (dx + w, dy),
            (dx + w, dy + h),
            (dx, dy + h),
        ]
        profile = profile_from_points(ifc_file, pts)
        solid = extrude_profile(
            ifc_file,
            profile,
            fill_depth,
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
    fill.OverallWidth = overall_width
    fill.OverallHeight = overall_height

    # Placement relative to opening (identity — same local frame).
    fill.ObjectPlacement = _relative_to_opening(ifc_file, opening_entity.ObjectPlacement)

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
    opening_anchor: str = "s",
) -> ifcopenshell.entity_instance:
    """
    Create an IfcDoor fill element inside *opening_entity*.

    Args:
        ifc_file:        Open ifcopenshell file.
        pending:         A ``PendingDoor`` instance.
        opening_entity:  The IfcOpeningElement this door fills.
        container:       The IfcBuildingStorey for containment.
        context:         The Body sub-context.
        type_entity:     Optional IfcDoorType entity to assign.
        opening_anchor:  Anchor of the parent ``PendingOpening`` (default ``"s"``).

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
        opening_anchor=opening_anchor,
    )
    _set_door_operation(ifc_file, door, pending.operation_type)
    return door


def build_window(
    ifc_file: ifcopenshell.file,
    pending,  # PendingWindow
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,
    opening_anchor: str = "s",
) -> ifcopenshell.entity_instance:
    """
    Create an IfcWindow fill element inside *opening_entity*.

    Args:
        ifc_file:        Open ifcopenshell file.
        pending:         A ``PendingWindow`` instance.
        opening_entity:  The IfcOpeningElement this window fills.
        container:       The IfcBuildingStorey for containment.
        context:         The Body sub-context.
        type_entity:     Optional IfcWindowType entity to assign.
        opening_anchor:  Anchor of the parent ``PendingOpening`` (default ``"s"``).

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
        opening_anchor=opening_anchor,
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
