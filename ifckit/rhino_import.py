"""
ifckit.rhino_import
===================

Import IFC geometry into Rhino as meshes with smart update by GUID.

Requires: Rhino 8+ with ifcopenshell installed.

Layer hierarchy mirrors IFC spatial structure::

    IFC
     └── Site: Site A
          └── Building: Building 1
               └── Storey: Ground Floor
                    └── Walls > Wall_Guid1, Wall_Guid2
                    └── Beams > Beam_Guid1

Usage::

    import ifckit.rhino_import as rim
    import scriptcontext as sc

    importer = rim.IfcMeshImporter(sc.doc)
    importer.import_file("/path/to/model.ifc")

    # Re-import after IFC changes (smart update)
    importer.import_file("/path/to/model.ifc")
"""

from __future__ import annotations

from typing import Any, Iterator, Optional


ELEMENT_TYPE_LAYERS: dict[str, str] = {
    "IfcWall": "Walls",
    "IfcWallStandardCase": "Walls",
    "IfcBeam": "Beams",
    "IfcBeamStandardCase": "Beams",
    "IfcColumn": "Columns",
    "IfcColumnStandardCase": "Columns",
    "IfcSlab": "Slabs",
    "IfcFloorSlab": "Slabs",
    "IfcRoof": "Roofs",
    "IfcRoofSlab": "Roofs",
    "IfcDoor": "Doors",
    "IfcWindow": "Windows",
    "IfcPlate": "Plates",
    "IfcMember": "Members",
    "IfcCurtainWall": "CurtainWalls",
    "IfcStair": "Stairs",
    "IfcRamp": "Ramps",
    "IfcBuildingElementProxy": "Proxies",
}


