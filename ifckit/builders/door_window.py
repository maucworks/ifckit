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

from typing import Optional

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid
import ifcopenshell.util.unit

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    product_definition_shape,
    profile_from_points,
    shape_representation,
)
from ifckit.builders._material import apply_material_to_solid
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


def _build_fill_from_graph(
    ifc_file: ifcopenshell.file,
    ifc_class: str,
    name: str,
    overall_width: float,
    overall_height: float,
    graph_name: str,
    pending,
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,
    opening_anchor: str = "sw",
) -> ifcopenshell.entity_instance:
    """Create a fill element whose geometry comes from a component-graph preset."""
    from ifckit.builders.component_graph import evaluate_component_graph

    params: dict = {"w": overall_width, "h": overall_height}
    if pending.parameters:
        params.update(pending.parameters)

    path = getattr(pending, "path", None)
    components = evaluate_component_graph(
        graph_name, ifc_file, context, params, pending.plane, path=path
    )
    return _build_fill_from_components(
        ifc_file=ifc_file,
        ifc_class=ifc_class,
        name=name,
        overall_width=overall_width,
        overall_height=overall_height,
        components=components,
        pending=pending,
        opening_entity=opening_entity,
        container=container,
        context=context,
        type_entity=type_entity,
        opening_anchor=opening_anchor,
    )


def _split_by_role(components):
    """Split EvaluatedComponents by role into opening/projection/fill lists.

    Returns:
        Tuple of ``(opening_solids, projection_solids, fill_components)``.
    """
    opening_solids = []
    projection_solids = []
    fill_components = []
    for comp in components:
        solid = comp.solid

        if comp.role == "Opening":
            opening_solids.append(solid)
        elif comp.role == "Projection":
            projection_solids.append(solid)
        else:
            fill_components.append(comp)
    return opening_solids, projection_solids, fill_components


def _build_fill_from_components(
    ifc_file: ifcopenshell.file,
    ifc_class: str,
    name: str,
    overall_width: float,
    overall_height: float,
    components,
    pending,
    opening_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    type_entity=None,
    opening_anchor: str = "sw",
) -> ifcopenshell.entity_instance:
    """Create a fill element from pre-built EvaluatedComponent list.

    Components already have geometry and placements; apply materials.
    """
    solids = []

    # Apply materials to components (already positioned)
    for comp in components:
        solid = comp.solid

        # Apply material if defined or overridden
        material = comp.material
        if pending.material_overrides and comp.role in pending.material_overrides:
            material_override = pending.material_overrides[comp.role]
            if material and material_override:
                merged_material = material.copy()
                merged_material.update(material_override)
                material = merged_material
            elif material_override:
                material = material_override

        if not material:
            material = {
                "color": {"r": 0.75, "g": 0.75, "b": 0.75},
                "transparency": 0.0,
                "name": "Default",
            }
        solid = apply_material_to_solid(ifc_file, solid, material)
        solids.append(solid)

    if not solids:
        raise ValueError("_build_fill_from_components: no fill components")

    # Build shape representation
    has_boolean = any(s.is_a("IfcBooleanResult") for s in solids)
    has_swept = any(s.is_a("IfcExtrudedAreaSolid") for s in solids)
    if has_boolean and has_swept:
        rep_type = "SolidModel"
    elif has_boolean:
        rep_type = "CSG"
    else:
        rep_type = "SweptSolid"

    shape_rep = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType=rep_type,
        Items=solids,
    )

    product_def_shape = ifc_file.create_entity(
        "IfcProductDefinitionShape",
        Representations=[shape_rep],
    )

    fill = ifc_file.create_entity(
        ifc_class,
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        Description=None,
        ObjectType="fill",
        ObjectPlacement=_relative_to_opening(ifc_file, opening_entity.ObjectPlacement),
        Representation=product_def_shape,
    )

    fill.OverallWidth = overall_width
    fill.OverallHeight = overall_height

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
    opening_anchor: str = "sw",  # anchor from the parent PendingOpening
    graph_name: "str | None" = None,
) -> ifcopenshell.entity_instance:
    """
    Shared implementation for door and window fill creation.

    If *graph_name* is provided, geometry is produced by the component-graph
    evaluator (``_build_fill_from_graph``) instead of the built-in lining logic.

    Profile convention:
      - local X = width direction, local Y = height (UP), local Z = extrusion through wall.
      - ``opening_anchor`` shifts the profile rectangle so the origin sits at the
        correct anchor point (matching the opening void geometry).
    """
    # Graph path: delegate entirely to _build_fill_from_graph.
    if graph_name is not None:
        return _build_fill_from_graph(
            ifc_file=ifc_file,
            ifc_class=ifc_class,
            name=name,
            overall_width=overall_width,
            overall_height=overall_height,
            graph_name=graph_name,
            pending=pending,
            opening_entity=opening_entity,
            container=container,
            context=context,
            type_entity=type_entity,
            opening_anchor=opening_anchor,
        )

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
    opening_anchor: str = "sw",
    graph_name: "Optional[str]" = None,
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
        graph_name:      Optional component graph preset name (overrides pending.component_graph).

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
        graph_name=graph_name or getattr(pending, "component_graph", None),
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
    opening_anchor: str = "sw",
    graph_name: "Optional[str]" = None,
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
        graph_name:      Optional component graph preset name (overrides pending.component_graph).

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
        graph_name=graph_name or getattr(pending, "component_graph", None),
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


