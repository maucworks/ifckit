"""
ifckit.json_build
=================

JSON to IFC building functions.

2-pass build (Model B only)
----------------------------
Pass 1 — spatial hierarchy + host elements (walls, slabs, spaces, …)
          Each element can carry an optional ``"id"`` field; the resulting
          ``EntityHandle`` is stored in a flat ``id_map`` dict keyed by
          that string.

Pass 2 — door/window *types* (root-level ``door_types`` / ``window_types``
          arrays) + *doors* and *windows* (nested directly inside each element).
          Every fill must reference a type via ``type_ref``.  The type carries
          ``component_graph`` which drives the Model B opening + fill geometry.

JSON schema
-----------
Root level::

    "door_types":  [{ ...PendingDoorType fields..., "component_graph": "door_flush" }]
    "window_types":[{ ...PendingWindowType fields..., "component_graph": "fixed_casement" }]

Per-storey elements (fills nested directly in element)::

    "elements": [
      {
        "id": "w1",
        "type": "basic_wall",
        ...,
        "windows": [
          {
            "plane": {"origin": {...}, "x_axis": {...}, "y_axis": {...}},
            "overall_width": 1200.0,
            "overall_height": 1000.0,
            "type_ref": "WT-1200x1000"
          }
        ],
        "doors": [
          {
            "plane": {"origin": {...}, "x_axis": {...}, "y_axis": {...}},
            "overall_width": 900.0,
            "overall_height": 2100.0,
            "type_ref": "DT-900x2100"
          }
        ]
      }
    ]
"""

import json
from typing import Any, Dict, List, Optional

from ifckit.elements.registry import ElementRegistry
from ifckit.model import IfcModel
from ifckit.schema import IfcSchema, LengthUnit
from ifckit.validator import ValidationResult as JsonValidationResult
from ifckit.validator import validate

# ---------------------------------------------------------------------------
# validate_json
# ---------------------------------------------------------------------------


def validate_json(data: Dict[str, Any]) -> JsonValidationResult:
    """Validate a JSON dict against the ifckit JSON schema."""
    errors: List[str] = []
    warnings: List[str] = []

    if "ifc_version" in data:
        if data["ifc_version"] not in ("IFC2X3", "IFC4", "IFC4X3"):
            errors.append(
                f"ifc_version must be 'IFC2X3', 'IFC4' or 'IFC4X3', got {data['ifc_version']}"
            )
    else:
        errors.append("Missing required field: ifc_version")

    if "project" in data:
        if not isinstance(data["project"], dict):
            errors.append("project must be a dict")
        elif "name" not in data["project"]:
            errors.append("project.name is required")
    else:
        errors.append("Missing required field: project")

    if "unit" in data:
        if data["unit"] not in ("METRE", "MILLIMETRE"):
            errors.append(f"unit must be METRE or MILLIMETRE, got {data['unit']}")
    else:
        errors.append("Missing required field: unit")

    if "buildings" in data:
        for i, bldg in enumerate(data.get("buildings", [])):
            if "name" not in bldg:
                errors.append(f"buildings[{i}] missing name")
            for j, storey in enumerate(bldg.get("storeys", [])):
                if "name" not in storey:
                    errors.append(f"buildings[{i}].storeys[{j}] missing name")

    # door_types / window_types — each entry must have overall_width + overall_height
    for section, label in (("door_types", "door_types"), ("window_types", "window_types")):
        for k, entry in enumerate(data.get(section, [])):
            if not isinstance(entry, dict):
                errors.append(f"{label}[{k}] must be a dict")
                continue
            for required in ("overall_width", "overall_height"):
                if required not in entry:
                    errors.append(f"{label}[{k}] missing required field '{required}'")

    # per-element fills — light structural check
    for i, bldg in enumerate(data.get("buildings", [])):
        for j, storey in enumerate(bldg.get("storeys", [])):
            prefix = f"buildings[{i}].storeys[{j}]"

            for m, elem in enumerate(storey.get("elements", [])):
                if not isinstance(elem, dict):
                    continue
                eprefix = f"{prefix}.elements[{m}]"

                for section, label in (("windows", "window"), ("doors", "door")):
                    for k, fill in enumerate(elem.get(section, [])):
                        if not isinstance(fill, dict):
                            errors.append(f"{eprefix}.{section}[{k}] must be a dict")
                            continue
                        for required in ("plane", "overall_width", "overall_height"):
                            if required not in fill:
                                errors.append(
                                    f"{eprefix}.{section}[{k}] missing required field '{required}'"
                                )
                        if "type_ref" not in fill and "component_graph" not in fill:
                            errors.append(
                                f"{eprefix}.{section}[{k}] requires 'type_ref' or 'component_graph'"
                            )

    return JsonValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# _parse_plane
