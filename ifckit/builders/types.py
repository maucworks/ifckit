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

from ifckit.builders.psets import _prop, _write_pset

# ---------------------------------------------------------------------------
# Shared pset writers
# ---------------------------------------------------------------------------


def _write_predefined_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    ifc_class: str,
    attr_map: dict,
    pending,
    extra_attrs: dict | None = None,
) -> None:
    """Create a pre-defined property set (IfcPreDefinedPropertySet subtype) and relate it.

    In IFC4, IfcDoorLiningProperties / IfcWindowLiningProperties etc. are subtypes of
    IfcPreDefinedPropertySet with typed, schema-defined attributes — not IfcPropertySingleValue
    items inside a generic IfcPropertySet.  Using the proper entities allows BIM tools and
    validators to recognise them correctly.

    Falls back to a generic IfcPropertySet for IFC2X3 where the pre-defined types may
    not be available in older library versions.
    """
    length_kwargs: dict = {}
    for ifc_attr, pending_attr in attr_map.items():
        val = getattr(pending, pending_attr, None)
        if val is not None:
            length_kwargs[ifc_attr] = float(val)

    all_kwargs = {**length_kwargs, **(extra_attrs or {})}
    if not all_kwargs:
        return

    try:
        pset = ifc_file.create_entity(
            ifc_class,
            GlobalId=ifcopenshell.guid.new(),
            Name=ifc_class,
            **all_kwargs,
        )
    except Exception:
        # Schema version does not have this pre-defined type; fall back to IfcPropertySet.
        from ifckit.builders.psets import _label_prop, _length_prop  # noqa: PLC0415

        props = [_length_prop(ifc_file, k, v) for k, v in length_kwargs.items()]
        for k, v in (extra_attrs or {}).items():
            props.append(_label_prop(ifc_file, k, str(v)))
        _write_pset(ifc_file, type_entity, ifc_class, props)
        return

    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[type_entity],
        RelatingPropertyDefinition=pset,
    )


def _write_door_lining_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcDoorLiningProperties (pre-defined property set)."""
    _write_predefined_pset(
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
    """Write IfcDoorPanelProperties (pre-defined property set)."""
    extra: dict = {}
    if getattr(pending, "panel_operation", None) is not None:
        extra["PanelOperation"] = pending.panel_operation
    _write_predefined_pset(
        ifc_file,
        type_entity,
        "IfcDoorPanelProperties",
        {"PanelDepth": "panel_depth", "PanelWidth": "panel_width"},
        pending,
        extra_attrs=extra if extra else None,
    )


def _write_window_lining_pset(
    ifc_file: ifcopenshell.file,
    type_entity: ifcopenshell.entity_instance,
    pending,
) -> None:
    """Write IfcWindowLiningProperties (pre-defined property set)."""
    _write_predefined_pset(
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
    """Write IfcWindowPanelProperties (pre-defined property set)."""
    extra: dict = {}
    if getattr(pending, "panel_operation", None) is not None:
        extra["OperationType"] = pending.panel_operation
    _write_predefined_pset(
        ifc_file,
        type_entity,
        "IfcWindowPanelProperties",
        {"PanelDepth": "panel_depth", "PanelWidth": "panel_width", "PanelHeight": "panel_height"},
        pending,
        extra_attrs=extra if extra else None,
    )


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
