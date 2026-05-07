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
    opening_anchor: str = "s",
) -> ifcopenshell.entity_instance:
    """Create a fill element whose geometry comes from a component-graph preset.

    The graph is evaluated with ``w=overall_width``, ``h=overall_height`` plus
    any extra parameters from the type entity's property sets.  The anchor
    offset is applied as a translation on each component's solid placement so
    that the fill sits flush inside the opening void.

    Returns the created ``IfcDoor`` or ``IfcWindow`` entity.
    """
    from ifckit.builders.component_graph import evaluate_component_graph

    dx, dy = anchor_offset(opening_anchor, overall_width, overall_height)

    params: dict = {"w": overall_width, "h": overall_height}
    # Merge user-provided component graph parameters (occurrence-level overrides)
    if pending.parameters:
        params.update(pending.parameters)

    components = evaluate_component_graph(graph_name, ifc_file, context, params, pending.plane)

    # Each component solid has its own placement (z_offset from the graph).
    # Apply the anchor (dx, dy) as an additional XY translation on each placement.
    # IfcBooleanResult has no Position — _shift_solid_placement recurses into leaves.
    solids = []
    for comp in components:
        solid = comp.solid
        _shift_solid_placement(ifc_file, solid, dx, dy)

        # Apply material if defined in component or overridden by pending
        material = comp.material
        if pending.material_overrides and comp.role in pending.material_overrides:
            # Occurrence-level material override takes precedence
            material_override = pending.material_overrides[comp.role]
            if material and material_override:
                # Merge: override fills in missing keys from component default
                merged_material = material.copy()
                merged_material.update(material_override)
                material = merged_material
            elif material_override:
                material = material_override

        # Apply styling to solid — fall back to neutral grey if no material defined
        if not material:
            material = {
                "color": {"r": 0.75, "g": 0.75, "b": 0.75},
                "transparency": 0.0,
                "name": "Default",
            }
        solid = _apply_material_to_solid(ifc_file, solid, material)

        solids.append(solid)

    # Build shape representation with all component solids.
    # - SweptSolid: only when all items are IfcExtrudedAreaSolid
    # - SolidModel: when mixing IfcBooleanResult with IfcExtrudedAreaSolid
    # - CSG: only when ALL items are IfcBooleanResult (pure CSG tree)
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
    fill.ObjectPlacement = _relative_to_opening(ifc_file, opening_entity.ObjectPlacement)

    # NOTE: Do NOT assign fill to spatial structure container.
    # Fills are part of the opening's composition and should be positioned
    # relative to the opening, not the storey. Their spatial relationship
    # is indirect through the opening element.

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
    opening_anchor: str = "s",  # anchor from the parent PendingOpening
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


def _shift_solid_placement(
    ifc_file: ifcopenshell.file,
    solid: ifcopenshell.entity_instance,
    dx: float,
    dy: float,
) -> None:
    """Recursively shift all leaf solid placements by (dx, dy, 0).

    IfcBooleanResult has no Position attribute — recurse into operands
    until we reach leaf solids that do (e.g. IfcExtrudedAreaSolid).
    """
    from ifckit.geometry import Vec

    if solid.is_a("IfcBooleanResult"):
        _shift_solid_placement(ifc_file, solid.FirstOperand, dx, dy)
        _shift_solid_placement(ifc_file, solid.SecondOperand, dx, dy)
    elif hasattr(solid, "Position"):
        old_origin = solid.Position.Location
        ox = old_origin.Coordinates[0] + dx
        oy = old_origin.Coordinates[1] + dy
        oz = old_origin.Coordinates[2]
        solid.Position = axis2placement3d(ifc_file, Vec(ox, oy, oz), Vec(0, 0, 1), Vec(1, 0, 0))


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
    opening_anchor: str = "s",
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