# ---------------------------------------------------------------------------


def _parse_plane(plane_data: Dict[str, Any]):
    """Parse a plane dict to a Plane instance."""
    from ifckit.geometry import Plane, Vec

    def _vec(d):
        return Vec(float(d["x"]), float(d["y"]), float(d["z"]))

    return Plane(
        origin=_vec(plane_data["origin"]),
        x_axis=_vec(plane_data["x_axis"]),
        y_axis=_vec(plane_data["y_axis"]),
    )


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def build(data: Dict[str, Any], output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON dict (Model B only).

    Uses a 2-pass approach:

    * **Pass 1** – spatial hierarchy + host elements (walls, slabs, spaces).
    * **Pass 2** – door/window types + fills nested in elements.

    Args:
        data:        Validated JSON dict.
        output_path: If provided, save the model to this path after building.

    Returns:
        The built :class:`~ifckit.model.IfcModel`.

    Raises:
        ValueError: If JSON validation fails or any ref is unresolved.
    """
    json_result = validate_json(data)
    if not json_result.ok:
        raise ValueError(f"Invalid JSON: {'; '.join(json_result.errors)}")

    schema_str = data.get("ifc_version", "IFC4")
    schema = {"IFC2X3": IfcSchema.IFC2X3, "IFC4": IfcSchema.IFC4, "IFC4X3": IfcSchema.IFC4X3}.get(
        schema_str, IfcSchema.IFC4
    )

    project_name = data.get("project", {}).get("name", "Unnamed Project")
    author = data.get("project", {}).get("author", "")
    unit_str = data.get("unit", "METRE")
    unit = LengthUnit.MILLIMETRE if unit_str == "MILLIMETRE" else LengthUnit.METRE

    model = IfcModel(name=project_name, schema=schema, author=author, unit=unit)
    site_data = data.get("site") or {}
    site = model.add_site(site_data.get("name", "Site"))

    id_map, storey_map = _pass1_spatial(model, data, site)
    type_map, type_entity_map = _pass2a_types(model, data)
    _pass2b_fills(model, data, id_map, type_map, type_entity_map)
    _add_drawings(model, data)

    if output_path:
        model.save(output_path)

    return model


def _pass1_spatial(
    model: IfcModel, data: Dict[str, Any], site: Any
) -> tuple[Dict[str, Any], Dict[tuple, Any]]:
    """:meta private:"""
    id_map: Dict[str, Any] = {}
    storey_map: Dict[tuple, Any] = {}

    for bi, bldg_data in enumerate(data.get("buildings", [])):
        building = site.add_building(bldg_data.get("name", "Building"))

        for si, storey_data in enumerate(bldg_data.get("storeys", [])):
            storey = building.add_storey(
                storey_data.get("name", "Storey"), elevation=storey_data.get("elevation", 0.0)
            )
            storey_map[(bi, si)] = storey

            storey_ids: set = set()
            for elem_data in storey_data.get("elements", []):
                elem_type = elem_data.get("type")
                elem_dict = elem_data.get("data") if "data" in elem_data else elem_data

                try:
                    cls = ElementRegistry.get(elem_type)
                except KeyError:
                    raise KeyError(
                        f"Unknown element type {elem_type!r} in "
                        f"building '{bldg_data.get('name')}' / "
                        f"storey '{storey_data.get('name')}'. "
                        f"Available: {list(ElementRegistry.types().keys())}"
                    )
                pending = cls.from_dict(elem_dict)
                if "hatch_pattern" in elem_data:
                    pending.hatch_pattern = elem_data["hatch_pattern"]

                result = validate(pending)
                if not result.ok:
                    raise ValueError(f"Validation failed: {result.errors}")

                handle = storey.add(pending)

                elem_id = elem_data.get("id") or elem_dict.get("id")
                if elem_id:
                    if elem_id in storey_ids:
                        raise ValueError(f"Duplicate element id {elem_id!r} in JSON")
                    storey_ids.add(elem_id)
                    scoped_id = f"{elem_id}__s{si}" if elem_id in id_map else elem_id
                    id_map[scoped_id] = handle

            from ifckit.elements.space import PendingSpace

            for space_data in storey_data.get("spaces", []):
                pending_space = PendingSpace.from_dict(space_data)
                result = validate(pending_space)
                if not result.ok:
                    raise ValueError(f"Space validation failed: {result.errors}")
                handle = storey.add(pending_space)
                space_id = space_data.get("id")
                if space_id:
                    if space_id in storey_ids:
                        raise ValueError(f"Duplicate element id {space_id!r} in JSON")
                    storey_ids.add(space_id)
                    scoped_id = f"{space_id}__s{si}" if space_id in id_map else space_id
                    id_map[scoped_id] = handle

    return id_map, storey_map


def _pass2a_types(model: IfcModel, data: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """:meta private:"""
    from ifckit.elements.types import PendingDoorType, PendingWindowType

    type_map: Dict[str, Any] = {}
    type_entity_map: Dict[str, Any] = {}

    for dt_data in data.get("door_types", []):
        pending_dt = PendingDoorType.from_dict(dt_data)
        dt_handle = model.add_door_type(pending_dt)
        if pending_dt.name:
            type_map[pending_dt.name] = pending_dt
            type_entity_map[pending_dt.name] = dt_handle

    for wt_data in data.get("window_types", []):
        pending_wt = PendingWindowType.from_dict(wt_data)
        wt_handle = model.add_window_type(pending_wt)
        if pending_wt.name:
            type_map[pending_wt.name] = pending_wt
            type_entity_map[pending_wt.name] = wt_handle

    return type_map, type_entity_map


def _pass2b_fills(
    model: IfcModel,
    data: Dict[str, Any],
    id_map: Dict[str, Any],
    type_map: Dict[str, Any],
    type_entity_map: Dict[str, Any],
) -> None:
    """:meta private:"""
    from ifckit.elements.opening import PendingDoor, PendingWindow
    from ifckit.elements.types import PendingDoorType, PendingWindowType

    for bi, bldg_data in enumerate(data.get("buildings", [])):
        for si, storey_data in enumerate(bldg_data.get("storeys", [])):
            for ei, elem_data in enumerate(storey_data.get("elements", [])):
                elem_dict = elem_data.get("data") if "data" in elem_data else elem_data
                elem_id = elem_data.get("id") or elem_dict.get("id")
                # Use the same registration logic as pass1: check plain id first, then scoped
                lookup_id = elem_id
                scoped_id = f"{elem_id}__s{si}" if elem_id else None
                if lookup_id and lookup_id not in id_map and scoped_id in id_map:
                    lookup_id = scoped_id

                # Check if element is missing but has nested fills
                if not lookup_id or lookup_id not in id_map:
                    if elem_data.get("windows") or elem_data.get("doors"):
                        eprefix = f"buildings[{bi}].storeys[{si}].elements[{ei}]"
                        import warnings

                        warnings.warn(
                            f"{eprefix}: element has no 'id' or id not found — "
                            f"{len(elem_data.get('windows', []))} window(s) and "
                            f"{len(elem_data.get('doors', []))} door(s) will be skipped.",
                            stacklevel=2,
                        )
                    continue

                host_handle = id_map[lookup_id]
                eprefix = f"buildings[{bi}].storeys[{si}].elements[{ei}]"

                for wk, win_data in enumerate(elem_data.get("windows", [])):
                    type_ref = win_data.get("type_ref")
                    component_graph = win_data.get("component_graph")

                    pending_wt = None
                    if type_ref:
                        pending_wt = type_map.get(type_ref)
                        if pending_wt is None:
                            raise ValueError(
                                f"{eprefix}.windows[{wk}]: "
                                f"type_ref {type_ref!r} not found. "
                                f"Available: {sorted(type_map)}"
                            )
                        if not isinstance(pending_wt, PendingWindowType):
                            raise ValueError(
                                f"{eprefix}.windows[{wk}]: "
                                f"type_ref {type_ref!r} is not a window type."
                            )
                        if not pending_wt.component_graph:
                            raise ValueError(
                                f"{eprefix}.windows[{wk}]: "
                                f"window type {type_ref!r} has no component_graph."
                            )
                    elif component_graph:
                        pending_wt = PendingWindowType(
                            name=f"inline_{component_graph}",
                            overall_width=win_data.get("overall_width", 1000),
                            overall_height=win_data.get("overall_height", 1000),
                            component_graph=component_graph,
                        )
                    else:
                        raise ValueError(
                            f"{eprefix}.windows[{wk}]: requires 'type_ref' or 'component_graph'"
                        )

                    plane = _parse_plane(win_data["plane"])
                    merged_params = _merge_params(pending_wt, win_data)
                    merged_materials = _merge_materials(pending_wt, win_data)

                    pending_win = PendingWindow(
                        overall_width=float(win_data["overall_width"]),
                        overall_height=float(win_data["overall_height"]),
                        plane=plane,
                        component_graph=pending_wt.component_graph,
                        name=win_data.get("name", ""),
                        parameters=merged_params if merged_params else None,
                        material_overrides=merged_materials if merged_materials else None,
                    )
                    win_handle = model.add(pending_win, host_handle)

                    if type_ref and type_ref in type_entity_map:
                        from ifckit.builders.door_window import _assign_type

                        wt_entity = type_entity_map[type_ref].entity
                        _assign_type(model.ifc_file, win_handle.entity, wt_entity)

                for dk, door_data in enumerate(elem_data.get("doors", [])):
                    type_ref = door_data.get("type_ref")
                    component_graph = door_data.get("component_graph")

                    pending_dt = None
                    if type_ref:
                        pending_dt = type_map.get(type_ref)
                        if pending_dt is None:
                            raise ValueError(
                                f"{eprefix}.doors[{dk}]: "
                                f"type_ref {type_ref!r} not found. "
                                f"Available: {sorted(type_map)}"
                            )
                        if not isinstance(pending_dt, PendingDoorType):
                            raise ValueError(
                                f"{eprefix}.doors[{dk}]: type_ref {type_ref!r} is not a door type."
                            )
                        if not pending_dt.component_graph:
                            raise ValueError(
                                f"{eprefix}.doors[{dk}]: "
                                f"door type {type_ref!r} has no component_graph."
                            )
                    elif component_graph:
                        pending_dt = PendingDoorType(
                            name=f"inline_{component_graph}",
                            overall_width=door_data.get("overall_width", 1000),
                            overall_height=door_data.get("overall_height", 2100),
                            component_graph=component_graph,
                        )
                    else:
                        raise ValueError(
                            f"{eprefix}.doors[{dk}]: requires 'type_ref' or 'component_graph'"
                        )

                    plane = _parse_plane(door_data["plane"])
                    merged_params = _merge_params(pending_dt, door_data)
                    merged_materials = _merge_materials(pending_dt, door_data)

                    pending_door = PendingDoor(
                        overall_width=float(door_data["overall_width"]),
                        overall_height=float(door_data["overall_height"]),
                        plane=plane,
                        component_graph=pending_dt.component_graph,
                        name=door_data.get("name", ""),
                        parameters=merged_params if merged_params else None,
                        material_overrides=merged_materials if merged_materials else None,
                    )
                    door_handle = model.add(pending_door, host_handle)

                    if type_ref and type_ref in type_entity_map:
                        from ifckit.builders.door_window import _assign_type

                        dt_entity = type_entity_map[type_ref].entity
                        _assign_type(model.ifc_file, door_handle.entity, dt_entity)


def _merge_params(pending_type, data: Dict[str, Any]) -> Dict[str, float]:
    """:meta private:"""
    merged: Dict[str, float] = {}
    for attr in ("lining_depth", "lining_thickness", "panel_depth", "panel_height", "panel_width"):
        val = getattr(pending_type, attr, None)
        if val is not None:
            merged[attr] = val
    if data.get("parameters"):
        merged.update(data["parameters"])
    return merged


def _merge_materials(pending_type, data: Dict[str, Any]) -> Dict[str, Any]:
    """:meta private:"""
    merged: Dict[str, Any] = {}
    if pending_type.material_overrides:
        merged.update(pending_type.material_overrides)
    if data.get("material_overrides"):
        for role, material_def in data["material_overrides"].items():
            if role in merged and isinstance(merged[role], dict):
                merged[role] = {**merged[role], **material_def}
            else:
                merged[role] = material_def
    return merged


def _add_drawings(model: IfcModel, data: Dict[str, Any]) -> None:
    """:meta private:"""
    for drawing_data in data.get("drawings", []):
        dname = drawing_data.get("name", "Drawing")
        target_view = drawing_data.get("target_view", "PLAN_VIEW")
        raw_origin = drawing_data.get("origin", [0.0, 0.0, 0.0])
        raw_x_axis = drawing_data.get("x_axis", [1.0, 0.0, 0.0])
        raw_z_axis = drawing_data.get("z_axis", [0.0, 0.0, -1.0])

        for field_name, val in (
            ("origin", raw_origin),
            ("x_axis", raw_x_axis),
            ("z_axis", raw_z_axis),
        ):
            if not isinstance(val, (list, tuple)) or len(val) != 3:
                raise ValueError(
                    f"Drawing {dname!r}: '{field_name}' must be a list of 3 numbers, got {val!r}"
                )

        model.add_drawing(
            name=dname,
            target_view=target_view,
            position=(float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2])),
            x_axis=(float(raw_x_axis[0]), float(raw_x_axis[1]), float(raw_x_axis[2])),
            z_axis=(float(raw_z_axis[0]), float(raw_z_axis[1]), float(raw_z_axis[2])),
        )


def build_from_json(json_str: str, output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON string."""
    return build(json.loads(json_str), output_path)
