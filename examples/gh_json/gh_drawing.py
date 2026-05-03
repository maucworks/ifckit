"""
gh_drawing.py — GH Script: "Generate Drawing"
==============================================

Imports one named IFC drawing (section plane + projection) into the active
Rhino document as curves and hatches.  The model is read from ``sc.sticky``
as stored by gh_export_json.py.

Each run replaces only the curves/hatches for the requested drawing (when
``clear=True``), leaving all other drawings untouched.

Flow:  [Export/Preview model_ready] ──→ [Generate Drawing ×N]

Wire the same ``model_ready`` output to all drawing nodes.  Each node is
independent: set its own ``run=True`` when you want to (re)generate that
particular drawing.

Component inputs
----------------
model_ready   : int   — From Export node.  Shown in status to confirm which
                         model version is loaded.  Does NOT auto-run this node.
drawing_name  : str   — Exact name of the IfcAnnotation[ObjectType=DRAWING]
                         to generate (e.g. "Ground Floor Plan").
run           : bool  — Set True to generate the drawing.  Generation can
                         take 10–120 s depending on model complexity.
hlr_poly      : bool  — Use polygonal HLR (default True, same as Bonsai).
                         Set False for exact BREP HLR (slower, more precise).
mesher_defl   : float — OCC mesher linear deflection in metres (default None
                         = ifcopenshell default ~0.001 m).  Try 0.01 for
                         ~4× speedup on curved profiles.
hatch_pattern : str   — Fallback Rhino hatch pattern name for elements that
                         do not have EPset_IfcKit.HatchPattern set
                         (default "Solid").
clear         : bool  — If True (default), remove existing curves/hatches for
                         this drawing before regenerating.
sticky_key    : str   — sc.sticky key to read the model from
                         (default "ifckit_model").  Must match the key used
                         in gh_export_json.py.
dest_plane    : Plane — Rhino Plane onto which the drawing is placed using
                         PlaneToPlane (scale 1:1).  Leave unconnected to keep
                         the drawing on its section plane in world space.

Component outputs
-----------------
out  : str  — Status message (curve count, hatch count, or error).
"""

import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit

from ifckit.rhino_import import IfcSvgImporter

import scriptcontext as sc

# ---------------------------------------------------------------------------
# Resolve inputs
# ---------------------------------------------------------------------------
_sticky_key    = sticky_key    if sticky_key    else "ifckit_model"
_drawing_name  = drawing_name  if drawing_name  else ""
_hlr_poly      = hlr_poly      if hlr_poly is not None else True
_mesher_defl   = float(mesher_defl) if mesher_defl else None
_hatch_pattern = hatch_pattern if hatch_pattern else "Solid"
_clear         = clear         if clear is not None else True
_model_ready   = model_ready   if model_ready is not None else 0

# Destination plane — None means keep drawing on section plane.
_dest_plane = dest_plane if dest_plane is not None else None

out = ""

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
if not _drawing_name:
    out = "Set drawing_name to the exact name of the drawing to generate."

elif not run:
    model = sc.sticky.get(_sticky_key)
    if model is None:
        out = (
            f"No model in sc.sticky[{_sticky_key!r}].\n"
            "Run the Export node first, then set run=True here."
        )
    else:
        lines = [
            f"Model ready (version {_model_ready}).",
            f"Drawing: {_drawing_name!r}",
        ]
        if _dest_plane is not None:
            lines.append(f"Destination plane: {_dest_plane.Origin}")
        lines.append("Set run=True to generate.")
        out = "\n".join(lines)

else:
    # -----------------------------------------------------------------------
    # Generate
    # -----------------------------------------------------------------------
    model = sc.sticky.get(_sticky_key)

    if model is None:
        out = (
            f"ERROR: no model found in sc.sticky[{_sticky_key!r}].\n"
            "Run the Export node first."
        )
    else:
        try:
            importer = IfcSvgImporter(hatch_pattern=_hatch_pattern)

            if _clear:
                removed = importer.clear_drawing(_drawing_name)
                clear_msg = f"Cleared {removed} existing objects."
            else:
                clear_msg = ""

            result = importer.import_model(
                model,
                hlr_poly=_hlr_poly,
                mesher_deflection=_mesher_defl,
                drawing_filter=_drawing_name,
                destination_plane=_dest_plane,
            )

            lines = [
                f"Drawing:  {_drawing_name!r}",
                f"Curves:   {result['curves']}",
                f"Hatches:  {result['hatches']}",
            ]
            if _dest_plane is not None:
                lines.append(f"Placed on destination plane: {_dest_plane.Origin}")
            if clear_msg:
                lines.append(clear_msg)
            out = "\n".join(lines)

        except Exception as exc:
            import traceback
            out = f"FAILED: {exc}\n{traceback.format_exc()}"

print(out)
