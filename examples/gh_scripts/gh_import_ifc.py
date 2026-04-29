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
ifc_path : str — Path to IFC file (.ifc)
clear    : bool — Clear existing before import (default: False)
delete   : bool — Delete removed elements (default: False)

Outputs
-------
out     : str — Status message
count   : int — Number of elements imported

Usage
-----
1. Connect IFC file path to ifc_path
2. Optional: toggle clear to clear existing meshes first
3. Optional: toggle delete to remove meshes no longer in IFC
4. Read count to verify import
"""

import scriptcontext as sc
import Rhino

if not ifc_path:
    out = "No IFC file"
    count = 0
else:
    try:
        from ifckit.rhino_import import IfcMeshImporter
    except ImportError as e:
        out = f"Import failed: {e}"
        count = 0
    else:
        importer = IfcMeshImporter(
            layer_root="IFC",
            clear_on_import=bool(clear),
            use_active_doc=True
        )

        if delete:
            importer.set_delete_removed(True)

        count = importer.import_file(ifc_path)
        out = f"Imported {count} elements"

print(out)