"""
ifckit.builders.types
=====================

build_door_type / build_window_type: create IFC type objects.

Each function:
  1. Creates IfcDoorType / IfcWindowType (IFC4) or IfcDoorStyle / IfcWindowStyle (IFC2X3).
  2. Attaches IfcDoorLiningProperties + IfcDoorPanelProperties psets for non-None fields.
  3. Returns the entity so it can be stored in the model's type cache.

Type cache (IfcModel._type_cache)
----------------------------------
The cache is a plain dict keyed by ``type_key`` string.  It is owned by
``IfcModel`` and lives for the lifetime of the model.  Builders do not
touch the cache — they only create entities.  The model methods
(add_door_type / add_window_type) handle cache lookup and collision
detection.

Collision rule: same type_key + different parameters → ValueError at
model-add time (not here).
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

from ifckit.builders.psets import _label_prop, _length_prop, _prop, _write_pset

# ---------------------------------------------------------------------------
# Shared pset writers
# ---------------------------------------------------------------------------


def _write_field_map_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pset_name: str,
    field_map: dict,
    pending,
) -> None:
    """Write a property set from a {IFC_name: pending_attr} mapping.

    Only fields with non-None values on *pending* are included.
    All values are written as IfcLengthMeasure via ``_length_prop``.
    """
    props = []
    for ifc_name, attr in field_map.items():
        val = getattr(pending, attr, None)
        if val is not None:
            props.append(_length_prop(ifc_file, ifc_name, val))
    _write_pset(ifc_file, type_entity, pset_name, props)


def _write_door_lining_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcDoorLiningProperties as a plain property set."""
    _write_field_map_pset(
        ifc_file,
        type_entity,
        "IfcDoorLiningProperties",
        {
            "LiningDepth": "lining_depth",
            "LiningThickness": "lining_thickness",
            "ThresholdDepth": "threshold_depth",
            "ThresholdThickness": "threshold_thickness",
            "ThresholdOffset": "threshold_offset",
            "TransomThickness": "transom_thickness",
            "TransomOffset": "transom_offset",
            "LiningOffset": "lining_offset",
            "CasingThickness": "casing_thickness",
            "CasingDepth": "casing_depth",
            "LiningToPanelOffsetX": "lining_to_panel_offset_x",
            "LiningToPanelOffsetY": "lining_to_panel_offset_y",
        },
        pending,
    )


def _write_door_panel_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcDoorPanelProperties as a plain property set."""
    props = []
    if getattr(pending, "panel_depth", None) is not None:
        props.append(_length_prop(ifc_file, "PanelDepth", pending.panel_depth))
    if getattr(pending, "panel_width", None) is not None:
        props.append(_prop(ifc_file, "PanelWidth", float(pending.panel_width)))
    if getattr(pending, "panel_operation", None) is not None:
        props.append(_label_prop(ifc_file, "PanelOperation", pending.panel_operation))
    _write_pset(ifc_file, type_entity, "IfcDoorPanelProperties", props)


def _write_window_lining_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcWindowLiningProperties as a plain property set."""
    _write_field_map_pset(
        ifc_file,
        type_entity,
        "IfcWindowLiningProperties",
        {
            "LiningDepth": "lining_depth",
            "LiningThickness": "lining_thickness",
            "TransomThickness": "transom_thickness",
            "MullionThickness": "mullion_thickness",
            "FirstTransomOffset": "first_transom_offset",
            "SecondTransomOffset": "second_transom_offset",
            "FirstMullionOffset": "first_mullion_offset",
            "SecondMullionOffset": "second_mullion_offset",
            "LiningOffset": "lining_offset",
            "LiningToPanelOffsetX": "lining_to_panel_offset_x",
            "LiningToPanelOffsetY": "lining_to_panel_offset_y",
        },
        pending,
    )