class IfcMeshImporter:
    """
    Import IFC geometry into Rhino as meshes.

    Features:
    - Layer hierarchy mirrors IFC spatial structure (Option B)
    - Smart update by GUID (updates changed, adds new)
    - Optional removal of deleted elements

    Args:
        doc: Rhino document (e.g., sc.doc in GH)
        layer_root: Root layer name (default: "IFC")
        clear_on_import: If True, clear existing IFC meshes before import
    """

    def __init__(
        self,
        doc: Any = None,
        layer_root: str = "IFC",
        clear_on_import: bool = False,
        use_active_doc: bool = True,
    ) -> None:
        if doc is None:
            import Rhino
            self.doc = Rhino.RhinoDoc.ActiveDoc
        elif use_active_doc:
            import Rhino
            self.doc = Rhino.RhinoDoc.ActiveDoc
        else:
            self.doc = doc

        self.layer_root = layer_root
        self.clear_on_import = clear_on_import
        self._guid_to_rhino_guid: dict[str, Any] = {}
        self._layer_cache: dict[str, int] = {}
        self._delete_removed: bool = False

    def import_file(self, ifc_path: str) -> int:
        """
        Import IFC file into Rhino.

        Args:
            ifc_path: Path to IFC file (.ifc, .ifcxml)

        Returns:
            Number of elements imported
        """
        import ifcopenshell

        ifc_file = ifcopenshell.open(ifc_path)
        return self.import_model(ifc_file)

    def import_model(self, ifc_model: Any) -> int:
        """
        Import IFC model into Rhino.

        Args:
            ifc_model: ifckit.IfcModel or ifcopenshell.file

        Returns:
            Number of elements imported
        """
        import ifcopenshell.geom as ic_geom

        if self.clear_on_import:
            self.clear()

        ifc_file = getattr(ifc_model, "ifc_file", ifc_model)

        settings = ic_geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.APPLY_DEFAULT_MATERIALS, True)

        iterator = ic_geom.iterator(settings, ifc_file)

        count = 0

        if not iterator.initialize():
            return 0

        while True:
            shape = iterator.get()
            element = ifc_file.by_guid(shape.guid)

            if element is None:
                if not iterator.next():
                    break
                continue

            ifc_class = element.is_a()
            element_type = ELEMENT_TYPE_LAYERS.get(ifc_class, "Other")

            hierarchy_key = self._get_element_spatial_hierarchy(element, ifc_file)
            if not hierarchy_key:
                if not iterator.next():
                    break
                continue

            site_name, building_name, storey_name = hierarchy_key

            verts = list(shape.geometry.verts)
            faces = list(shape.geometry.faces)

            if not verts or not faces:
                if not iterator.next():
                    break
                continue

            self._process_element(
                element=element,
                guid=shape.guid,
                verts=verts,
                faces=faces,
                site_name=site_name,
                building_name=building_name,
                storey_name=storey_name,
                element_type=element_type,
            )

            count += 1

            if not iterator.next():
                break

        if self._delete_removed:
            self._remove_deleted(ifc_file)

        return count

    def clear(self) -> int:
        """
        Remove all IFC-imported meshes and layers.

        Returns:
            Number of meshes removed
        """
        import Rhino

        count = 0

        for rhino_guid in self._guid_to_rhino_guid.values():
            obj = self.doc.Objects.Find(rhino_guid)
            if obj:
                self.doc.Objects.Delete(obj, True)
                count += 1

        self._guid_to_rhino_guid.clear()
        self._layer_cache.clear()

        root_index = self.doc.Layers.FindByName(self.layer_root, -1)
        if root_index >= 0:
            self._delete_layer_recursive(root_index)

        return count

    def set_delete_removed(self, enabled: bool) -> None:
        """
        Enable/disable deletion of elements no longer in IFC.

        Args:
            enabled: If True, remove meshes whose GUID is no longer in IFC
        """
        self._delete_removed = enabled

    def _get_element_spatial_hierarchy(
        self, element: Any, ifc_file: Any
    ) -> Optional[tuple[str, str, str]]:
        """
        Traverse up from element to find its spatial container.

        Returns:
            (site_name, building_name, storey_name) or None
        """
        visited = set()
        current = element

        while current and current.id() not in visited:
            visited.add(current.id())

            ifc_class = current.is_a()

            if ifc_class == "IfcBuildingStorey":
                return ("Site", "Building", current.Name or "Storey")

            if ifc_class == "IfcBuilding":
                return ("Site", current.Name or "Building", "Storey")

            if ifc_class == "IfcSite":
                return (current.Name or "Site", "Building", "Storey")

            for rel in getattr(current, "ContainedInStructure", []) or []:
                if hasattr(rel, "RelatingStructure"):
                    current = rel.RelatingStructure
                    break
            else:
                for rel in getattr(current, "Decomposes", []) or []:
                    if hasattr(rel, "RelatingObject"):
                        current = rel.RelatingObject
                        break
                else:
                    break

        return None

    def _process_element(
        self,
        element: Any,
        guid: str,
        verts: list,
        faces: list,
        site_name: str,
        building_name: str,
        storey_name: str,
        element_type: str,
    ) -> None:
        """Process a single IFC element."""
        layer_path = self.layer_root
        layer_path += f"::{site_name}"
        layer_path += f"::{building_name}"
        layer_path += f"::{storey_name}"
        layer_path += f"::{element_type}"

        layer_index = self._ensure_layer(layer_path)
        element_name = element.Name or guid

        if guid in self._guid_to_rhino_guid:
            self._update_mesh(guid, verts, faces)
        else:
            mesh = self._create_rhino_mesh(verts, faces)
            new_guid = self._add_mesh(mesh, layer_index, guid, element_name)
            self._guid_to_rhino_guid[guid] = new_guid

    def _create_rhino_mesh(self, verts: list, faces: list) -> Any:
        """Create Rhino mesh from vertex/face data."""
        import Rhino

        mesh = Rhino.Geometry.Mesh()

        for i in range(0, len(verts), 3):
            mesh.Vertices.Add(verts[i], verts[i + 1], verts[i + 2])

        for i in range(0, len(faces), 3):
            mesh.Faces.AddFace(faces[i], faces[i + 1], faces[i + 2])

        mesh.Normals.ComputeNormals()
        mesh.Compact()

        return mesh

    def _ensure_layer(self, path: str) -> int:
        """Ensure layer hierarchy exists."""
        if path in self._layer_cache:
            return self._layer_cache[path]

        import Rhino

        parts = path.split("::")

        for i, part in enumerate(parts):
            current_path = "::".join(parts[: i + 1])

            if current_path in self._layer_cache:
                continue

            layer = Rhino.DocObjects.Layer()
            layer.Name = part

            if i > 0:
                parent_path = "::".join(parts[:i])
                if parent_path in self._layer_cache:
                    parent_layer = self.doc.Layers[self._layer_cache[parent_path]]
                    layer.ParentLayerId = parent_layer.Id

            index = self.doc.Layers.Add(layer)
            self._layer_cache[current_path] = index

        return self._layer_cache[path]

    def _add_mesh(
        self, mesh: Any, layer_index: int, ifc_guid: str, element_name: str
    ) -> Any:
        """Add new mesh to document."""
        import Rhino

        attributes = Rhino.DocObjects.ObjectAttributes()
        attributes.LayerIndex = layer_index
        attributes.Name = element_name
        attributes.SetUserString("ifc_guid", ifc_guid)

        return self.doc.Objects.Add(mesh, attributes)

    def _update_mesh(self, guid: str, new_verts: list, new_faces: list) -> None:
        """Update existing mesh geometry."""
        import Rhino

        rhino_guid = self._guid_to_rhino_guid.get(guid)
        if not rhino_guid:
            return

        obj = self.doc.Objects.Find(rhino_guid)
        if not obj or not obj.Geometry:
            return

        mesh = Rhino.Geometry.Mesh()

        for i in range(0, len(new_verts), 3):
            mesh.Vertices.Add(new_verts[i], new_verts[i + 1], new_verts[i + 2])

        for i in range(0, len(new_faces), 3):
            mesh.Faces.AddFace(new_faces[i], new_faces[i + 1], new_faces[i + 2])

        mesh.Normals.ComputeNormals()
        mesh.Compact()

        self.doc.Objects.Replace(rhino_guid, mesh)

    def _remove_deleted(self, ifc_file: Any) -> None:
        """Remove meshes whose GUID is no longer in IFC."""
        ifc_guids = set()

        settings = None
        try:
            import ifcopenshell.geom as ic_geom
            settings = ic_geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)
            iterator = ic_geom.iterator(settings, ifc_file)
            if iterator.initialize():
                while True:
                    shape = iterator.get()
                    ifc_guids.add(shape.guid)
                    if not iterator.next():
                        break
        except ImportError:
            pass

        to_remove = []
        for ifc_guid, rhino_guid in self._guid_to_rhino_guid.items():
            if ifc_guid not in ifc_guids:
                to_remove.append((ifc_guid, rhino_guid))

        for ifc_guid, rhino_guid in to_remove:
            obj = self.doc.Objects.Find(rhino_guid)
            if obj:
                self.doc.Objects.Delete(obj, True)
            del self._guid_to_rhino_guid[ifc_guid]

    def _delete_layer_recursive(self, layer_index: int) -> None:
        """Recursively delete layer and its children."""
        layer = self.doc.Layers[layer_index]

        children = layer.GetChildren()
        for child in children or []:
            child_idx = self.doc.Layers.FindByName(child.Name, layer_index)
            if child_idx >= 0:
                self._delete_layer_recursive(child_idx)

        self.doc.Layers.Delete(layer_index, True)