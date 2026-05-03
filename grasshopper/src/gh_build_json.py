"""
gh_build_json.py  —  GH Script component: "ifckit Build JSON"
==============================================================

@component  nickname:"ifckit Build JSON"
@group "Export"
@input  json_input   : str  list — JSON strings from element nodes
@input  project_name : str  item — IFC project name (default "GH Project")
@input  author       : str  item — Author string (default "GH")
@input  unit         : str  item — "METRE" or "MILLIMETRE" (default "MILLIMETRE")
@input  ifc_version  : str  item — "IFC2X3" or "IFC4" (default "IFC2X3")
@output out      : str item — Status message
@output json_out : str item — Full IFC project JSON for Export node

Stateless: merges element JSON strings into a full IFC project JSON.
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
