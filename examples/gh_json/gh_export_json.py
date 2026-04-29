"""
gh_export_json.py  —  GH Script component: "Export IFC from JSON"
===================================================================

Stateless component: builds IFC from JSON, optionally writes to file
and/or previews in the active Rhino document.

Each run is independent - no state, no accumulation.

Component inputs
----------------
json_input     : str  — JSON string from Collector.
project_name   : str  — IFC project name (default "GH Project").
author         : str  — Author string stored in IFC header (default "GH").
unit           : str  — "METRE" or "MILLIMETRE" (default MILLIMETRE).
ifc_output     : str  — Absolute path for the output IFC file (optional).
run_export     : bool — Set True to write the IFC file (requires ifc_output).
run_preview    : bool — Set True to import meshes into the active Rhino doc.
mesh_quality   : str  — Preview tessellation quality
                          (superfine/fine/default/coarse/supercoarse).

Component outputs
-----------------
out  : str  — Status message (element count, file path, or error).

Workflow
--------
1. Wire Collector json_out to json_input here
2. Set run_export=False / run_preview=False while testing - see element count
3. Set run_preview=True  → meshes appear in Rhino viewport (no file needed)
4. Set run_export=True   → IFC file is also written to ifc_output path
5. Each run is independent - no accumulation!
"""

import json
import os
import sys
import importlib

# Ensure local ifckit is on path (for development).
# Set the IFCKIT_PATH environment variable or edit this fallback to your checkout.
_fallback_path = r'/Users/Mauc/L140-py-ifckit'
pkg_path = os.environ.get('IFCKIT_PATH', _fallback_path)
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

# Rhino/Grasshopper: force reload to pick up code changes and avoid
# class-identity mismatches that break isinstance() checks.
# NOTE: Must import and reload submodules explicitly (reload() doesn't cascade).
import ifckit
import ifckit.json_build
import ifckit.builders
import ifckit.builders.swept  # <-- MUST import explicitly
import ifckit.elements
import ifckit.elements.swept
import ifckit.geometry
import ifckit.validator

# Reload in dependency order (leaves before roots)
importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.elements.swept)
importlib.reload(ifckit.builders.swept)  # <-- MUST reload explicitly
importlib.reload(ifckit.builders)
importlib.reload(ifckit.validator)
importlib.reload(ifckit.json_build)
importlib.reload(ifckit)

from ifckit.json_build import build

_project_name = project_name if project_name else "GH Project"
_author = author if author else "GH"
_unit = unit.upper() if unit else "MILLIMETRE"
_quality = mesh_quality if mesh_quality else "default"

out = ""

if not json_input:
    out = "ERROR: no JSON input."
elif not run_export and not run_preview:
    try:
        data = json.loads(json_input)
        total = sum(
            len(storey.get("elements", []))
            for bldg in data.get("buildings", [])
            for storey in bldg.get("storeys", [])
        )
        # also count flat "storeys" key produced by gh_collector.py
        if not data.get("buildings") and "storeys" in data:
            total = sum(len(elems) for elems in data["storeys"].values())
        lines = [f"Model has {total} elements."]
        if ifc_output:
            lines.append(f"Set run_export=True to export to:\n  {ifc_output}")
        lines.append("Set run_preview=True to preview in Rhino.")
        out = "\n".join(lines)
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

        model = build(project_json)
        messages = []

        if run_export:
            if not ifc_output:
                messages.append("EXPORT SKIPPED: ifc_output is empty.")
            else:
                model.save(ifc_output)
                messages.append(f"Exported to:\n  {ifc_output}")

        if run_preview:
            count = model.preview_rhino(mesh_quality=_quality)
            messages.append(f"Previewing {count} elements in Rhino.")

        out = "\n".join(messages)

    except Exception as exc:
        out = f"FAILED: {exc}"

print(out)