def _write_window_panel_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcWindowPanelProperties as a plain property set."""
    props = []
    if getattr(pending, "panel_depth", None) is not None:
        props.append(_length_prop(ifc_file, "PanelDepth", pending.panel_depth))
    if getattr(pending, "panel_width", None) is not None:
        props.append(_prop(ifc_file, "PanelWidth", float(pending.panel_width)))
    if getattr(pending, "panel_height", None) is not None:
        props.append(_prop(ifc_file, "PanelHeight", float(pending.panel_height)))
    if getattr(pending, "panel_operation", None) is not None:
        props.append(_label_prop(ifc_file, "PanelOperation", pending.panel_operation))
    _write_pset(ifc_file, type_entity, "IfcWindowPanelProperties", props)


def _write_user_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    props_dict = getattr(pending, "properties", {}) or {}
    if props_dict:
        user_props = [_prop(ifc_file, k, v) for k, v in props_dict.items()]
        _write_pset(ifc_file, type_entity, "EPset_IfcKit", user_props)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_door_type(
    ifc_file: ifcopenshell.file,
    pending,  # PendingDoorType
) -> ifcopenshell.entity_instance:
    """
    Create an IfcDoorType (IFC4) or IfcDoorStyle (IFC2X3) entity.

    Does NOT consult the type cache — that is the caller's responsibility.

    Args:
        ifc_file: Open ifcopenshell file.
        pending:  A ``PendingDoorType`` instance.

    Returns:
        The created IFC type entity.
    """
    schema = ifc_file.schema
    if schema == "IFC2X3":
        ifc_class = "IfcDoorStyle"
    else:
        ifc_class = "IfcDoorType"

    type_entity = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class=ifc_class,
        name=pending.name or pending.type_key,
    )

    # Set operation type attribute (schema-conditional).
    _set_door_type_operation(ifc_file, type_entity, pending.operation_type)

    # Lining and panel psets.
    _write_door_lining_pset(ifc_file, type_entity, pending)
    _write_door_panel_pset(ifc_file, type_entity, pending)
    _write_user_pset(ifc_file, type_entity, pending)

    return type_entity


def build_window_type(
    ifc_file: ifcopenshell.file,
    pending,  # PendingWindowType
) -> ifcopenshell.entity_instance:
    """
    Create an IfcWindowType (IFC4) or IfcWindowStyle (IFC2X3) entity.

    Does NOT consult the type cache — that is the caller's responsibility.

    Args:
        ifc_file: Open ifcopenshell file.
        pending:  A ``PendingWindowType`` instance.

    Returns:
        The created IFC type entity.
    """
    schema = ifc_file.schema
    if schema == "IFC2X3":
        ifc_class = "IfcWindowStyle"
    else:
        ifc_class = "IfcWindowType"

    type_entity = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class=ifc_class,
        name=pending.name or pending.type_key,
    )

    _set_window_type_attr(ifc_file, type_entity, pending.window_type)

    _write_window_lining_pset(ifc_file, type_entity, pending)
    _write_window_panel_pset(ifc_file, type_entity, pending)
    _write_user_pset(ifc_file, type_entity, pending)

    return type_entity


# ---------------------------------------------------------------------------
# Schema-conditional attribute setters
# ---------------------------------------------------------------------------


def _set_door_type_operation(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    operation_type: str,
) -> None:
    # Both IFC4 (IfcDoorType) and IFC2X3 (IfcDoorStyle) expose OperationType.
    # IFC4 PredefinedType is IfcDoorTypeEnum (DOOR/GATE/TRAPDOOR), not the
    # operation enum — we leave it at its default NOTDEFINED.
    try:
        type_entity.OperationType = operation_type
    except (AttributeError, RuntimeError):
        # Attribute absent in this schema variant — safe to skip.
        pass


def _set_window_type_attr(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    window_type: str,
) -> None:
    try:
        type_entity.PredefinedType = window_type
    except (AttributeError, RuntimeError):
        # Attribute absent in this schema variant — safe to skip.
        pass
