# IFC Mesh Import Implementation Plan

## Overview

Import IFC geometry into Rhino as meshes with intelligent update by GUID.

```
┌─────────────┐    export()    ┌─────────┐    import()    ┌──────────┐
│  IfcModel   │ ──────────────►│   IFC   │ ──────────────►│  Rhino   │
└─────────────┘                └─────────┘    (meshes)    └──────────┘
```

## Layer Hierarchy (Option B)

```
IFC
 └── Site: Site A
      └── Building: Building 1
           └── Storey: Ground Floor
                └── Walls > Wall_Guid1, Wall_Guid2
                └── Beams > Beam_Guid1
                └── Slabs > ...
```

## Implementation Details

### Class: IfcMeshImporter

Location: `ifckit/rhino_import.py`

```python
class IfcMeshImporter:
    """
    Import IFC geometry into Rhino as meshes.

    Features:
    - Layer hierarchy mirrors IFC spatial structure
    - Smart update by GUID (updates changed, adds new)
    - Optional removal of deleted elements
    """

    def __init__(
        self,
        doc,                    # Rhino document (sc.doc)
        layer_root: str = "IFC",  # Root layer name
        clear_on_import: bool = False  # Clear existing before import
    ):
        self.doc = doc
        self.layer_root = layer_root
        self.clear_on_import = clear_on_import
        self._guid_to_rhino_guid: dict[str, Guid] = {}
        self._layer_cache: dict[str, int] = {}  # path -> layer index
```

### Public Methods

```python
def import_file(self, ifc_path: str) -> int:
    """
    Import IFC file into Rhino.

    Args:
        ifc_path: Path to IFC file (.ifc, .ifcxml)

    Returns:
        Number of elements imported
    """

def import_model(self, ifc_model) -> int:
    """
    Import existing IfcModel into Rhino.

    Args:
        ifc_model: ifckit.IfcModel or ifcopenshell.file

    Returns:
        Number of elements imported
    """

def clear(self) -> int:
    """
    Remove all IFC-imported meshes and layers.

    Returns:
        Number of meshes removed
    """

def set_delete_removed(self, enabled: bool) -> None:
    """
    Enable/disable deletion of elements no longer in IFC.

    Args:
        enabled: If True, remove meshes whose GUID is no longer in IFC
    """
```

### Private Methods

```python
def _get_ifc_hierarchy(self, ifc_file) -> dict:
    """
    Parse IFC spatial hierarchy.

    Returns:
        {(site_name, building_name, storey_name): [elements]}
    """

def _iterate_geometry(self, ifc_file) -> Iterator[tuple]:
    """
    Iterate all products with geometry.

    Yields:
        (element, guid, mesh_data) tuples
    """

def _create_rhino_mesh(self, verts: list, faces: list) -> Rhino.Geometry.Mesh:
    """
    Create Rhino mesh from vertex/face data.
    """

def _ensure_layer(self, path: str) -> int:
    """
    Ensure layer hierarchy exists.

    Args:
        path: "IFC::Site A::Building 1::Ground Floor::Walls"

    Returns:
        Layer index
    """

def _get_element_type_layer(self, ifc_class: str) -> str:
    """
    Map IFC class to layer name.

    IfcWall -> "Walls"
    IfcBeam -> "Beams"
    IfcSlab -> "Slabs"
    """

def _update_mesh(self, rhino_guid: Guid, new_verts: list, new_faces: list) -> None:
    """
    Update existing mesh geometry (smart update).
    """

def _add_mesh(self, mesh, layer_index: int, ifc_guid: str, element_name: str) -> Guid:
    """
    Add new mesh to document.
    """
```

### Key Data Structures

**GUID Tracking:**
```python
self._guid_to_rhino_guid = {
    "3$s2x...": uuid1,  # IFC GUID -> Rhino Guid
}
```

**Layer Path Cache:**
```python
self._layer_cache = {
    "IFC::Site A::Building 1::Ground Floor::Walls": 5,
}
```

### IFC Element Type Mapping

```python
ELEMENT_TYPE_LAYERS = {
    "IfcWall": "Walls",
    "IfcWallStandardCase": "Walls",
    "IfcBeam": "Beams",
    "IfcBeamStandardCase": "Beams",
    "IfcColumn": "Columns",
    "IfcColumnStandardCase": "Columns",
    "IfcSlab": "Slabs",
    "IfcFloorSlab": "Slabs",
    "IfcRoof": "Roofs",
    "IfcDoor": "Doors",
    "IfcWindow": "Windows",
    "IfcPlate": "Plates",
    "IfcMember": "Members",
}
```

