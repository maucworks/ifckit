"""
gh_preview_element.py  —  GH Script component: "ifckit Preview Element"
=========================================================================

@component  nickname:"ifckit Preview Element"
@group "Preview"
@input  json_in  : str  list — Collector storey JSON(s) or single element JSON(s)
@input  unit     : str  item — Length unit of coordinates: "MILLIMETRE" (default) or "METRE"
@output out      : str  item — Status message
@output preview  : geometry list — Ephemeral meshes (never added to Rhino doc)
"""

from __future__ import annotations

import traceback

# ---------------------------------------------------------------------------
# Reload helper (development only — harmless in production)
# ---------------------------------------------------------------------------
try:
    import ifckit.preview  # noqa: F401
    from ifckit.rhinokit import reload_all

    reload_all(__file__)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
preview = []
out = ""

try:
    from ifckit.preview import build_preview_meshes

    inputs = json_in if isinstance(json_in, list) else [json_in]
    inputs = [s for s in inputs if s]
    _unit = str(unit).upper() if unit else "MILLIMETRE"

    if not inputs:
        out = "No input"
    else:
        total_meshes = 0
        errors = []

        for s in inputs:
            try:
                meshes = build_preview_meshes(s, unit=_unit)
                preview.extend(meshes)
                total_meshes += len(meshes)
            except Exception as exc:
                errors.append(str(exc))

        parts = [f"{total_meshes} mesh(es)"]
        if errors:
            parts.append(f"{len(errors)} error(s): {'; '.join(errors)}")
        out = ", ".join(parts)

except Exception as exc:
    out = f"ERROR: {exc}\n{traceback.format_exc()}"