# ---------------------------------------------------------------------------
# Model B helpers
# ---------------------------------------------------------------------------


def _thickness_from_extruded(extruded) -> float | None:
    """Extract thickness from an IfcExtrudedAreaSolid, or None if not possible."""
    area = extruded.SweptArea
    if area.is_a("IfcRectangleProfileDef"):
        return float(area.YDim) * 1000.0
    if area.is_a("IfcArbitraryClosedProfileDef"):
        return _get_profile_thickness(area)
    return None


def _extract_wall_thickness(host_entity: ifcopenshell.entity_instance) -> float:
    try:
        rep = host_entity.Representation
        if rep is None:
            return 200.0
        for shape_rep in rep.Representations:
            for item in shape_rep.Items:
                if item.is_a("IfcExtrudedAreaSolid"):
                    thickness = _thickness_from_extruded(item)
                    if thickness is not None:
                        return thickness
                elif item.is_a("IfcBooleanClippingResult"):
                    first_op = item.FirstOperand
                    if first_op.is_a("IfcExtrudedAreaSolid"):
                        thickness = _thickness_from_extruded(first_op)
                        if thickness is not None:
                            return thickness
    except Exception:  # noqa: BLE001
        pass
    return 200.0


def _get_profile_thickness(area) -> float:
    """Extract thickness from profile by calculating bounding box Y extent."""
    try:
        curve = area.OuterCurve
        if hasattr(curve, "Points"):
            coords_raw = [(p.Coordinates[0], p.Coordinates[1]) for p in curve.Points]
        else:
            coords_raw = []
            for seg in curve:
                if hasattr(seg, "Points"):
                    coords_raw.extend([(p.Coordinates[0], p.Coordinates[1]) for p in seg.Points])
        if not coords_raw:
            return 200.0
        test_y = max(p[1] for p in coords_raw)
        if test_y > 100:
            thickness = max(p[1] for p in coords_raw) - min(p[1] for p in coords_raw)
        else:
            thickness = (max(p[1] for p in coords_raw) - min(p[1] for p in coords_raw)) * 1000.0
        if thickness > 0:
            return thickness
    except Exception:  # noqa: BLE001
        pass
    return 200.0


