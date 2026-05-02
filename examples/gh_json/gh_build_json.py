"""
gh_build_json.py — GH Script: "Build IFC JSON"
===============================================

Stateless: merges multiple Collector outputs into a full IFC project JSON.

Flow:  [Collector A] ──┐
       [Collector B] ──┼──→ [Build JSON] ──→ [Export/Preview]
       [Collector C] ──┘

Inputs
------
json_input   : list — JSON strings from Collectors (one per storey).
project_name : str  — IFC project name (default "GH Project").
author       : str  — Author string stored in IFC header (default "GH").
unit         : str  — "METRE" or "MILLIMETRE" (default "MILLIMETRE").
ifc_version  : str  — "IFC2X3" or "IFC4" (default "IFC2X3").

Outputs
-------
out      : str — Status message (element count or error).
json_out : str — Full IFC project JSON ready for Export/Preview node.
                 Section planes / drawings are added separately via
                 model.add_drawing() after export, not via this node.
"""

import json

out = ""
json_out = ""

if not json_input:
    out = "ERROR: no JSON input."
else:
    try:
        _project_name = str(project_name) if project_name else "GH Project"
        _author = str(author) if author else "GH"
        _unit = str(unit).upper() if unit else "MILLIMETRE"
        _ifc_version = str(ifc_version).upper() if ifc_version else "IFC2X3"

        inputs = json_input if isinstance(json_input, list) else [json_input]

        storeys_out = []
        total = 0

        for item in inputs:
            s = str(item).strip()
            if not s:
                continue
            storey = json.loads(s)
            sname = storey.get("storey_name", "Default")
            elev = float(storey.get("elevation", 0.0))
            elems = storey.get("elements", [])
            parsed = [json.loads(e) if isinstance(e, str) else e for e in elems]
            storeys_out.append(
                {
                    "name": sname,
                    "elevation": elev,
                    "elements": parsed,
                }
            )
            total += len(parsed)

        project_json = {
            "ifc_version": _ifc_version,
            "project": {"name": _project_name, "author": _author},
            "unit": _unit,
            "site": {"name": "Site"},
            "buildings": [{"name": "Building", "storeys": storeys_out}],
        }

        out = "Built project JSON: {} elements across {} storey(s).".format(
            total, len(storeys_out)
        )
        json_out = json.dumps(project_json, separators=(",", ":"))

    except Exception as exc:
        out = "FAILED: {}".format(exc)

print(out)
