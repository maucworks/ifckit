"""
gh_spaces.py  —  GH Script component: "ifckit Spaces"
======================================================

@component  nickname:"ifckit Spaces"  panel:"Import"
@input  ifc_path      : str   item — Absolute path to the .ifc file
@input  run           : bool  item — Set True to import
@input  layer_root    : str   item — Root layer name (default "IFC-Spaces")
@input  hatch_pattern : str   item — Rhino hatch pattern for fills (default "Solid")
@input  import_fp     : bool  item — Draw 2-D footprint curves (default True)
@input  import_hatch  : bool  item — Draw hatch fills (default True)
@input  import_ann    : bool  item — Draw TextDot labels (default True)
@input  import_mesh   : bool  item — Tessellate 3-D bodies (default False)
@input  mesh_quality  : str   item — Tessellation quality preset (default "default")
@input  clear         : bool  item — Clear existing objects first (default True)
@output out : str item — Status message

Reads IfcSpace entities from an IFC file and draws footprint curves,
hatches, annotations and/or 3-D mesh bodies in the active Rhino document.
"""

import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit

from ifckit.rhino_import import IfcSpaceImporter

import scriptcontext as sc

# ---------------------------------------------------------------------------
# Resolve inputs
# ---------------------------------------------------------------------------
_ifc_path      = ifc_path      if ifc_path      else ""
_layer_root    = layer_root    if layer_root    else "IFC-Spaces"
_hatch_pattern = hatch_pattern if hatch_pattern else "Solid"
_import_fp     = import_fp     if import_fp  is not None else True
_import_hatch  = import_hatch  if import_hatch is not None else True
_import_ann    = import_ann    if import_ann  is not None else True
_import_mesh   = import_mesh   if import_mesh is not None else False
_mesh_quality  = mesh_quality  if mesh_quality else "default"
_clear         = clear         if clear is not None else True

out = ""

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
if not _ifc_path:
    out = "Set ifc_path to the absolute path of the IFC file."

elif not run:
    out = (
        f"IFC file: {_ifc_path}\n"
        f"Layer root: {_layer_root!r}\n"
        f"Import: footprint={_import_fp}, hatch={_import_hatch}, "
        f"annotation={_import_ann}, mesh={_import_mesh}\n"
        "Set run=True to import."
    )

else:
    try:
        importer = IfcSpaceImporter(
            layer_root=_layer_root,
            hatch_pattern=_hatch_pattern,
            import_footprint=_import_fp,
            import_hatch=_import_hatch,
            import_annotation=_import_ann,
            import_mesh=_import_mesh,
            mesh_quality=_mesh_quality,
        )

        if _clear:
            removed = importer.clear()
            clear_msg = f"Cleared {removed} existing objects."
        else:
            clear_msg = ""

        result = importer.import_file(_ifc_path)

        lines = [
            f"Spaces:      {result['spaces']}",
            f"Footprints:  {result['footprints']}",
            f"Hatches:     {result['hatches']}",
            f"Annotations: {result['annotations']}",
            f"Meshes:      {result['meshes']}",
        ]
        if clear_msg:
            lines.append(clear_msg)
        out = "\n".join(lines)

    except Exception as exc:
        import traceback
        out = f"FAILED: {exc}\n{traceback.format_exc()}"

print(out)
