"""
gh_export_json.py  —  GH Script component: "Export IFC from JSON"
===================================================================

Stateless component: builds IFC from JSON and writes to file.

Each run is independent - no state, no accumulation.

Component inputs
----------------
json_input     : str  — JSON string from Collector.
project_name   : str  — IFC project name (default "GH Project").
author         : str  — Author string stored in IFC header (default "GH").
unit           : str  — "METRE" or "MILLIMETRE" (default MILLIMETRE).
ifc_output     : str  — Absolute path for the output IFC file.
run_export     : bool — Set True to actually write the file.
                          When False, reports element count.

Component outputs
-----------------
out  : str  — Status message (element count, file path, or error).

Workflow
--------
1. Wire Collector json_out to json_input here
2. Set run_export=False while testing - see what's in the model
3. Set run_export=True → IFC file is written
4. Each run is independent - no accumulation!
"""

import json
import sys

# Ensure local ifckit is on path (for development)
pkg_path = '/Users/Mauc/L140-py-ifckit'
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

from ifckit.json_build import build

_project_name = project_name if project_name else "GH Project"
_author = author if author else "GH"
_unit = unit.upper() if unit else "MILLIMETRE"

out = ""

if not json_input:
    out = "ERROR: no JSON input."
elif not ifc_output:
    out = "ERROR: ifc_output is empty."
elif not run_export:
    try:
        data = json.loads(json_input)
        total = sum(len(elements) for elements in data.get("storeys", {}).values())
        out = f"Model has {total} elements. Set run_export=True to export to:\n  {ifc_output}"
    except json.JSONDecodeError as exc:
        out = f"ERROR: Invalid JSON: {exc}"
else:
    try:
        data = json.loads(json_input)

        project_json = {
            "ifc_version": "IFC4",
            "project": {"name": _project_name, "author": _author},
            "unit": _unit,
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Building",
                    "storeys": [
                        {
                            "name": storey_name,
                            "elevation": 0.0,
                            "elements": [
                                json.loads(elem_json) if isinstance(elem_json, str) else elem_json
                                for elem_json in elements
                            ]
                        }
                        for storey_name, elements in data.get("storeys", {}).items()
                    ]
                }
            ],
        }

        build(project_json, ifc_output)
        out = f"Exported to:\n  {ifc_output}"

    except Exception as exc:
        out = f"EXPORT FAILED: {exc}"