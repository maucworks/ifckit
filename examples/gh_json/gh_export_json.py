"""
gh_export_json.py — GH Script: "Export / Preview IFC"
======================================================

Builds an IFC model from JSON, optionally exports to file and/or previews
meshes in Rhino, and stores the model in ``sc.sticky`` for downstream
drawing nodes (gh_drawing.py).

Flow:  [Build JSON json_out] ──→ [Export / Preview]
                                       │ model_ready
                                       ▼
                               [Drawing node ×N]

Component inputs
----------------
json_input     : str  — Full IFC project JSON from Build JSON node.
ifc_output     : str  — Absolute path for the output .ifc file (optional).
run_export     : bool — Set True to write the IFC file (requires ifc_output).
run_preview    : bool — Set True to import meshes into Rhino.
mesh_quality   : str  — Preview tessellation quality
                          (superfine/fine/default/coarse/supercoarse).
sticky_key     : str  — sc.sticky key under which the model is stored
                          (default "ifckit_model").  Change only when running
                          multiple independent IFC models side by side.

Component outputs
-----------------
out          : str  — Status message (element count, file path, or error).
model_ready  : int  — Increments on every successful build.  Wire to
                       drawing nodes so they know a new model is available.
                       Does NOT auto-trigger drawing nodes — each drawing
                       node has its own run=True guard.
"""

import json
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit

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
