"""
ifckit.json_build
=================

JSON to IFC building functions.

Moved here to avoid import issues with 'ifckit.schema' being treated
as a module vs package in some environments.

3-pass build
------------
Pass 1 — spatial hierarchy + host elements (walls, slabs, spaces, …)
          Each element can carry an optional ``"id"`` field; the resulting
          ``EntityHandle`` is stored in a flat ``id_map`` dict keyed by
          that string.

Pass 2 — door/window *types* (root-level ``door_types`` / ``window_types``
          arrays) + *openings* (nested inside each element in the
          per-storey ``elements`` array).
          Host is implicit — the element that contains the opening.
          n:1 supported: each opening may have multiple door/window fills.

Pass 3 — *doors* and *windows* (nested inside each opening).
          Each fill may supply ``type_ref`` to reference a root-level type.

JSON schema
-----------
Root level::

    "door_types":  [{ ...PendingDoorType fields... }]
    "window_types":[{ ...PendingWindowType fields... }]

Per-storey elements (openings nested in element, fills nested in opening)::

    "elements": [
      {
        "id": "w1",
        "type": "basic_wall",
        ...,
        "openings": [
          {
            "plane": {...},
            "width": 0.9,
            "height": 2.1,
            "doors": [
              {"overall_width": 0.9, "overall_height": 2.1, "type_ref": "my-dt"}
            ],
            "windows": [
              {"overall_width": 1.2, "overall_height": 1.4, "type_ref": "my-wt"}
            ]
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

    # per-element openings (nested) — light structural check
    for i, bldg in enumerate(data.get("buildings", [])):
        for j, storey in enumerate(bldg.get("storeys", [])):
            prefix = f"buildings[{i}].storeys[{j}]"

            for m, elem in enumerate(storey.get("elements", [])):
                if not isinstance(elem, dict):
                    continue
                eprefix = f"{prefix}.elements[{m}]"

                for k, op in enumerate(elem.get("openings", [])):
                    if not isinstance(op, dict):
                        errors.append(f"{eprefix}.openings[{k}] must be a dict")
                        continue
                    for required in ("plane", "width", "height"):
                        if required not in op:
                            errors.append(
                                f"{eprefix}.openings[{k}] missing required field '{required}'"
                            )

                    for dk, door in enumerate(op.get("doors", [])):
                        if not isinstance(door, dict):
                            errors.append(f"{eprefix}.openings[{k}].doors[{dk}] must be a dict")
                            continue
                        for required in ("overall_width", "overall_height"):
                            if required not in door:
                                path = f".openings[{k}].doors[{dk}]"
                                errors.append(f"{eprefix}{path} missing field '{required}'")

                    for wk, win in enumerate(op.get("windows", [])):
                        if not isinstance(win, dict):
                            errors.append(f"{eprefix}.openings[{k}].windows[{wk}] must be a dict")
                            continue
                        for required in ("overall_width", "overall_height"):
                            if required not in win:
                                path = f".openings[{k}].windows[{wk}]"
                                errors.append(f"{eprefix}{path} missing field '{required}'")

    return JsonValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def build(data: Dict[str, Any], output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON dict.

    Uses a 3-pass approach:

    * **Pass 1** – spatial hierarchy + host elements (walls, slabs, spaces).
      Elements with an ``"id"`` field are registered in a flat ``id_map``.
    * **Pass 2** – door/window types (root-level arrays) + openings
      (per-storey arrays).  Openings reference hosts via ``host_ref``.
    * **Pass 3** – doors + windows (per-storey arrays).  Fills reference
      openings via ``opening_ref`` and optionally a type via ``type_ref``.

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

    # Flat map: user-assigned string id → EntityHandle.
    # Populated by pass 1 (elements) and pass 2 (openings).
    id_map: Dict[str, Any] = {}

    # Storey handles keyed by (bldg_index, storey_index) for pass 2/3.
    storey_map: Dict[tuple, Any] = {}

    # -----------------------------------------------------------------------
    # Pass 2 — spatial hierarchy + host elements
    # -----------------------------------------------------------------------

    for bi, bldg_data in enumerate(data.get("buildings", [])):
        building = site.add_building(bldg_data.get("name", "Building"))

        for si, storey_data in enumerate(bldg_data.get("storeys", [])):
            storey = building.add_storey(
                storey_data.get("name", "Storey"), elevation=storey_data.get("elevation", 0.0)
            )
            storey_map[(bi, si)] = storey

            storey_ids: set = set()  # ids seen within this storey — duplicates are an error
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
                    if elem_id in id_map:
                        # Same id reused in a different storey (common GH pattern: one
                        # wall component feeding N storey nodes).  Scope by storey index
                        # so downstream opening lookups still resolve within each storey.
                        scoped_id = f"{elem_id}__s{si}"
                    else:
                        scoped_id = elem_id
                    id_map[scoped_id] = handle

            # spaces[]
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
                    if space_id in id_map:
                        scoped_id = f"{space_id}__s{si}"
                    else:
                        scoped_id = space_id
                    id_map[scoped_id] = handle

    # -----------------------------------------------------------------------
    # Pass 2a — door/window types (root-level)
    # -----------------------------------------------------------------------

    from ifckit.elements.types import PendingDoorType, PendingWindowType

    type_handle_map: Dict[str, Any] = {}  # type_key / name → EntityHandle

    for dt_data in data.get("door_types", []):
        pending_dt = PendingDoorType.from_dict(dt_data)
        handle = model.add_door_type(pending_dt)
        # Register under type_key and, if present, name.
        type_handle_map[pending_dt.type_key] = handle
        if pending_dt.name:
            type_handle_map[pending_dt.name] = handle

    for wt_data in data.get("window_types", []):
        pending_wt = PendingWindowType.from_dict(wt_data)
        handle = model.add_window_type(pending_wt)
        type_handle_map[pending_wt.type_key] = handle
        if pending_wt.name:
            type_handle_map[pending_wt.name] = handle

    # -----------------------------------------------------------------------
    # Pass 2b — openings + Pass 3 — doors/windows (nested in elements)
    # -----------------------------------------------------------------------

    from ifckit.elements.opening import PendingDoor, PendingOpening, PendingWindow

    for bi, bldg_data in enumerate(data.get("buildings", [])):
        for si, storey_data in enumerate(bldg_data.get("storeys", [])):
            storey = storey_map[(bi, si)]

            for ei, elem_data in enumerate(storey_data.get("elements", [])):
                elem_dict = elem_data.get("data") if "data" in elem_data else elem_data
                elem_id = elem_data.get("id") or elem_dict.get("id")
                # id may have been scoped to storey when duplicate across storeys
                scoped = f"{elem_id}__s{si}" if elem_id else None
                lookup_id = scoped if scoped in id_map else elem_id
                if lookup_id not in id_map:
                    continue  # element had no id, skip

                host_handle = id_map[lookup_id]
                eprefix = f"buildings[{bi}].storeys[{si}].elements[{ei}]"

                for ki, op_data in enumerate(elem_data.get("openings", [])):
                    pending_op = PendingOpening.from_dict(op_data)
                    opening_handle = model.add_opening(
                        pending_op, host=host_handle, container=storey
                    )

                    opprefix = f"{eprefix}.openings[{ki}]"

                    for dk, door_data in enumerate(op_data.get("doors", [])):
                        type_ref = door_data.get("type_ref")
                        door_type_handle = type_handle_map.get(type_ref) if type_ref else None
                        if type_ref and door_type_handle is None:
                            raise ValueError(
                                f"{opprefix}.doors[{dk}]: "
                                f"type_ref {type_ref!r} not found. "
                                f"Available: {sorted(type_handle_map)}"
                            )
                        pending_door = PendingDoor.from_dict(door_data)
                        model.add_door(
                            pending_door,
                            opening=opening_handle,
                            container=storey,
                            door_type=door_type_handle,
                            opening_anchor=pending_op.anchor,
                        )

                    for wk, win_data in enumerate(op_data.get("windows", [])):
                        type_ref = win_data.get("type_ref")
                        win_type_handle = type_handle_map.get(type_ref) if type_ref else None
                        if type_ref and win_type_handle is None:
                            raise ValueError(
                                f"{opprefix}.windows[{wk}]: "
                                f"type_ref {type_ref!r} not found. "
                                f"Available: {sorted(type_handle_map)}"
                            )
                        pending_win = PendingWindow.from_dict(win_data)
                        model.add_window(
                            pending_win,
                            opening=opening_handle,
                            container=storey,
                            window_type=win_type_handle,
                            opening_anchor=pending_op.anchor,
                        )

            # elements without an id can still have openings — walk again
            for ei, elem_data in enumerate(storey_data.get("elements", [])):
                elem_dict = elem_data.get("data") if "data" in elem_data else elem_data
                elem_id = elem_data.get("id") or elem_dict.get("id")
                if elem_id in id_map:
                    continue  # already handled above
                if not elem_data.get("openings"):
                    continue
                raise ValueError(
                    f"buildings[{bi}].storeys[{si}].elements[{ei}]: "
                    f"element has openings but no 'id' field — add an 'id' so the "
                    f"opening builder can resolve the host."
                )

    # -----------------------------------------------------------------------
    # Drawings (unchanged)
    # -----------------------------------------------------------------------

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

    if output_path:
        model.save(output_path)

    return model


def build_from_json(json_str: str, output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON string."""
    return build(json.loads(json_str), output_path)