def _extract_wall_thickness(host_entity: ifcopenshell.entity_instance) -> float:
    """
    Extract wall thickness from an IfcWall or IfcSlab entity.

    Strategy:
    1. Look for IfcExtrudedAreaSolid in the host representation.
       For a wall with a rectangular footprint, the profile is
       IfcRectangleProfileDef with YDim = thickness.
    2. Fallback: return 200 (200 mm, a common default).

    Args:
        host_entity: An IfcWall, IfcWallStandardCase, or IfcSlab entity.

    Returns:
        Thickness in millimeters (IFC metres are converted to mm for component_graph).
    """
    try:
        rep = host_entity.Representation
        if rep is None:
            return 200.0  # 200 mm default
        for shape_rep in rep.Representations:
            for item in shape_rep.Items:
                # Direct IfcExtrudedAreaSolid
                if item.is_a("IfcExtrudedAreaSolid"):
                    area = item.SweptArea
                    if area.is_a("IfcRectangleProfileDef"):
                        # For a wall: XDim = length, YDim = thickness
                        # IFC stores in metres, convert to mm for component_graph
                        return float(area.YDim) * 1000.0
                # IfcBooleanClippingResult wraps a solid
                if item.is_a("IfcBooleanClippingResult"):
                    first_op = item.FirstOperand
                    if first_op.is_a("IfcExtrudedAreaSolid"):
                        area = first_op.SweptArea
                        if area.is_a("IfcRectangleProfileDef"):
                            return float(area.YDim) * 1000.0
    except Exception:  # noqa: BLE001
        pass
    return 200.0  # 200 mm default


def _apply_material_to_solid(
    ifc_file: ifcopenshell.file,
    solid: ifcopenshell.entity_instance,
    material_def: Optional[dict],
) -> ifcopenshell.entity_instance:
    """
    Create an IfcStyledItem referencing the solid with color and transparency.

    The IfcStyledItem is created as a standalone entity in the file — it must
    NOT replace the solid in the representation Items list, because SweptSolid
    representations require raw solids as items. Returns the original solid
    unchanged so callers can safely append it to the items list.

    Args:
        ifc_file: IFC file object
        solid: IfcExtrudedAreaSolid or similar representation item
        material_def: Dict with keys:
            - color: {"r": 0.0-1.0, "g": 0.0-1.0, "b": 0.0-1.0}
            - transparency: 0.0-1.0 (0=transparent, 1=opaque)
            - name: optional material name

    Returns:
        The original solid (unchanged).
    """
    if not material_def:
        return solid

    color_def = material_def.get("color", {})
    transparency = material_def.get("transparency", 1.0)
    name = material_def.get("name", "")

    # Create RGB color entity
    color = ifc_file.create_entity(
        "IfcColourRgb",
        Red=float(color_def.get("r", 1.0)),
        Green=float(color_def.get("g", 1.0)),
        Blue=float(color_def.get("b", 1.0)),
    )

    # IfcSurfaceStyleRendering is the correct subtype — it is supported by all
    # major viewers (Blender, web-ifc, Bonsai). IfcSurfaceStyleShading is the
    # abstract base and may be ignored or handled inconsistently.
    # ReflectanceMethod=FLAT gives flat shading without specular highlights.
    shading = ifc_file.create_entity(
        "IfcSurfaceStyleRendering",
        SurfaceColour=color,
        Transparency=float(transparency),
        ReflectanceMethod="FLAT",
    )

    # BOTH: style applies to front and back faces.
    surface_style = ifc_file.create_entity(
        "IfcSurfaceStyle",
        Name=name or "Material",
        Side="BOTH",
        Styles=[shading],
    )

    # Create styled item referencing the solid.
    # IfcStyledItem must NOT be placed in the representation Items list —
    # SweptSolid representations require raw solids as items. The styled item
    # lives standalone in the file; geometry processors find it via Item=solid.
    ifc_file.create_entity(
        "IfcStyledItem",
        Item=solid,
        Styles=[surface_style],
    )

    return solid