### Smart Update Logic

```python
def _process_element(self, element, guid, verts, faces, hierarchy_key):
    if guid in self._guid_to_rhino_guid:
        # Update existing
        rhino_guid = self._guid_to_rhino_guid[guid]
        obj = self.doc.Objects.Find(rhino_guid)
        if obj:
            self._update_mesh(rhino_guid, verts, faces)
    else:
        # Add new
        mesh = self._create_rhino_mesh(verts, faces)
        new_guid = self._add_mesh(mesh, layer_index, guid, name)
        self._guid_to_rhino_guid[guid] = new_guid
```

### Geometry Extraction

```python
def _iterate_geometry(self, ifc_file):
    import ifcopenshell.geom as ic_geom

    settings = ic_geom.settings()
    settings.set(ic_geom.settings.USE_WORLD_COORDS, True)
    settings.set(ic_geom.settings.APPLY_DEFAULT_MATERIALS, True)

    iterator = ic_geom.iterator(settings, ifc_file)

    if iterator.initialize():
        while True:
            shape = iterator.get()
            element = ifc_file.by_guid(shape.guid)

            # verts: flattened list [x,y,z,x,y,z,...]
            verts = list(shape.geometry.verts)
            # faces: flattened list [i,j,k,i,j,k,...]
            faces = list(shape.geometry.faces)

            yield (element, shape.guid, verts, faces)

            if not iterator.next():
                break
```

### Rhino Mesh Creation

```python
def _create_rhino_mesh(self, verts: list, faces: list) -> Rhino.Geometry.Mesh:
    mesh = Rhino.Geometry.Mesh()

    # Add vertices (flattened to triplets)
    for i in range(0, len(verts), 3):
        mesh.Vertices.Add(verts[i], verts[i+1], verts[i+2])

    # Add faces (triangulate)
    for i in range(0, len(faces), 3):
        mesh.Faces.AddFace(faces[i], faces[i+1], faces[i+2])

    mesh.Normals.ComputeNormals()
    mesh.Compact()

    return mesh
```

### Layer Creation

```python
def _ensure_layer(self, path: str) -> int:
    if path in self._layer_cache:
        return self._layer_cache[path]

    parts = path.split("::")
    current_path = ""

    for i, part in enumerate(parts):
        current_path = current_path + "::" + part if current_path else part

        # Check if exists
        index = self.doc.Layers.FindByFullName(current_path, -1)
        if index >= 0:
            self._layer_cache[path] = index
            continue

        # Create
        layer = Rhino.DocObjects.Layer()
        layer.Name = part

        if i > 0:
            parent_path = "::".join(parts[:-1])
            parent_index = self._layer_cache.get(parent_path, -1)
            if parent_index >= 0:
                parent_layer = self.doc.Layers[parent_index]
                layer.ParentLayerId = parent_layer.Id

        index = self.doc.Layers.Add(layer)
        self._layer_cache[current_path] = index

    return self._layer_cache[path]
```

## Export to __init__.py

```python
# Add to imports
from ifckit.rhino_import import IfcMeshImporter

# Add to __all__
__all__ = [
    # ... existing ...
    "IfcMeshImporter",
]
```

## GH Component Usage

```python
"""
gh_import_ifc.py — GH Script: "Import IFC to Rhino"
====================================================

Inputs
------
ifc_path : str — Path to IFC file
clear    : bool — Clear existing before import (default: False)
delete   : bool — Delete removed elements (default: False)

Output
------
out     : str — Status message
count   : int — Number of elements imported
"""

import scriptcontext as sc
import ifckit.rhino_import as rim

if not ifc_path:
    out = "No IFC file"
    count = 0
else:
    importer = rim.IfcMeshImporter(
        doc=sc.doc,
        layer_root="IFC",
        clear_on_import=bool(clear)
    )
    if delete:
        importer.set_delete_removed(True)

    count = importer.import_file(ifc_path)
    out = f"Imported {count} elements"

print(out)
```

## Testing

1. Export IFC from ifckit
2. Import via IfcMeshImporter
3. Modify IFC (add/change/remove elements)
4. Re-import and verify smart update works

## Edge Cases

- IFC elements without geometry (skip)
- IFC elements with multiple meshes (combine or keep separate)
- Materials from IFC (optional: apply to Rhino mesh)
- Nested elements (IfcOpeningElement, IfcVoid)
- IFC4 vs IFC4X3 hierarchy differences