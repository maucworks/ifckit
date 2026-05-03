"""
gh_build_json.py  —  GH Script component: "ifckit Build JSON"
==============================================================

@component  nickname:"ifckit Build JSON"
@group "Export"
@input  storeys      : str  list — Storey bundle JSON strings from gh_storey nodes
@input  project_name : str  item — IFC project name (default "GH Project")
@input  author       : str  item — Author string (default "GH")
@input  unit         : str  item — "METRE" or "MILLIMETRE" (default "MILLIMETRE")
@input  ifc_version  : str  item — "IFC2X3" or "IFC4" (default "IFC2X3")
@output out      : str item — Status message
@output json_out : str item — Full IFC project JSON for Export node

Assembles storeys into a project JSON ready for gh_export_json.
Openings and their fills are nested inside elements (no flat openings/doors/windows arrays).
door_types / window_types are hoisted from storey bundles to project root.

Storey bundle format (from gh_storey):
    {
        "storey_name": "Ground Floor",
        "elevation": 0.0,
        "elements":     [...],   ← openings nested inside elements
        "door_types":   [...],   ← hoisted to root
        "window_types": [...]    ← hoisted to root
    }
"""

import json
from ifckit import rhinokit as rk

out = ""
json_out = ""

if not storeys:
    out = "ERROR: no storey input."
else:
    try:
        _project_name = str(project_name) if project_name else "GH Project"
        _author       = str(author) if author else "GH"
        _unit         = str(unit).upper() if unit else "MILLIMETRE"
        _ifc_version  = str(ifc_version).upper() if ifc_version else "IFC2X3"

        inputs = storeys if isinstance(storeys, list) else [storeys]

        storeys_out   = []
        door_types    = []
        window_types  = []
        total_elems   = 0

        for raw in inputs:
            s = str(raw).strip()
            if not s:
                continue
            bundle = json.loads(s)

            elems = rk.parse_json_list(bundle.get("elements", []))

            # Hoist type arrays to root — deduplicate by type_key/name.
            for dt in rk.parse_json_list(bundle.get("door_types", [])):
                key = dt.get("type_key") or dt.get("name")
                if not any((x.get("type_key") or x.get("name")) == key for x in door_types):
                    door_types.append(dt)

            for wt in rk.parse_json_list(bundle.get("window_types", [])):
                key = wt.get("type_key") or wt.get("name")
                if not any((x.get("type_key") or x.get("name")) == key for x in window_types):
                    window_types.append(wt)

            storeys_out.append({
                "name":      bundle.get("storey_name", "Storey"),
                "elevation": float(bundle.get("elevation", 0.0)),
                "elements":  elems,
            })
            total_elems += len(elems)

        project_json = {
            "ifc_version": _ifc_version,
            "project":     {"name": _project_name, "author": _author},
            "unit":        _unit,
            "site":        {"name": "Site"},
            "buildings":   [{"name": "Building", "storeys": storeys_out}],
        }
        if door_types:
            project_json["door_types"] = door_types
        if window_types:
            project_json["window_types"] = window_types

        n_openings = sum(
            len(e.get("openings", []))
            for s in storeys_out for e in s.get("elements", [])
            if isinstance(e, dict)
        )
        n_fills = sum(
            len(op.get("doors", [])) + len(op.get("windows", []))
            for s in storeys_out for e in s.get("elements", [])
            if isinstance(e, dict)
            for op in e.get("openings", [])
        )

        out = (
            "Built: {} elements, {} openings, {} fills, "
            "{} door types, {} window types across {} storey(s).".format(
                total_elems, n_openings, n_fills,
                len(door_types), len(window_types), len(storeys_out),
            )
        )
        json_out = json.dumps(project_json, separators=(",", ":"))

    except Exception as exc:
        out = f"FAILED: {exc}"
