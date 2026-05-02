"""
gh_export_json.py — GH Script: "Export / Preview IFC"
======================================================

Stateless: takes a full IFC project JSON (from Build JSON node),
exports to file and/or previews in the active Rhino document.

Flow:  [Build JSON json_out] ──→ [Export/Preview]

Component inputs
----------------
json_input     : str  — Full IFC project JSON from Build JSON node.
ifc_output     : str  — Absolute path for the output .ifc file (optional).
run_export     : bool — Set True to write the IFC file (requires ifc_output).
run_preview    : bool — Set True to import meshes into Rhino.
run_svg        : bool — Set True to import SVG curves + hatches into Rhino (slow).
mesh_quality   : str  — Preview tessellation quality
                          (superfine/fine/default/coarse/supercoarse).

Component outputs
-----------------
out  : str  — Status message (element count, file path, or error).
"""

import json
import sys
import importlib

# Ensure local ifckit is on path (for development).
# Set the IFCKIT_PATH environment variable or edit this fallback to your checkout.
import os
_fallback_path = r'/Users/Mauc/L140-py-ifckit'
pkg_path = os.environ.get('IFCKIT_PATH', _fallback_path)
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

import ifckit
import ifckit.geometry
import ifckit.elements
import ifckit.builders
import ifckit.builders._geom
import ifckit.builders.base
import ifckit.builders.extruded
import ifckit.builders.wall
import ifckit.builders.slab
import ifckit.builders.beam_factory
import ifckit.builders.revolved_beam
import ifckit.builders.bridge
import ifckit.rhinokit
import ifckit.rhino_import
import ifckit.model
import ifckit.validator
import ifckit.json_build

# Reload in dependency order (leaves before packages that import them)
importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.builders._geom)
importlib.reload(ifckit.builders.base)
importlib.reload(ifckit.builders.extruded)
importlib.reload(ifckit.builders.wall)
importlib.reload(ifckit.builders.slab)
importlib.reload(ifckit.builders.beam_factory)
importlib.reload(ifckit.builders.revolved_beam)
importlib.reload(ifckit.builders.bridge)
importlib.reload(ifckit.builders)
importlib.reload(ifckit.rhinokit)
importlib.reload(ifckit.rhino_import)
importlib.reload(ifckit.model)
importlib.reload(ifckit.validator)
importlib.reload(ifckit.json_build)
importlib.reload(ifckit)

from ifckit.json_build import build

_quality       = mesh_quality  if mesh_quality  else "default"

out = ""

if not json_input:
    out = "ERROR: no JSON input."
elif not run_export and not run_preview:
    try:
        data = json.loads(json_input)
        total = sum(
            len(s.get("elements", []))
            for b in data.get("buildings", [])
            for s in b.get("storeys", [])
        )
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
        model = build(data)
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

        if run_svg:
            curve_preview = model.preview_rhino_curves(clear=True)
            messages.append(f"Curves:  {curve_preview['curves']}")
            messages.append(f"Hatches: {curve_preview['hatches']}")

        out = "\n".join(messages)

    except Exception as exc:
        out = f"FAILED: {exc}"

print(out)
