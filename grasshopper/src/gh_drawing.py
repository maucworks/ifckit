"""
gh_drawing.py  —  GH Script component: "ifckit Drawing"
========================================================

@component  nickname:"ifckit Drawing"
@group "Drawing"
@input  model_ready   : int   item — From Export node; confirms model version
@input  drawing_name  : str   item — Name of the IfcAnnotation drawing to generate
@input  run           : bool  item — Set True to generate
@input  hlr_poly      : bool  item — Use polygonal HLR (default True)
@input  mesher_defl   : float item — OCC mesher linear deflection in metres (optional)
@input  hatch_pattern : str   item — Fallback hatch pattern (default "Solid")
@input  clear         : bool  item — Remove existing curves/hatches first (default True)
@input  sticky_key    : str   item — sc.sticky key to read model from (default "ifckit_model")
@input  dest_plane    : plane item — Rhino Plane for drawing placement (optional)
@output out : str item — Status message

Imports one named IFC drawing (section plane + projection) into the active
Rhino document as curves and hatches.
"""


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
