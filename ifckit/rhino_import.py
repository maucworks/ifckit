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

import os
from typing import Any, Optional


# (linear_deflection, angular_deflection)
# linear_deflection: max chord deviation in metres
# angular_deflection: max angle between facet normals in radians
MESH_QUALITY: dict[str, tuple[float, float]] = {
    "superfine":   (0.0001, 0.05),   # ~2.9°  — slowest, highest fidelity
    "fine":        (0.0005, 0.1),    # ~5.7°
    "default":     (0.001,  0.5),    # ~28.6° — ifcopenshell default
    "coarse":      (0.005,  1.0),    # ~57.3°
    "supercoarse": (0.01,   1.5),    # ~85.9° — fastest, lowest fidelity
}


def _ifc_class_to_layer(ifc_class: str) -> str:
    """Strip 'Ifc' prefix and naive-pluralize for use as a layer name.

    Examples:
        IfcWall             -> Walls
        IfcWallStandardCase -> Walls  (StandardCase suffix stripped)
        IfcBeam             -> Beams
        IfcCurtainWall      -> CurtainWalls
        IfcStair            -> Stairs
        IfcProxy            -> Proxies
    """
    name = ifc_class[3:] if ifc_class.startswith("Ifc") else ifc_class
    # Strip common noise suffixes so variants land on the same layer
    for suffix in ("StandardCase", "ElementedCase"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Naive pluralise
    if name.endswith("s") or name.endswith("x") or name.endswith("z"):
        return name + "es"
    if name.endswith("y") and not name[-2] in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def _colour_from_item(item: Any) -> Optional[tuple]:
    """Walk IfcRepresentationItem → IfcStyledItem → IfcSurfaceStyleRendering.

    Returns (r, g, b, a) with values 0–255, or None.
    """
    styled_items = []

    if item.is_a("IfcStyledItem"):
        styled_items.append(item)

    # IfcRepresentationItem may reference a StyledByItem inverse
    for rel in getattr(item, "StyledByItem", []) or []:
        styled_items.append(rel)

    for styled in styled_items:
        for style in getattr(styled, "Styles", []) or []:
            # IFC4: IfcSurfaceStyle wraps a set of IfcSurfaceStyleElementSelect
            if style.is_a("IfcSurfaceStyle"):
                for s in getattr(style, "Styles", []) or []:
                    colour = _colour_from_surface_style(s)
                    if colour:
                        return colour
            colour = _colour_from_surface_style(style)
            if colour:
                return colour
    return None


def _colour_from_surface_style(style: Any) -> Optional[tuple]:
    """Extract RGBA from IfcSurfaceStyleRendering or IfcSurfaceStyleShading."""
    if not style.is_a("IfcSurfaceStyleRendering") and not style.is_a("IfcSurfaceStyleShading"):
        return None
    colour_rgb = getattr(style, "SurfaceColour", None)
    if colour_rgb is None:
        return None
    r = int(round(colour_rgb.Red * 255))
    g = int(round(colour_rgb.Green * 255))
    b = int(round(colour_rgb.Blue * 255))
    transparency = float(getattr(style, "Transparency", None) or 0.0)
    a = int(round((1.0 - transparency) * 255))
    return (r, g, b, a)


class IfcMeshImporter:
    """
    Import IFC geometry into Rhino as meshes.

    Features:
    - Layer hierarchy mirrors IFC spatial structure
    - Smart update by GUID (updates changed, adds new)
    - Optional removal of deleted elements

    Args:
        doc: Rhino document. Defaults to RhinoDoc.ActiveDoc.
        layer_root: Root layer name (default: "IFC")
        clear_on_import: If True, clear existing IFC meshes before import
        delete_removed: If True, delete meshes no longer present in IFC
        mesh_quality: Tessellation quality preset (superfine/fine/default/coarse/supercoarse)
    """

    def __init__(
        self,
        doc: Any = None,
        layer_root: str = "IFC",
        clear_on_import: bool = False,
        delete_removed: bool = False,
        mesh_quality: str = "default",
    ) -> None:
        import Rhino
        self.doc = doc if doc is not None else Rhino.RhinoDoc.ActiveDoc

        self.layer_root = layer_root
        self.clear_on_import = clear_on_import
        self.delete_removed = delete_removed
        if mesh_quality not in MESH_QUALITY:
            raise ValueError(f"mesh_quality must be one of {list(MESH_QUALITY)}")
        self.linear_deflection, self.angular_deflection = MESH_QUALITY[mesh_quality]

        self._guid_to_rhino_guid: dict[str, Any] = {}
        self._layer_cache: dict[str, int] = {}
        self._ifc_unit_scale: float = 1.0
        self._seen_guids: set = set()
        self._skip_update: bool = False

        self._rhino_unit = self.doc.ModelUnitSystem

    def _detect_unit(self) -> None:
        """Compute scale factor: ifcopenshell.geom always returns metres."""
        import Rhino

        unit_map = {
            Rhino.UnitSystem.Millimeters: 1000.0,
            Rhino.UnitSystem.Centimeters: 100.0,
            Rhino.UnitSystem.Meters: 1.0,
            Rhino.UnitSystem.Feet: 3.28084,
            Rhino.UnitSystem.Inches: 39.3701,
        }
        self._ifc_unit_scale = unit_map.get(self._rhino_unit, 1.0)

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
        self._seen_guids.clear()
        self._skip_update = False

        self._detect_unit()

        settings = ic_geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.APPLY_DEFAULT_MATERIALS, True)
        settings.set("mesher-linear-deflection", self.linear_deflection)
        settings.set("mesher-angular-deflection", self.angular_deflection)

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

            guid = shape.guid
            if guid in self._seen_guids:
                if not iterator.next():
                    break
                continue
            self._seen_guids.add(guid)

            element_type = _ifc_class_to_layer(ifc_class)

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

        if self.delete_removed:
            self._remove_deleted()

        return count

    def clear(self) -> int:
        """Remove all IFC-imported meshes and IFC layers.

        Returns:
            Number of meshes removed
        """
        to_delete = []
        for obj in self.doc.Objects:
            if obj.ObjectType == 0:
                continue
            try:
                if obj.Attributes.GetUserString("ifc_guid"):
                    to_delete.append(obj.Id)
            except Exception:
                pass

        for obj_id in to_delete:
            obj = self.doc.Objects.Find(obj_id)
            if obj:
                self.doc.Objects.Delete(obj, True)

        self._guid_to_rhino_guid.clear()
        self._layer_cache.clear()
        self._seen_guids.clear()
        self._skip_update = True

        root_layer = self.doc.Layers.FindName(self.layer_root)
        if root_layer is not None:
            idx = root_layer.Index
            if idx >= 0:
                self._delete_layer_recursive(idx)

        return len(to_delete)

    def _delete_layer_recursive(self, layer_index: int) -> None:
        """Recursively delete layer and all its children."""
        if layer_index < 0:
            return

        children = self.doc.Layers[layer_index].GetChildren()
        for child in children or []:
            self._delete_layer_recursive(child.Index)

        self.doc.Layers.Delete(layer_index, False)

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
                storey = current.Name or "UnknownStorey"
                # walk further up to get building/site names
                building, site = "UnknownBuilding", "UnknownSite"
                parent = current
                for rel in getattr(parent, "Decomposes", []) or []:
                    if hasattr(rel, "RelatingObject"):
                        p = rel.RelatingObject
                        if p.is_a() == "IfcBuilding":
                            building = p.Name or "UnknownBuilding"
                            for rel2 in getattr(p, "Decomposes", []) or []:
                                if hasattr(rel2, "RelatingObject"):
                                    s = rel2.RelatingObject
                                    if s.is_a() == "IfcSite":
                                        site = s.Name or "UnknownSite"
                return (site, building, storey)

            if ifc_class == "IfcBuilding":
                building = current.Name or "UnknownBuilding"
                for rel in getattr(current, "Decomposes", []) or []:
                    if hasattr(rel, "RelatingObject"):
                        s = rel.RelatingObject
                        if s.is_a() == "IfcSite":
                            return (s.Name or "UnknownSite", building, "UnknownStorey")
                return ("UnknownSite", building, "UnknownStorey")

            if ifc_class == "IfcSite":
                return (current.Name or "UnknownSite", "UnknownBuilding", "UnknownStorey")

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
        layer_path = f"{self.layer_root}::{site_name}::{building_name}::{storey_name}::{element_type}"

        layer_index = self._ensure_layer(layer_path)
        element_name = element.Name or f"{element_type}_{guid[:8]}"
        colour = self._get_ifc_colour(element)

        if guid in self._guid_to_rhino_guid and not self._skip_update:
            self._update_geometry(guid, verts, faces)
        else:
            geometry = self._create_rhino_mesh(verts, faces)
            new_guid = self._add_geometry(geometry, layer_index, guid, element_name, colour)
            self._guid_to_rhino_guid[guid] = new_guid

    @staticmethod
    def _get_ifc_colour(element: Any) -> Optional[tuple]:
        """Extract RGBA from IfcStyledItem → IfcSurfaceStyleRendering.

        Returns an (r, g, b, a) tuple with values 0–255, or None if no style
        is present.  Alpha is derived from ``Transparency`` (0 = opaque,
        1 = fully transparent) and mapped to 255 = opaque, 0 = transparent.
        """
        try:
            for assoc in getattr(element, "HasAssociations", []) or []:
                if assoc.is_a("IfcRelAssociatesMaterial"):
                    continue  # material, not style
            rep = getattr(element, "Representation", None)
            if rep is None:
                return None
            for shape_rep in rep.Representations or []:
                for item in shape_rep.Items or []:
                    colour = _colour_from_item(item)
                    if colour:
                        return colour
        except Exception:
            pass
        return None

    def _create_rhino_mesh(self, verts: list, faces: list) -> Any:
        """Create Rhino mesh from vertex/face data with flat (hard-edge) shading.

        ifcopenshell returns an indexed mesh where vertices are shared between
        faces.  Calling ``ComputeNormals()`` on that produces smooth interpolated
        vertex normals, making flat-faced geometry (boxes, beams, slabs) look
        rounded.

        Fix: build an *unwelded* mesh — each triangle gets its own three
        vertices so Rhino computes one flat normal per face instead of
        blending across shared vertices.
        """
        import Rhino

        mesh = Rhino.Geometry.Mesh()
        s = self._ifc_unit_scale

        # Pre-index original vertices for fast lookup
        all_verts = [verts[i:i + 3] for i in range(0, len(verts), 3)]

        # Add one dedicated vertex triple per face (unweld)
        vi = 0
        for i in range(0, len(faces), 3):
            a, b, c = faces[i], faces[i + 1], faces[i + 2]
            for idx in (a, b, c):
                x, y, z = all_verts[idx]
                mesh.Vertices.Add(x * s, y * s, z * s)
            mesh.Faces.AddFace(vi, vi + 1, vi + 2)
            vi += 3

        mesh.Normals.ComputeNormals()
        mesh.Compact()

        return mesh

    def _ensure_layer(self, path: str) -> int:
        """Ensure layer hierarchy exists. Returns layer index or raises."""
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
                    parent_layer_index = self._layer_cache[parent_path]
                    if parent_layer_index >= 0:
                        parent_layer = self.doc.Layers[parent_layer_index]
                        layer.ParentLayerId = parent_layer.Id

            index = self.doc.Layers.Add(layer)
            if index < 0:
                raise RuntimeError(f"Failed to create Rhino layer: {current_path!r}")
            self._layer_cache[current_path] = index

        result = self._layer_cache[path]
        return result if result >= 0 else 0

    def _add_geometry(
        self, mesh: Any, layer_index: int, ifc_guid: str, element_name: str,
        colour: Optional[tuple] = None,
    ) -> Any:
        """Add new mesh to document."""
        import Rhino
        import System.Drawing

        attributes = Rhino.DocObjects.ObjectAttributes()
        attributes.LayerIndex = layer_index
        attributes.Name = element_name
        attributes.SetUserString("ifc_guid", ifc_guid)

        if colour is not None:
            r, g, b, a = colour
            attributes.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            attributes.ObjectColor = System.Drawing.Color.FromArgb(a, r, g, b)
            if a < 255:
                # Create a simple render material with transparency
                mat = Rhino.DocObjects.Material()
                mat.DiffuseColor = System.Drawing.Color.FromArgb(255, r, g, b)
                mat.Transparency = 1.0 - a / 255.0
                mat_index = self.doc.Materials.Add(mat)
                attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
                attributes.MaterialIndex = mat_index

        return self.doc.Objects.Add(mesh, attributes)

    def _update_geometry(self, guid: str, new_verts: list, new_faces: list) -> None:
        """Replace geometry of an existing Rhino object in-place."""
        rhino_guid = self._guid_to_rhino_guid.get(guid)
        if not rhino_guid:
            return

        obj = self.doc.Objects.Find(rhino_guid)
        if not obj or not obj.Geometry:
            return

        geometry = self._create_rhino_mesh(new_verts, new_faces)
        self.doc.Objects.Replace(rhino_guid, geometry)

    def _remove_deleted(self) -> None:
        """Remove meshes whose GUID was not seen in the current import."""
        to_remove = [
            (ifc_guid, rhino_guid)
            for ifc_guid, rhino_guid in self._guid_to_rhino_guid.items()
            if ifc_guid not in self._seen_guids
        ]
        for ifc_guid, rhino_guid in to_remove:
            obj = self.doc.Objects.Find(rhino_guid)
            if obj:
                self.doc.Objects.Delete(obj, True)
            del self._guid_to_rhino_guid[ifc_guid]

