"""
gh_import_ifc.py — GH Script: "Import IFC to Rhino"
======================================================

Import IFC geometry as meshes with smart update by GUID.

Layer hierarchy mirrors IFC spatial structure::

    IFC
     └── Site: Site A
          └── Building: Building 1
               └── Storey: Ground Floor
                    └── Walls > [elements]
                    └── Beams > [elements]

Inputs
------
ifc_path : str  — Path to IFC file (.ifc)
clear    : bool — Clear existing before import (default: False)
delete   : bool — Delete removed elements (default: False)
quality  : str  — Mesh quality: superfine/fine/default/coarse/supercoarse
run      : bool — Set True to trigger import

Outputs
-------
out     : str — Status message
count   : int — Number of elements imported
"""

import importlib
import ifckit.rhino_import
importlib.reload(ifckit.rhino_import)

from ifckit.rhino_import import IfcMeshImporter

count = 0

if not ifc_path:
    out = "No IFC file"
elif not run:
    out = f"Ready. Set run=True to import:\n  {ifc_path}"
else:
    q = (quality or "default").strip().lower()
    importer = IfcMeshImporter(
        layer_root="IFC",
        clear_on_import=bool(clear),
        delete_removed=bool(delete),
        mesh_quality=q,
    )
    count = importer.import_file(ifc_path)
    out = f"Imported {count} elements from:\n  {ifc_path}"

print(out)