def _build_model_b(
    ifc_file: ifcopenshell.file,
    ifc_class: str,
    pending,
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
    params_extras: dict,
    post_process,
) -> ifcopenshell.entity_instance:
    """Shared Model B: create IfcOpeningElement + fill (door/window) in one call.

    Args:
        ifc_file:      Open ifcopenshell file.
        ifc_class:     ``"IfcWindow"`` or ``"IfcDoor"``.
        pending:       PendingWindow or PendingDoor with ``plane``, ``component_graph``.
        host_entity:   IfcWall / IfcSlab to void.
        container:     IfcBuildingStorey for containment.
        context:       Body sub-context.
        params_extras: Extra params dict merged into ``{"w", "h", "wall_thickness"}``.
        post_process:  Callable ``(ifc_file, fill_entity, pending)`` called before
                       returning (e.g. to set window type or door operation).

    Returns:
        The created IfcDoor or IfcWindow entity.
    """
    from ifckit.builders._geom import plane_from_local_placement
    from ifckit.builders.component_graph import evaluate_opening_nodes
    from ifckit.builders.opening import build_opening_from_solids

    if not pending.component_graph:
        raise ValueError("_build_model_b: pending.component_graph must be set.")

    if not pending.plane:
        raise ValueError("_build_model_b: pending.plane must be set.")

    # Transform plane from storey coords to wall-local coords
    wall_plane = plane_from_local_placement(host_entity.ObjectPlacement)
    local_plane = pending.plane.in_frame(wall_plane)

    wall_thickness = _extract_wall_thickness(host_entity)
    params = {
        "w": pending.overall_width,
        "h": pending.overall_height,
        "wall_thickness": wall_thickness,
    }
    params.update(params_extras)
    if pending.parameters:
        params.update(pending.parameters)

    path = getattr(pending, "path", None)
    opening_components = evaluate_opening_nodes(
        pending.component_graph, ifc_file, context, params, local_plane, path=path
    )

    opening_solids, projection_solids, fill_components = _split_by_role(opening_components)

    opening_entity = build_opening_from_solids(
        ifc_file,
        local_plane,
        opening_solids,
        host_entity,
        context,
        name=f"Opening-{pending.name}" if pending.name else "",
    )

    if opening_entity is None:
        raise ValueError(
            f"_build_model_b: preset {pending.component_graph!r} "
            "produced no opening solid. Cannot create IfcOpeningElement."
        )

    # Boolean-union Projection solids into the host wall's body representation
    body_reps = [
        r
        for r in host_entity.Representation.Representations
        if r.RepresentationIdentifier == "Body"
    ]
    if body_reps:
        body_rep = body_reps[0]
        items = list(body_rep.Items)
        if items:
            current = items[0]
            for item in items[1:]:
                current = ifc_file.create_entity(
                    "IfcBooleanResult",
                    Operator="UNION",
                    FirstOperand=current,
                    SecondOperand=item,
                )
            for proj_solid in projection_solids:
                current = ifc_file.create_entity(
                    "IfcBooleanResult",
                    Operator="UNION",
                    FirstOperand=current,
                    SecondOperand=proj_solid,
                )
            body_rep.Items = [current]

    if fill_components:
        fill = _build_fill_from_components(
            ifc_file=ifc_file,
            ifc_class=ifc_class,
            name=pending.name,
            overall_width=pending.overall_width,
            overall_height=pending.overall_height,
            components=fill_components,
            pending=pending,
            opening_entity=opening_entity,
            container=container,
            context=context,
            type_entity=None,
            opening_anchor="sw",
        )
    else:
        fill = _build_fill(
            ifc_file=ifc_file,
            ifc_class=ifc_class,
            name=pending.name,
            overall_width=pending.overall_width,
            overall_height=pending.overall_height,
            pending=pending,
            opening_entity=opening_entity,
            container=container,
            context=context,
            type_entity=None,
            opening_anchor="sw",
            graph_name=pending.component_graph,
        )

    post_process(ifc_file, fill, pending)
    return fill


