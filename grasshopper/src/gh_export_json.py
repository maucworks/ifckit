"""
gh_export_json.py  —  GH Script component: "ifckit Export IFC"
===============================================================

@component  nickname:"ifckit Export IFC"
@group "Export"
@input  json_input   : str  item — Full IFC project JSON from Build JSON node
@input  ifc_output   : str  item — Absolute path for the output .ifc file (optional)
@input  run_export   : bool item — Set True to write the IFC file
@input  run_preview  : bool item — Set True to import meshes into Rhino
@input  mesh_quality : str  item — Preview tessellation quality (default "default")
@input  sticky_key   : str  item — sc.sticky key (default "ifckit_model")
@output out         : str item — Status message
@output model_ready : int item — Increments on every successful build

Builds an IFC model from JSON, optionally exports to file and/or previews
meshes in Rhino, and stores the model in sc.sticky for downstream drawing nodes.
"""

import json

from ifckit.json_build import build

import scriptcontext as sc

_quality    = mesh_quality if mesh_quality else "default"
_sticky_key = sticky_key   if sticky_key   else "ifckit_model"
_ver_key    = _sticky_key + "_version"

out         = ""
model_ready = sc.sticky.get(_ver_key, 0)  # expose current version even when idle

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
        data  = json.loads(json_input)
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

        # Store model in sticky for drawing nodes.
        sc.sticky[_sticky_key] = model
        sc.sticky[_ver_key]    = sc.sticky.get(_ver_key, 0) + 1
        model_ready            = sc.sticky[_ver_key]
        messages.append(f"Model stored (version {model_ready}).")

        out = "\n".join(messages)

    except Exception as exc:
        import traceback
        out = f"FAILED: {exc}\n{traceback.format_exc()}"

print(out)
