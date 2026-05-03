"""
gh_svg_curves.py  —  GH Script component: "ifckit SVG Curves"
==============================================================

@component  nickname:"ifckit SVG Curves"
@group "Drawing"
@input  json_input   : str   item — JSON string from Build JSON node (or leave empty)
@input  project_name : str   item — IFC project name (default "GH Project")
@input  author       : str   item — Author (default "GH")
@input  unit         : str   item — "METRE" or "MILLIMETRE" (default "MILLIMETRE")
@input  run          : bool  item — Set True to execute
@input  ifc_path     : str   item — Path to existing .ifc (overrides json_input)
@input  hlr_poly     : bool  item — Use polygonal HLR (default True)
@input  mesher_defl  : float item — OCC mesher deflection in metres (optional)
@output out : str item — Status message

Generates 2-D section drawings from an IFC model via ifcopenshell.draw,
parses the SVG and places curves + hatches on structured Rhino layers.
"""


# ---------------------------------------------------------------------------
# Resolve inputs with sensible defaults
# ---------------------------------------------------------------------------
import json

_project_name  = project_name   if project_name   else "GH Project"
_author        = author         if author         else "GH"
_unit          = unit.upper()   if unit           else "MILLIMETRE"
_ifc_path      = ifc_path       if ifc_path       else ""
_hlr_poly      = hlr_poly       if hlr_poly is not None else True
_mesher_defl   = float(mesher_defl) if mesher_defl else None

out = ""

if not run:
    out = "Set run=True to import SVG curves into Rhino."

elif _ifc_path:
    # -----------------------------------------------------------------------
    # Direct IFC file import — bypass JSON build
    # -----------------------------------------------------------------------
    try:
        from ifckit.rhino_import import IfcSvgImporter

        importer = IfcSvgImporter()
        importer.clear()
        result = importer.import_file(
            _ifc_path,
            hlr_poly=_hlr_poly,
            mesher_deflection=_mesher_defl,
        )
        out = (
            f"Imported from file:\n  {_ifc_path}\n"
            f"Curves:  {result['curves']}\n"
            f"Hatches: {result['hatches']}"
        )
    except Exception as exc:
        import traceback
        out = f"FAILED: {exc}\n{traceback.format_exc()}"

elif json_input:
    # -----------------------------------------------------------------------
    # Build IFC from JSON then import
    # -----------------------------------------------------------------------
    try:
        from ifckit.json_build import build

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
                                json.loads(elem_json)
                                if isinstance(elem_json, str)
                                else elem_json
                                for elem_json in elements
                            ],
                        }
                        for storey_name, elements in data.get("storeys", {}).items()
                    ],
                }
            ],
        }

        model = build(project_json)
        result = model.preview_rhino_curves(
            clear=True,
            hlr_poly=_hlr_poly,
            mesher_deflection=_mesher_defl,
        )
        out = (
            f"Curves:  {result['curves']}\n"
            f"Hatches: {result['hatches']}"
        )

    except Exception as exc:
        import traceback
        out = f"FAILED: {exc}\n{traceback.format_exc()}"

else:
    out = "ERROR: provide json_input or ifc_path."

print(out)
