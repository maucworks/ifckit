"""
gh_preview_element.py  —  GH Script component: "ifckit Preview Element"
=========================================================================

@component  nickname:"ifckit Preview Element"
@group "Preview"
@input  json_in    : str  list  — Collector storey JSON(s) or single element JSON(s)
@input  unit       : str  item  — Length unit: "MILLIMETRE" (default) or "METRE"
@input  skip_voids : bool item  — If True, hide opening void geometry (default False)
@output out      : str  item — Status message
@output preview  : geometry list — Ephemeral meshes (never added to Rhino doc)

All inputs are merged into one project dict before building, so that
window_types / door_types defined in a storey bundle are available to
openings that reference them via type_ref.
"""

from __future__ import annotations

import traceback

# ---------------------------------------------------------------------------
# Reload (development only — harmless in production)
# ---------------------------------------------------------------------------
try:
    from ifckit.rhinokit import reload_all
    reload_all()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
preview = []
out = ""

try:
    from ifckit.preview import build_preview_meshes_merged

    inputs = json_in if isinstance(json_in, list) else [json_in]
    inputs = [s for s in inputs if s]
    _unit = str(unit).upper() if unit else "MILLIMETRE"
    _skip = bool(skip_voids) if skip_voids is not None else False

    if not inputs:
        out = "No input"
    else:
        meshes = build_preview_meshes_merged(inputs, unit=_unit, skip_voids=_skip)
        preview = meshes
        out = f"{len(meshes)} mesh(es)"

except Exception as exc:
    out = f"ERROR: {exc}\n{traceback.format_exc()}"