def build_window_model_b(
    ifc_file: ifcopenshell.file,
    pending,
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """Model B: IfcOpeningElement + IfcWindow from a component-graph preset."""
    return _build_model_b(
        ifc_file,
        "IfcWindow",
        pending,
        host_entity,
        container,
        context,
        params_extras={"window_type": pending.window_type},
        post_process=lambda f, fill, p: _set_window_type_attr(f, fill, p.window_type),
    )


def build_door_model_b(
    ifc_file: ifcopenshell.file,
    pending,
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """Model B: IfcOpeningElement + IfcDoor from a component-graph preset."""
    return _build_model_b(
        ifc_file,
        "IfcDoor",
        pending,
        host_entity,
        container,
        context,
        params_extras={"operation_type": pending.operation_type},
        post_process=lambda f, fill, p: _set_door_operation(f, fill, p.operation_type),
    )


# ---------------------------------------------------------------------------
# Standalone fill builder (no host / no opening)
# ---------------------------------------------------------------------------


def build_standalone_fill(
    ifc_file: ifcopenshell.file,
    ifc_class: str,
    name: str,
    components: list,
    context: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,
    placement: ifcopenshell.entity_instance | None = None,
    type_entity=None,
    overall_width: float = 0.0,
    overall_height: float = 0.0,
) -> ifcopenshell.entity_instance:
    """Create a fill product (window/door/plate) without a host opening.

    The product is placed directly in *container* without an
    ``IfcOpeningElement`` or ``IfcRelFillsElement`` — useful for
    standalone elements such as storefronts, free-standing windows,
    or shading devices that use path-based geometry.

    Args:
        ifc_file:   Open ifcopenshell file.
        ifc_class:  IFC class (e.g. ``"IfcWindow"``, ``"IfcPlate"``).
        name:       Product name.
        components: List of ``EvaluatedComponent`` objects (no ``Opening``
                    role — that would create a host relationship).
        context:    Body sub-context.
        container:  Spatial container (``IfcBuildingStorey`` or
                    ``IfcSite``, etc.).
        placement:  Optional ``IfcLocalPlacement``.  When ``None`` a
                    direct (world-origin) placement is created.
        type_entity: Optional type entity to assign (e.g. ``IfcWindowType``).
        overall_width:  Overall width for IfcWindow/IfcDoor (default 0.0).
        overall_height: Overall height for IfcWindow/IfcDoor (default 0.0).

    Returns:
        The created IFC product entity.
    """
    solids: list = []

    for comp in components:
        material = comp.material or {
            "color": {"r": 0.75, "g": 0.75, "b": 0.75},
            "transparency": 0.0,
            "name": "Default",
        }
        solid = apply_material_to_solid(ifc_file, comp.solid, material)
        solids.append(solid)

    if not solids:
        raise ValueError("build_standalone_fill: no components")

    has_boolean = any(s.is_a("IfcBooleanResult") for s in solids)
    has_swept = any(s.is_a("IfcExtrudedAreaSolid") for s in solids)
    if has_boolean and has_swept:
        rep_type = "SolidModel"
    elif has_boolean:
        rep_type = "CSG"
    else:
        rep_type = "SweptSolid"

    shape_rep = ifc_file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType=rep_type,
        Items=solids,
    )

    prod_def_shape = ifc_file.create_entity(
        "IfcProductDefinitionShape",
        Representations=[shape_rep],
    )

    if placement is None:
        from ifckit.geometry import Vec

        ax = axis2placement3d(ifc_file, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0))
        placement = ifc_file.create_entity("IfcLocalPlacement", RelativePlacement=ax)

    fill = ifc_file.create_entity(
        ifc_class,
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        Description=None,
        ObjectType="standalone",
        ObjectPlacement=placement,
        Representation=prod_def_shape,
    )

    if ifc_class in ("IfcWindow", "IfcDoor"):
        fill.OverallWidth = overall_width
        fill.OverallHeight = overall_height

    if type_entity is not None:
        _assign_type(ifc_file, fill, type_entity)

    ifcopenshell.api.run(
        "spatial.assign_container",
        ifc_file,
        products=[fill],
        relating_structure=container,
    )

    return fill


# ---------------------------------------------------------------------------
# Builder classes for the default_registry
# ---------------------------------------------------------------------------