def build_window_model_b(
    ifc_file: ifcopenshell.file,
    pending,  # PendingWindow with .plane and .component_graph set
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,  # IfcBuildingStorey
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """
    Model B: create an IfcOpeningElement + IfcWindow in one call.

    The opening geometry is produced by evaluating the preset's
    ``opening_nodes`` section. The fill geometry comes from ``nodes``.
    Both node lists share the same reference-space scaling:
    ``scale_x = actual_w / ref_w``, ``scale_y = actual_h / ref_h``.

    If the preset has no ``opening_nodes``, or all opening nodes have
    ``output: false``, no IfcOpeningElement is created (niche scenario).

    Args:
        ifc_file:    Open ifcopenshell file.
        pending:     PendingWindow — must have ``plane`` and ``component_graph``.
        host_entity: IfcWall or IfcSlab entity to void.
        container:   IfcBuildingStorey for spatial containment of the window.
        context:     Body sub-context.

    Returns:
        The created IfcWindow entity.

    Raises:
        ValueError: If pending.plane or pending.component_graph is not set.
    """
    from ifckit.builders.component_graph import evaluate_opening_nodes
    from ifckit.builders.opening import build_opening_from_solids

    if pending.plane is None:
        raise ValueError(
            "build_window_model_b: pending.plane must be set for Model B. "
            "Provide a Plane that defines the insert position in the host wall."
        )
    if not pending.component_graph:
        raise ValueError("build_window_model_b: pending.component_graph must be set for Model B.")

    wall_thickness = _extract_wall_thickness(host_entity)
    params = {
        "w": pending.overall_width,
        "h": pending.overall_height,
        "wall_thickness": wall_thickness,
    }
    # Merge user-provided component graph parameters (occurrence-level overrides)
    if pending.parameters:
        params.update(pending.parameters)

    opening_components = evaluate_opening_nodes(pending.component_graph, ifc_file, context, params)

    # Apply anchor offset to opening solids and apply materials

    opening_anchor = "s"
    dx, dy = anchor_offset(opening_anchor, pending.overall_width, pending.overall_height)
    opening_solids = []
    for comp in opening_components:
        solid = comp.solid
        _shift_solid_placement(ifc_file, solid, dx, dy)

        # Opening solids are voids — do NOT wrap in IfcStyledItem.
        opening_solids.append(solid)

    opening_entity = build_opening_from_solids(
        ifc_file,
        pending.plane,
        opening_solids,
        host_entity,
        context,
        name=f"Opening-{pending.name}" if pending.name else "",
    )

    if opening_entity is None:
        raise ValueError(
            f"build_window_model_b: preset {pending.component_graph!r} "
            "produced no opening solid (all opening_nodes have output: false "
            "or opening_nodes is absent). Cannot create IfcOpeningElement."
        )

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
        type_entity=None,
        opening_anchor="s",
        graph_name=pending.component_graph,
    )
    _set_window_type_attr(ifc_file, window, pending.window_type)
    return window


def build_door_model_b(
    ifc_file: ifcopenshell.file,
    pending,  # PendingDoor with .plane and .component_graph set
    host_entity: ifcopenshell.entity_instance,
    container: ifcopenshell.entity_instance,  # IfcBuildingStorey
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """
    Model B: create an IfcOpeningElement + IfcDoor in one call.

    See ``build_window_model_b`` for full documentation.

    Args:
        ifc_file:    Open ifcopenshell file.
        pending:     PendingDoor — must have ``plane`` and ``component_graph``.
        host_entity: IfcWall or IfcSlab entity to void.
        container:   IfcBuildingStorey for spatial containment of the door.
        context:     Body sub-context.

    Returns:
        The created IfcDoor entity.

    Raises:
        ValueError: If pending.plane or pending.component_graph is not set.
    """
    from ifckit.builders.component_graph import evaluate_opening_nodes
    from ifckit.builders.opening import build_opening_from_solids

    if pending.plane is None:
        raise ValueError(
            "build_door_model_b: pending.plane must be set for Model B. "
            "Provide a Plane that defines the insert position in the host wall."
        )
    if not pending.component_graph:
        raise ValueError("build_door_model_b: pending.component_graph must be set for Model B.")

    wall_thickness = _extract_wall_thickness(host_entity)
    params = {
        "w": pending.overall_width,
        "h": pending.overall_height,
        "wall_thickness": wall_thickness,
    }
    # Merge user-provided component graph parameters (occurrence-level overrides)
    if pending.parameters:
        params.update(pending.parameters)

    opening_components = evaluate_opening_nodes(pending.component_graph, ifc_file, context, params)

    # Apply anchor offset to opening solids and apply materials

    opening_anchor = "s"
    dx, dy = anchor_offset(opening_anchor, pending.overall_width, pending.overall_height)
    opening_solids = []
    for comp in opening_components:
        solid = comp.solid
        _shift_solid_placement(ifc_file, solid, dx, dy)

        # Opening solids are voids — do NOT wrap in IfcStyledItem.
        # Styling an opening solid puts an IfcStyledItem into the SweptSolid
        # representation, which breaks ifcopenshell geometry processing.
        opening_solids.append(solid)

    opening_entity = build_opening_from_solids(
        ifc_file,
        pending.plane,
        opening_solids,
        host_entity,
        context,
        name=f"Opening-{pending.name}" if pending.name else "",
    )

    if opening_entity is None:
        raise ValueError(
            f"build_door_model_b: preset {pending.component_graph!r} "
            "produced no opening solid (all opening_nodes have output: false "
            "or opening_nodes is absent). Cannot create IfcOpeningElement."
        )

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
        type_entity=None,
        opening_anchor="s",
        graph_name=pending.component_graph,
    )
    _set_door_operation(ifc_file, door, pending.operation_type)
    return door
