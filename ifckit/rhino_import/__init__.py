"""
ifckit.rhino_import
===================

Import IFC geometry into Rhino as meshes (``IfcMeshImporter``), as 2-D
curves and hatches derived from an SVG floor-plan view (``IfcSvgImporter``),
or as space fills and annotations (``IfcSpaceImporter``).

Requires: Rhino 8+ with ifcopenshell installed.

Mesh layer hierarchy mirrors IFC spatial structure::

    IFC
     └── Site: Site A
          └── Building: Building 1
               └── Storey: Ground Floor
                    └── Walls > Wall_Guid1, Wall_Guid2
                    └── Beams > Beam_Guid1

SVG layer hierarchy::

    IFC-SVG
     └── Ground Floor
          ├── cut            ← section-cut curves  (IfcWall, IfcSlab, …)
          ├── cut_hatch      ← section-cut hatches (filled solid, IFC material colour)
          ├── projection     ← below-cut projection curves
          └── projection_hatch

Usage::

    import ifckit.rhino_import as rim
    import scriptcontext as sc

    # mesh importer (existing)
    importer = rim.IfcMeshImporter(sc.doc)
    importer.import_file("/path/to/model.ifc")

    # SVG curve + hatch importer (new)
        svg_imp = rim.IfcSvgImporter(sc.doc)
    result = svg_imp.import_file("/path/to/model.ifc")
    print(result)  # {"curves": 42, "hatches": 18}
"""

from ifckit.rhino_import._helpers import MESH_QUALITY
from ifckit.rhino_import.ifc_mesh_importer import IfcMeshImporter
from ifckit.rhino_import.ifc_space_importer import IfcSpaceImporter
from ifckit.rhino_import.ifc_svg_importer import BONSAI_HATCH_MAP, IfcSvgImporter

__all__ = [
    "BONSAI_HATCH_MAP",
    "IfcMeshImporter",
    "IfcSpaceImporter",
    "IfcSvgImporter",
    "MESH_QUALITY",
]
