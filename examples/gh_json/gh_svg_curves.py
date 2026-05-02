"""
gh_svg_curves.py  —  GH Script component: "IFC → SVG Curves + Hatches"
=======================================================================

Generates 2-D section drawings from an IFC model (via ifcopenshell.draw),
parses the SVG into Rhino curves and hatches, and places them in the active
Rhino document on a structured layer hierarchy.

Each drawing is defined by an IfcAnnotation[ObjectType="DRAWING"] in the IFC
file, carrying an explicit section plane (origin, x_axis, z_axis).

Layer structure in Rhino::

    IFC-SVG
     └── <drawing name>
          ├── cut / IfcWall          ← section-cut curves
          ├── cut_hatch / IfcWall    ← filled hatches (IFC material colour)
          ├── projection / IfcWall   ← below-cut projection curves
          └── projection_hatch / IfcWall

Component inputs
----------------
json_input     : str   — JSON string from Collector (same as gh_export_json).
project_name   : str   — IFC project name (default "GH Project").
author         : str   — Author stored in IFC header (default "GH").
unit           : str   — "METRE" or "MILLIMETRE" (default MILLIMETRE).
run            : bool  — Set True to execute (prevents accidental re-runs).
ifc_path       : str   — Optional: path to an existing .ifc file.  When
                         provided, json_input is ignored and the file is
                         imported directly.
hlr_poly       : bool  — Use polygonal HLR (default True, faster, same as
                         Bonsai).  Set False for exact BREP HLR (slower,
                         more precise section curves).
mesher_defl    : float — OCC mesher linear deflection in metres (default
                         None = ifcopenshell default ~0.001).  Set to 0.01
                         for ~4× speedup on curved profiles at the cost of
                         slightly coarser tessellation.

Component outputs
-----------------
out  : str  — Status message (curve count, hatch count, or error).

Workflow
--------
1.  Wire Collector json_out → json_input  (or set ifc_path directly).
2.  Leave run=False while wiring to avoid repeated imports.
3.  Set run=True  → curves and hatches appear in Rhino viewport.
4.  Each run replaces the previous IFC-SVG objects (clear=True).
"""

import os
import sys
import importlib

# ---------------------------------------------------------------------------
# Path setup — identical to gh_export_json.py
# ---------------------------------------------------------------------------
_fallback_path = r'/Users/Mauc/L140-py-ifckit'
pkg_path = os.environ.get('IFCKIT_PATH', _fallback_path)
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

# Force reload so Rhino picks up code changes without restarting.
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
import ifckit.validator
import ifckit.json_build

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
importlib.reload(ifckit.validator)
importlib.reload(ifckit.json_build)
importlib.reload(ifckit)

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
