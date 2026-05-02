"""
ifckit.rhino_import
===================

Import IFC geometry into Rhino as meshes (``IfcMeshImporter``) or as 2-D
curves and hatches derived from an SVG floor-plan view (``IfcSvgImporter``).

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

from __future__ import annotations

import io
import math
import os
import re
import xml.etree.ElementTree as ET
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


def _ensure_layer(doc: Any, path: str, cache: dict) -> int:
    """Ensure a ``::``-separated layer hierarchy exists in *doc*.

    Creates each missing layer in order and stores the resulting index in
    *cache* (keyed by the full path string).  Returns the leaf layer index.

    Args:
        doc:   Rhino document (``RhinoDoc``).
        path:  Layer path with ``::`` separators, e.g.
               ``"IFC-SVG::Ground Floor::cut::IfcWall"``.
        cache: Mutable dict used as a per-importer index cache.

    Returns:
        Integer layer index of the leaf layer.
    """
    if path in cache:
        return cache[path]

    import Rhino

    parts = path.split("::")

    for i, part in enumerate(parts):
        current_path = "::".join(parts[: i + 1])

        if current_path in cache:
            continue

        layer = Rhino.DocObjects.Layer()
        layer.Name = part

        if i > 0:
            parent_path = "::".join(parts[:i])
            if parent_path in cache:
                parent_layer_index = cache[parent_path]
                if parent_layer_index >= 0:
                    parent_layer = doc.Layers[parent_layer_index]
                    layer.ParentLayerId = parent_layer.Id

        index = doc.Layers.Add(layer)
        if index < 0:
            raise RuntimeError(f"Failed to create Rhino layer: {current_path!r}")
        cache[current_path] = index

    result = cache[path]
    return result if result >= 0 else 0


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
        return _ensure_layer(self.doc, path, self._layer_cache)

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


# ---------------------------------------------------------------------------
# SVG path parser (pure Python, no extra dependencies)
# ---------------------------------------------------------------------------

_SVG_CMD_RE = re.compile(r"([MmLlHhVvAaZzCcSsQqTt])")
_SVG_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_NS = {
    "svg": "http://www.w3.org/2000/svg",
    "ifc": "http://www.ifcopenshell.org/ns",
}


def _parse_path_d(d: str) -> list[tuple]:
    """Parse an SVG path ``d`` attribute into a list of absolute segments.

    Each segment is a tuple whose first element is a command letter (upper
    case, i.e. absolute coordinates) and the remaining elements are floats:

    * ``("M", x, y)``        – move-to (starts a new sub-path)
    * ``("L", x, y)``        – line-to
    * ``("A", rx, ry, x_rot, large_arc, sweep, x, y)`` – arc
    * ``("Z",)``             – close path

    Unsupported commands (C, S, Q, T) are approximated as straight lines to
    the final endpoint of each segment so that the boundary is still usable
    as a hatch outline.

    Args:
        d: SVG path data string.

    Returns:
        List of segment tuples in absolute coordinates.
    """
    # Tokenise: split on command letters, keep the letter
    tokens = _SVG_CMD_RE.split(d.strip())
    # tokens[0] is empty string before first command
    # interleaved: ["", "M", "10,20", "L", "30,40 50,60", "Z", ""]

    # Group into (cmd_letter, [numbers]) pairs
    cmd_blocks: list[tuple[str, list[float]]] = []
    i = 1
    while i < len(tokens):
        cmd = tokens[i]
        nums_str = tokens[i + 1] if i + 1 < len(tokens) else ""
        nums = [float(n) for n in _SVG_NUM_RE.findall(nums_str)]
        cmd_blocks.append((cmd, nums))
        i += 2

    segments: list[tuple] = []
    cx, cy = 0.0, 0.0   # current point
    sx, sy = 0.0, 0.0   # sub-path start (for Z)

    for cmd, nums in cmd_blocks:
        # ---------- M / m ----------
        if cmd in ("M", "m"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for k, (dx, dy) in enumerate(pairs):
                if cmd == "m":
                    cx += dx; cy += dy
                else:
                    cx, cy = dx, dy
                if k == 0:
                    sx, sy = cx, cy
                    segments.append(("M", cx, cy))
                else:
                    # Implicit L after first pair
                    segments.append(("L", cx, cy))

        # ---------- L / l ----------
        elif cmd in ("L", "l"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for dx, dy in pairs:
                if cmd == "l":
                    cx += dx; cy += dy
                else:
                    cx, cy = dx, dy
                segments.append(("L", cx, cy))

        # ---------- H / h ----------
        elif cmd in ("H", "h"):
            for v in nums:
                if cmd == "h":
                    cx += v
                else:
                    cx = v
                segments.append(("L", cx, cy))

        # ---------- V / v ----------
        elif cmd in ("V", "v"):
            for v in nums:
                if cmd == "v":
                    cy += v
                else:
                    cy = v
                segments.append(("L", cx, cy))

        # ---------- A / a ----------
        elif cmd in ("A", "a"):
            # 7 numbers per arc: rx ry x-rotation large-arc-flag sweep-flag x y
            n = 7
            for j in range(0, len(nums), n):
                chunk = nums[j: j + n]
                if len(chunk) < n:
                    break
                rx, ry, x_rot, large_arc, sweep, ex, ey = chunk
                if cmd == "a":
                    ex += cx; ey += cy
                segments.append(("A", rx, ry, x_rot, int(large_arc), int(sweep), ex, ey))
                cx, cy = ex, ey

        # ---------- Z / z ----------
        elif cmd in ("Z", "z"):
            segments.append(("Z",))
            cx, cy = sx, sy

        # ---------- C / c (cubic bezier — approximate as line to endpoint) ----------
        elif cmd in ("C", "c"):
            # 6 numbers per segment: cp1x cp1y cp2x cp2y ex ey
            for j in range(0, len(nums), 6):
                chunk = nums[j: j + 6]
                if len(chunk) < 6:
                    break
                ex, ey = chunk[4], chunk[5]
                if cmd == "c":
                    ex += cx; ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        # ---------- S / s (smooth cubic — approximate) ----------
        elif cmd in ("S", "s"):
            for j in range(0, len(nums), 4):
                chunk = nums[j: j + 4]
                if len(chunk) < 4:
                    break
                ex, ey = chunk[2], chunk[3]
                if cmd == "s":
                    ex += cx; ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        # ---------- Q / q (quadratic bezier — approximate) ----------
        elif cmd in ("Q", "q"):
            for j in range(0, len(nums), 4):
                chunk = nums[j: j + 4]
                if len(chunk) < 4:
                    break
                ex, ey = chunk[2], chunk[3]
                if cmd == "q":
                    ex += cx; ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        # ---------- T / t (smooth quadratic — approximate) ----------
        elif cmd in ("T", "t"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for dx, dy in pairs:
                if cmd == "t":
                    cx += dx; cy += dy
                else:
                    cx, cy = dx, dy
                segments.append(("L", cx, cy))

    return segments


def _parse_fill_colour(style: str) -> Optional[tuple[int, int, int]]:
    """Extract ``fill`` colour from an inline SVG style string.

    Handles ``fill: rgb(r, g, b)`` and ``fill: #rrggbb``.

    Returns:
        ``(r, g, b)`` integers 0–255, or *None* if no fill is present.
    """
    if not style:
        return None

    # rgb(r, g, b) — values may be floats, e.g. rgb(245.10, 245.10, 245.10)
    m = re.search(r"fill\s*:\s*rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", style)
    if m:
        r = min(255, int(round(float(m.group(1)))))
        g = min(255, int(round(float(m.group(2)))))
        b = min(255, int(round(float(m.group(3)))))
        return r, g, b

    # #rrggbb
    m = re.search(r"fill\s*:\s*#([0-9a-fA-F]{6})", style)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    return None


def _parse_matrix3(matrix3_attr: str) -> Optional[tuple[float, float, float]]:
    """Parse the ``ifc:matrix3`` attribute on a storey ``<g>`` element.

    IfcOpenShell serialises the 2-D affine transform from model coordinates
    (metres) to SVG coordinates (mm at drawing scale) as a 3×3 row-major
    matrix::

        [[sc,  0, tx],
         [ 0, sc, ty],
         [ 0,  0,  1]]

    i.e. ``SVG_x = model_x * sc + tx``  and  ``SVG_y = model_y * sc + ty``
    (where model Y is already negated/flipped by IfcOpenShell before the
    matrix is applied).

    The **inverse** transform used by the importer is::

        model_x  = (SVG_x - tx) / sc          (metres)
        model_y  = (SVG_y - ty) / sc          (metres, Y-up after caller flips)
        rhino    = model * rhino_unit_factor   (e.g. ×1000 for mm Rhino doc)

    Args:
        matrix3_attr: Raw attribute string, e.g.
            ``"[[10.0,0.0,141.1],[0.0,10.0,280.9],[0.0,0.0,1.0]]"``.

    Returns:
        ``(sc, tx, ty)`` floats, or *None* if parsing fails.
    """
    if not matrix3_attr:
        return None
    nums = [float(n) for n in _SVG_NUM_RE.findall(matrix3_attr)]
    # Row-major layout: index 0=sc, 1=0, 2=tx, 3=0, 4=sc, 5=ty, 6=0, 7=0, 8=1
    if len(nums) >= 9:
        sc = nums[0]
        tx = nums[2]
        ty = nums[5]
        if sc == 0.0:
            return None
        return sc, tx, ty
    return None


def _parse_ifc_plane(plane_attr: str) -> Optional[list]:
    """Parse the ``ifc:plane`` attribute on a ``<g class="section">`` element.

    IfcOpenShell serialises the section plane as a 4×4 row-major matrix in
    **metres**::

        [[rx, ux, nx, ox],
         [ry, uy, ny, oy],
         [rz, uz, nz, oz],
         [0,  0,  0,  1 ]]

    where (rx,ry,rz) = x-axis, (ux,uy,uz) = y-axis, (nx,ny,nz) = normal,
    (ox,oy,oz) = origin in metres.

    Args:
        plane_attr: Raw attribute string.

    Returns:
        Row-major 4×4 list of floats, or *None* if parsing fails.
    """
    if not plane_attr:
        return None
    nums = [float(n) for n in _SVG_NUM_RE.findall(plane_attr)]
    if len(nums) >= 16:
        return nums[:16]
    return None


def _arc_segment_to_rhino_curve(
    x0: float, y0: float,
    rx: float, ry: float,
    x_rot_deg: float,
    large_arc: int,
    sweep: int,
    x1: float, y1: float,
    z: float,
) -> Any:
    """Convert an SVG arc segment to a Rhino ``ArcCurve``.

    All x/y coordinates are in **Rhino document units** (already transformed
    from SVG space by the caller).  ``rx`` and ``ry`` are also in Rhino units.

    Only circular arcs (rx == ry, x_rot == 0) are converted to true
    ``ArcCurve``; elliptical arcs fall back to a straight ``LineCurve``.

    Args:
        x0, y0: Start point in Rhino units (Y-up).
        rx, ry: Semi-axes in Rhino units.
        x_rot_deg: X-axis rotation in degrees.
        large_arc: Large-arc flag (0 or 1).
        sweep: Sweep flag (1 = CCW in SVG Y-down = CW after Y-flip).
        x1, y1: End point in Rhino units (Y-up).
        z: Z height in Rhino units.

    Returns:
        A Rhino ``Curve`` object, or *None* if degenerate.
    """
    import Rhino

    if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
        return None

    p0 = Rhino.Geometry.Point3d(x0, y0, z)
    p1 = Rhino.Geometry.Point3d(x1, y1, z)

    if rx < 1e-9 or ry < 1e-9:
        return Rhino.Geometry.LineCurve(p0, p1)

    if abs(rx - ry) < 1e-6 * rx and abs(x_rot_deg) < 1e-6:
        r = rx
        phi = math.radians(x_rot_deg)   # == 0
        mx = (x0 - x1) / 2.0
        my = (y0 - y1) / 2.0
        x1p =  math.cos(phi) * mx + math.sin(phi) * my
        y1p = -math.sin(phi) * mx + math.cos(phi) * my

        r2   = r * r
        x1p2 = x1p * x1p
        y1p2 = y1p * y1p
        denom = r2 * (x1p2 + y1p2)
        if denom < 1e-12:
            return Rhino.Geometry.LineCurve(p0, p1)

        sq = max(0.0, (r2 * r2 - r2 * x1p2 - r2 * y1p2) / denom)
        sq = math.sqrt(sq)
        if large_arc == sweep:
            sq = -sq

        cxp =  sq * r * y1p / r
        cyp = -sq * r * x1p / r
        cx = math.cos(phi) * cxp - math.sin(phi) * cyp + (x0 + x1) / 2.0
        cy = math.sin(phi) * cxp + math.cos(phi) * cyp + (y0 + y1) / 2.0

        def _angle(ux, uy, vx, vy):
            return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

        a_start = _angle(1, 0, (x0 - cx) / r, (y0 - cy) / r)
        d_theta = _angle(
            (x0 - cx) / r, (y0 - cy) / r,
            (x1 - cx) / r, (y1 - cy) / r,
        )
        # sweep=1 in SVG (CW in Y-down) → CCW in Rhino (Y-up) → d_theta > 0
        if sweep == 1 and d_theta < 0:
            d_theta += 2 * math.pi
        elif sweep == 0 and d_theta > 0:
            d_theta -= 2 * math.pi

        centre = Rhino.Geometry.Point3d(cx, cy, z)
        plane  = Rhino.Geometry.Plane(centre, Rhino.Geometry.Vector3d.ZAxis)
        try:
            arc = Rhino.Geometry.Arc(plane, r, abs(d_theta))
            arc.StartAngle = a_start if d_theta > 0 else a_start + d_theta
            arc.EndAngle   = a_start + d_theta if d_theta > 0 else a_start
            crv = Rhino.Geometry.ArcCurve(arc)
            if crv.IsValid:
                return crv
        except Exception:
            pass

    return Rhino.Geometry.LineCurve(p0, p1)


def _segments_to_rhino(
    segments: list[tuple],
    z: float,
    sc: float,
    tx: float,
    ty: float,
    uf: float,
    plane: Optional[list] = None,
) -> tuple[list, list]:
    """Convert parsed SVG path segments to Rhino curves.

    Applies the inverse of the ``ifc:matrix3`` affine transform to convert
    SVG coordinates back to local model coordinates (metres), then either:

    - If *plane* is given (``ifc:plane`` 4×4 row-major matrix in metres):
      transforms local (x, y, 0) → world-space via the plane matrix, then
      scales to Rhino document units.
    - Otherwise: places curves at ``z`` in Rhino document units using the
      flat XY transform.

    Transform (flat mode)::

        rhino_x =  (svg_x - tx) / sc * uf
        rhino_y = -(svg_y - ty) / sc * uf   ← Y-flip: SVG Y-down → Rhino Y-up

    Transform (plane mode)::

        local_x = (svg_x - tx) / sc          # metres along plane x-axis
        local_y = (svg_y - ty) / sc          # metres along plane y-axis (SVG Y-down → negate)
        world   = plane_matrix * [local_x, -local_y, 0, 1]  # metres
        rhino   = world * uf

    Args:
        segments: Output of :func:`_parse_path_d`.
        z:    Z height in Rhino document units (used only when *plane* is None).
        sc:   Scale factor from ``ifc:matrix3`` (SVG units per model-metre).
        tx:   X translation from ``ifc:matrix3`` (SVG units).
        ty:   Y translation from ``ifc:matrix3`` (SVG units).
        uf:   Rhino unit factor (metres → Rhino units, e.g. 1000 for mm).
        plane: Optional 16-element row-major 4×4 plane matrix in metres
               from ``ifc:plane``.  When provided, curves are placed in
               world-space on the section plane rather than at a fixed Z.

    Returns:
        ``(open_curves, closed_curves)`` — Rhino ``Curve`` objects.
        Closed curves appear in *both* lists.
    """
    import Rhino

    if plane is not None:
        # Pre-extract plane columns for speed:
        # plane[row*4 + col]
        # world = M * [lx, -ly, 0, 1]  where lx/ly in metres
        # wx = m00*lx + m01*(-ly) + m03
        # wy = m10*lx + m11*(-ly) + m13
        # wz = m20*lx + m21*(-ly) + m23
        m00,m01,m02,m03 = plane[0],plane[1],plane[2],plane[3]
        m10,m11,m12,m13 = plane[4],plane[5],plane[6],plane[7]
        m20,m21,m22,m23 = plane[8],plane[9],plane[10],plane[11]

        def _to_rhino_xyz(svg_x: float, svg_y: float):
            lx = (svg_x - tx) / sc   # local metres, x
            ly = (svg_y - ty) / sc   # local metres, y (SVG Y-down, flip below)
            # Apply Y-flip: SVG y-down → local y-up → negate ly
            wx = (m00 * lx + m01 * (-ly) + m03) * uf
            wy = (m10 * lx + m11 * (-ly) + m13) * uf
            wz = (m20 * lx + m21 * (-ly) + m23) * uf
            return wx, wy, wz

        def _make_pt(svg_x, svg_y):
            wx, wy, wz = _to_rhino_xyz(svg_x, svg_y)
            return Rhino.Geometry.Point3d(wx, wy, wz)

        def _make_arc(prev_pt, arx, ary, x_rot, large_arc, sweep, ex, ey):
            arx_r = arx / sc * uf
            ary_r = ary / sc * uf
            dest_wx, dest_wy, dest_wz = _to_rhino_xyz(ex, ey)
            return _arc_segment_to_rhino_curve(
                prev_pt.X, prev_pt.Y,
                arx_r, ary_r,
                x_rot, large_arc, sweep,
                dest_wx, dest_wy,
                prev_pt.Z,
            ), Rhino.Geometry.Point3d(dest_wx, dest_wy, dest_wz)

    else:
        def _make_pt(svg_x, svg_y):
            return Rhino.Geometry.Point3d(
                (svg_x - tx) / sc * uf,
                -(svg_y - ty) / sc * uf,
                z,
            )

        def _make_arc(prev_pt, arx, ary, x_rot, large_arc, sweep, ex, ey):
            arx_r = arx / sc * uf
            ary_r = ary / sc * uf
            dest_rx = (ex - tx) / sc * uf
            dest_ry = -(ey - ty) / sc * uf
            return _arc_segment_to_rhino_curve(
                prev_pt.X, prev_pt.Y,
                arx_r, ary_r,
                x_rot, large_arc, sweep,
                dest_rx, dest_ry,
                z,
            ), Rhino.Geometry.Point3d(dest_rx, dest_ry, z)

    open_curves:   list = []
    closed_curves: list = []

    # Split on M into sub-paths
    sub_paths: list[list[tuple]] = []
    current: list[tuple] = []
    for seg in segments:
        if seg[0] == "M" and current:
            sub_paths.append(current)
            current = []
        current.append(seg)
    if current:
        sub_paths.append(current)

    for sub in sub_paths:
        if not sub:
            continue

        # Closed if explicit Z command, or if last point == first point
        _last_seg = sub[-1]
        _last_xy = (_last_seg[1], _last_seg[2]) if len(_last_seg) >= 3 else None
        _first_xy = (sub[0][1], sub[0][2])
        is_closed = (
            _last_seg[0] == "Z"
            or (_last_xy is not None and abs(_last_xy[0] - _first_xy[0]) < 1e-6 and abs(_last_xy[1] - _first_xy[1]) < 1e-6)
        )
        pts: list = []
        arc_entries: list[tuple[int, Any]] = []
        has_arcs = False

        _, sx, sy = sub[0]
        pts.append(_make_pt(sx, sy))

        for seg in sub[1:]:
            cmd = seg[0]
            if cmd == "L":
                _, ex, ey = seg
                pts.append(_make_pt(ex, ey))

            elif cmd == "A":
                _, arx, ary, x_rot, large_arc, sweep, ex, ey = seg
                prev = pts[-1]
                arc_crv, dest_pt = _make_arc(prev, arx, ary, x_rot, large_arc, sweep, ex, ey)
                if arc_crv is not None:
                    arc_entries.append((len(pts) - 1, arc_crv))
                    has_arcs = True
                pts.append(dest_pt)

            elif cmd == "Z":
                if pts and pts[-1].DistanceTo(pts[0]) > 1e-9:
                    pts.append(pts[0])

        if len(pts) < 2:
            continue

        if not has_arcs:
            crv = Rhino.Geometry.PolylineCurve(
                Rhino.Collections.Point3dList(pts)
            )
        else:
            poly = Rhino.Geometry.PolyCurve()
            arc_map = {idx: ac for idx, ac in arc_entries}
            i = 0
            while i < len(pts) - 1:
                if i in arc_map:
                    poly.AppendSegment(arc_map[i])
                else:
                    poly.AppendSegment(
                        Rhino.Geometry.LineCurve(pts[i], pts[i + 1])
                    )
                i += 1
            crv = poly

        if not crv.IsValid:
            continue

        open_curves.append(crv)
        if is_closed:
            closed_curves.append(crv)

    return open_curves, closed_curves



# ---------------------------------------------------------------------------
# IfcSvgImporter
# ---------------------------------------------------------------------------


#: Mapping from Bonsai/ifcopenshell hatch-pattern names to Rhino hatch names.
#: Keys are the values written to ``EPset_IfcKit.HatchPattern`` by the
#: ifckit builder; values are the names of hatch patterns that must exist
#: in the Rhino document.  Extend or override on the importer instance.
BONSAI_HATCH_MAP: dict[str, str] = {
    "Solid":            "Solid",
    "ANSI31":           "ANSI31",     # 45° steel hatch
    "ANSI32":           "ANSI32",
    "ANSI33":           "ANSI33",
    "ANSI34":           "ANSI34",
    "ANSI35":           "ANSI35",
    "ANSI36":           "ANSI36",
    "ANSI37":           "ANSI37",
    "ANSI38":           "ANSI38",
    "CONCRETE":         "Concrete",
    "EARTH":            "Earth",
    "GRAVEL":           "Gravel",
    "INSULATION":       "Insulation",
    "SAND":             "Sand",
    "WOOD":             "Wood",
}


class IfcSvgImporter:
    """Import IFC geometry into Rhino as 2-D curves and hatches.

    Generates a floor-plan SVG from an IFC model using
    ``ifcopenshell.draw``, then parses the SVG into:

    * **Curves** — one ``PolylineCurve`` / ``PolyCurve`` per ``<path>``
      element, placed on layers mirroring the SVG group structure.
    * **Hatches** — one ``Hatch`` per *closed* path that carries a fill
      colour, placed on a parallel ``_hatch``-suffixed layer set with the
      IFC material colour.  Hatch pattern is resolved per-element from
      ``EPset_IfcKit.HatchPattern`` when an IFC file is provided, falling
      back to ``"Solid"``.

    Layer structure::

        <layer_root>
         └── <storey name>
              ├── cut                ← section-cut curves
              │    └── IfcWall
              ├── cut_hatch          ← filled cut sections
              │    └── IfcWall
              └── projection         ← below-cut projection curves
                   └── IfcWall

    Args:
        doc:           Rhino document.  Defaults to ``RhinoDoc.ActiveDoc``.
        layer_root:    Root layer name (default ``"IFC-SVG"``).
        hatch_pattern: Default Rhino hatch pattern name for filled areas
                       (default ``"Solid"``).  Used when no per-element
                       ``EPset_IfcKit.HatchPattern`` is found.
        hatch_map:     Optional override for :data:`BONSAI_HATCH_MAP`.
    """

    #: SVG namespace map used with ``xml.etree.ElementTree``.
    _NS = _NS

    def __init__(
        self,
        doc: Any = None,
        layer_root: str = "IFC-SVG",
        hatch_map: Optional[dict] = None,
    ) -> None:
        import Rhino
        self.doc = doc if doc is not None else Rhino.RhinoDoc.ActiveDoc
        self.layer_root = layer_root
        self.hatch_map: dict[str, str] = dict(BONSAI_HATCH_MAP)
        if hatch_map:
            self.hatch_map.update(hatch_map)

        self._layer_cache: dict[str, int] = {}
        self._hatch_pattern_index: Optional[int] = None
        self._guid_hatch_index: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_file(
        self,
        ifc_path: str,
        hlr_poly: bool = True,
        mesher_deflection: Optional[float] = None,
    ) -> dict[str, int]:
        """Import curves and hatches from an IFC file.

        Args:
            ifc_path:           Path to the ``.ifc`` file.
            hlr_poly:           Use polygonal HLR (faster, Bonsai default).
                                Set ``False`` for exact BREP HLR (slower, more precise).
            mesher_deflection:  OCC mesher linear deflection in metres.
                                ``None`` = ifcopenshell default.  Try ``0.01`` for
                                a significant speedup on curved profiles.

        Returns:
            ``{"curves": int, "hatches": int}``
        """
        import ifcopenshell
        ifc_model = ifcopenshell.open(ifc_path)
        return self.import_model(ifc_model, hlr_poly=hlr_poly, mesher_deflection=mesher_deflection)

    def import_model(
        self,
        ifc_model: Any,
        hlr_poly: bool = True,
        mesher_deflection: Optional[float] = None,
    ) -> dict[str, int]:
        """Import curves and hatches from an ifcopenshell model or
        ``ifckit.IfcModel``.

        Iterates all ``IfcAnnotation[ObjectType="DRAWING"]`` in the IFC file
        and generates one SVG per drawing via ``ifcopenshell.draw`` with
        ``drawing_guid``.  Each drawing's curves are placed at ``z = 0``
        (the section plane is already encoded in the IFC annotation) and
        collected into a Rhino group named after the drawing.

        Args:
            ifc_model:          ``ifcopenshell.file`` or ``ifckit.IfcModel``.
            hlr_poly:           Use polygonal HLR (faster, Bonsai default).
                                Set ``False`` for exact BREP HLR (slower, more precise).
            mesher_deflection:  OCC mesher linear deflection in metres.
                                ``None`` = ifcopenshell default.  Try ``0.01`` for
                                a significant speedup on curved profiles.

        Returns:
            ``{"curves": int, "hatches": int}``
        """
        self._resolve_hatch_pattern()

        ifc_file = getattr(ifc_model, "ifc_file", ifc_model)
        uf = self._rhino_unit_factor()

        # Build GUID → hatch pattern index map from EPset_IfcKit.HatchPattern
        self._build_guid_hatch_map(ifc_file)

        drawings = [
            a for a in ifc_file.by_type("IfcAnnotation")
            if getattr(a, "ObjectType", None) == "DRAWING"
        ]

        if not drawings:
            import warnings
            warnings.warn("IfcSvgImporter: no DRAWING annotations found in IFC file.")
            return {"curves": 0, "hatches": 0}

        total_curves = 0
        total_hatches = 0

        import time as _time
        for ann in drawings:
            drawing_name = ann.Name or ann.GlobalId
            t0 = _time.time()
            print(f"[ifckit] generating SVG for {drawing_name!r} ...")
            svg_bytes = self._generate_svg(
                ifc_model, ann.GlobalId,
                hlr_poly=hlr_poly,
                mesher_deflection=mesher_deflection,
            )
            if not svg_bytes:
                print(f"[ifckit]   _generate_svg returned None — skipping")
                continue
            import re as _re
            n_paths = len(_re.findall(rb'<path', svg_bytes if isinstance(svg_bytes, bytes) else svg_bytes.encode()))
            print(f"[ifckit]   SVG ok: {len(svg_bytes)} bytes, {n_paths} paths  ({_time.time()-t0:.1f}s)")
            t1 = _time.time()
            result = self._process_svg(svg_bytes, drawing_name, uf)
            print(f"[ifckit]   processed: curves={result['curves']} hatches={result['hatches']}  ({_time.time()-t1:.1f}s)")
            total_curves  += result["curves"]
            total_hatches += result["hatches"]

        return {"curves": total_curves, "hatches": total_hatches}

    def clear(self) -> int:
        """Remove all objects added by this importer (tagged ``ifc_svg=1``).

        Returns:
            Number of objects removed.
        """
        to_delete = []
        for obj in self.doc.Objects:
            try:
                if obj.Attributes.GetUserString("ifc_svg") == "1":
                    to_delete.append(obj.Id)
            except Exception:
                pass
        for obj_id in to_delete:
            obj = self.doc.Objects.Find(obj_id)
            if obj:
                self.doc.Objects.Delete(obj, True)

        self._layer_cache.clear()

        root = self.doc.Layers.FindName(self.layer_root)
        if root is not None and root.Index >= 0:
            self._delete_layer_recursive(root.Index)

        return len(to_delete)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delete_layer_recursive(self, layer_index: int) -> None:
        if layer_index < 0:
            return
        children = self.doc.Layers[layer_index].GetChildren()
        for child in children or []:
            self._delete_layer_recursive(child.Index)
        self.doc.Layers.Delete(layer_index, False)

    def _resolve_hatch_pattern(self) -> None:
        """Find the Solid hatch pattern index in the document."""
        self._hatch_pattern_index = self._pattern_index_by_name("Solid")

    def _pattern_index_by_name(self, name: str) -> int:
        """Return the Rhino hatch-pattern index for *name*, or 0 as fallback."""
        for i in range(self.doc.HatchPatterns.Count):
            hp = self.doc.HatchPatterns[i]
            if hp.Name == name:
                return i
        return 0

    def _resolve_named_hatch_pattern(self, bonsai_name: str) -> int:
        """Resolve a Bonsai/ifckit hatch-pattern name to a Rhino pattern index.

        Looks up *bonsai_name* in :attr:`hatch_map` to get the Rhino name,
        then resolves to a document index.  Falls back to the default
        ``_hatch_pattern_index`` if the name is not found.

        Args:
            bonsai_name: Value of ``EPset_IfcKit.HatchPattern`` (e.g.
                ``"ANSI31"``).

        Returns:
            Rhino hatch-pattern index (int).
        """
        rhino_name = self.hatch_map.get(bonsai_name)
        if rhino_name is None:
            # Try exact Rhino name directly
            rhino_name = bonsai_name
        idx = self._pattern_index_by_name(rhino_name)
        if idx == 0 and rhino_name not in ("Solid", "solid"):
            # Pattern not found — fall back to instance default
            return self._hatch_pattern_index if self._hatch_pattern_index is not None else 0
        return idx

    def _build_guid_hatch_map(self, ifc_file: Any) -> None:
        """Populate ``_guid_hatch_index`` from ``EPset_IfcKit.HatchPattern``.

        Iterates all IFC products, reads their ``EPset_IfcKit.HatchPattern``
        property, resolves to a Rhino hatch-pattern index, and stores the
        result keyed by the product's GlobalId.  Called once per
        ``import_model`` invocation.
        """
        import ifcopenshell.util.element as ifc_util

        self._guid_hatch_index.clear()
        for product in ifc_file.by_type("IfcProduct"):
            try:
                psets = ifc_util.get_psets(product)
            except Exception:
                continue
            ep = psets.get("EPset_IfcKit", {})
            pattern_name = ep.get("HatchPattern", "")
            if pattern_name:
                self._guid_hatch_index[product.GlobalId] = (
                    self._resolve_named_hatch_pattern(pattern_name)
                )

    def _rhino_unit_factor(self) -> float:
        """Return the factor to convert metres into the Rhino document unit.

        E.g. ``1000.0`` for a millimetre document, ``1.0`` for metres.
        """
        import Rhino
        unit_map = {
            Rhino.UnitSystem.Millimeters: 1000.0,
            Rhino.UnitSystem.Centimeters: 100.0,
            Rhino.UnitSystem.Meters:      1.0,
            Rhino.UnitSystem.Feet:        3.28084,
            Rhino.UnitSystem.Inches:      39.3701,
        }
        return unit_map.get(self.doc.ModelUnitSystem, 1.0)

    def _generate_svg(
        self,
        ifc_model: Any,
        drawing_guid: str,
        hlr_poly: bool = True,
        mesher_deflection: Optional[float] = 0.01,
    ) -> Optional[bytes]:
        """Generate an in-memory SVG for a single drawing (section plane).

        Uses a bbox dot-product prefilter to split elements into cut and
        projection sets.  Cut elements go through the full HLR SVG serializer
        with ``subtract_before_hlr=True``.  Projection elements bypass HLR
        entirely — their edges are projected directly onto the drawing plane,
        which is ~100x faster for large element counts.

        The two SVG fragments are merged before being returned; ``_process_svg``
        handles both the ``<g class="section">`` groups in the combined output.

        Args:
            ifc_model:          ``ifcopenshell.file`` or ``ifckit.IfcModel``.
            drawing_guid:       GlobalId of the ``IfcAnnotation[ObjectType="DRAWING"]``
                                to render.
            hlr_poly:           Use polygonal HLR (``HLRBRep_PolyAlgo``) instead of
                                exact BREP HLR.  Polygonal is significantly faster and
                                accurate enough for technical drawings at standard
                                scales.  Default ``True`` (same as Bonsai).
            mesher_deflection:  Linear deflection for the OCC mesher used during
                                tessellation.  Smaller = finer mesh = slower HLR.
                                ``None`` uses the ifcopenshell default (~0.001 m).
                                Try ``0.01`` for a ~4× speedup on curved profiles
                                with negligible quality loss at drawing scale.
        """
        try:
            import ifcopenshell.draw as ifc_draw
            import ifcopenshell.geom as _geom
            import ifcopenshell.ifcopenshell_wrapper as _W

            ifc_file = getattr(ifc_model, "ifc_file", ifc_model)

            svg_geom = _geom.settings(ELEMENT_HIERARCHY=True, REORIENT_SHELLS=True)
            svg_geom.set("dimensionality", _W.SURFACES_AND_SOLIDS)
            svg_geom.set("iterator-output", _W.NATIVE)
            svg_geom.set("apply-default-materials", True)
            if mesher_deflection is not None:
                svg_geom.set("mesher-linear-deflection", mesher_deflection)

            settings = ifc_draw.draw_settings(
                auto_floorplan=False,
                auto_elevation=False,
                auto_section=False,
                drawing_object_type="DRAWING",
                drawing_guid=drawing_guid,
                cells=True,
                merge_cells=False,
                hlr_poly=hlr_poly,
                subtract_before_hlr=True,
                include_projection=True,
            )
            svg = ifc_draw.main(settings, files=[ifc_file])
            if isinstance(svg, bytes):
                svg = svg.decode()
            return svg.encode()

        except Exception as exc:
            import warnings
            warnings.warn(f"IfcSvgImporter: SVG generation failed for {drawing_guid!r}: {exc}")
            return None

    def _process_svg(
        self,
        svg_bytes: bytes,
        drawing_name: str,
        uf: float,
    ) -> dict[str, int]:
        """Parse SVG bytes for one drawing and add curves + hatches to Rhino.

        The section plane geometry is already encoded in the IFC annotation;
        all curves are placed at ``z = 0`` in Rhino (the drawing is in its own
        section plane coordinate system).

        Layer structure::

            <layer_root>
             └── <drawing_name>
                  ├── cut
                  │    └── IfcWall
                  ├── cut_hatch
                  │    └── IfcWall
                  └── projection
                       └── IfcWall

        All objects for the drawing are added to a Rhino group named
        ``drawing_name``.

        Args:
            svg_bytes:    Raw SVG output from ``ifcopenshell.draw``.
            drawing_name: Name used as the layer and group name.
            uf:           Rhino unit factor (metres → Rhino units).
        """
        import System
        import warnings

        root = ET.fromstring(svg_bytes)
        IFC_NS = self._NS["ifc"]

        n_curves  = 0
        n_hatches = 0
        drawing_guids: list = []

        z = 0.0  # section plane coords — Z always 0

        # The SVG may have one or more storey <g> groups; we flatten them all
        # into a single drawing layer hierarchy.
        def _handle_path(
            path_el: ET.Element,
            group_name: str,
            ifc_type: str,
            ifc_guid: str,
            transform: Optional[tuple[float, float, float]],
            default_fill: Optional[tuple[int, int, int]] = None,
            plane: Optional[list] = None,
        ) -> tuple[int, int, list]:
            d        = path_el.get("d", "")
            style    = path_el.get("style", "")
            path_cls = path_el.get("class", "")
            effective_type = path_cls if path_cls.startswith("Ifc") else ifc_type

            # Projection curves use layer colour, not material fill.
            # Fill colour is only meaningful for cut hatches.
            fill = (_parse_fill_colour(style) or default_fill) if group_name != "projection" else None
            if not d:
                return 0, 0, []

            segs = _parse_path_d(d)
            if plane is not None:
                sc, tx, ty = transform if transform is not None else (1.0, 0.0, 0.0)
                open_crvs, closed_crvs = _segments_to_rhino(segs, 0.0, sc, tx, ty, uf, plane=plane)
            elif transform is not None:
                sc, tx, ty = transform
                open_crvs, closed_crvs = _segments_to_rhino(segs, z, sc, tx, ty, uf)
            else:
                open_crvs, closed_crvs = _segments_to_rhino(segs, z, 1.0, 0.0, 0.0, uf)

            curve_layer = f"{self.layer_root}::{drawing_name}::{group_name}::{effective_type or 'Unknown'}"
            c_idx = _ensure_layer(self.doc, curve_layer, self._layer_cache)

            nc = nh = 0
            path_guids: list = []
            for crv in open_crvs + closed_crvs:
                g = self._add_curve(crv, c_idx, ifc_guid, fill)
                if g is not None:
                    path_guids.append(g)
                nc += 1

            if closed_crvs and fill is not None and group_name == "cut":
                hatch_layer = f"{self.layer_root}::{drawing_name}::cut_hatch::{effective_type or 'Unknown'}"
                h_idx = _ensure_layer(self.doc, hatch_layer, self._layer_cache)
                nh, hatch_guids = self._add_hatches(closed_crvs, h_idx, ifc_guid, fill)
                path_guids.extend(hatch_guids)

            return nc, nh, path_guids

        # Walk storey groups (ifcopenshell.draw still wraps per storey in SVG)
        # In drawing_guid mode the SVG has <g class="section"> directly under
        # root (no IfcBuildingStorey wrapper). Support both structures.
        def _process_storey_or_section(storey_g, transform, plane=None):
            nonlocal n_curves, n_hatches

            for child_g in storey_g.findall("svg:g", self._NS):
                child_cls = child_g.get("class", "")

                if child_cls in ("cut", "projection"):
                    group_name = child_cls

                    def _walk_ifc_group(g, ifc_type, ifc_guid):
                        """Recurse into nested IfcType groups (ELEMENT_HIERARCHY nesting)."""
                        nonlocal n_curves, n_hatches
                        for path_el in g.findall("svg:path", self._NS):
                            nc, nh, gs = _handle_path(path_el, group_name, ifc_type, ifc_guid, transform, plane=plane)
                            n_curves += nc; n_hatches += nh; drawing_guids.extend(gs)
                        for sub_g in g.findall("svg:g", self._NS):
                            sub_cls  = sub_g.get("class", "Unknown")
                            sub_guid = sub_g.get(f"{{{IFC_NS}}}guid", "") or ifc_guid
                            sub_type = sub_cls if sub_cls.startswith("Ifc") else ifc_type
                            _walk_ifc_group(sub_g, sub_type, sub_guid)

                    # Direct <path> children of the cut/projection group
                    for path_el in child_g.findall("svg:path", self._NS):
                        ifc_guid = path_el.get(f"{{{IFC_NS}}}guid", "")
                        ifc_type = path_el.get("class", "Unknown")
                        nc, nh, gs = _handle_path(path_el, group_name, ifc_type, ifc_guid, transform, plane=plane)
                        n_curves += nc; n_hatches += nh; drawing_guids.extend(gs)
                    # Recurse into nested IfcType groups
                    for type_g in child_g.findall("svg:g", self._NS):
                        ifc_type = type_g.get("class", "Unknown")
                        ifc_guid = type_g.get(f"{{{IFC_NS}}}guid", "")
                        _walk_ifc_group(type_g, ifc_type, ifc_guid)

                elif child_cls.startswith("Ifc"):
                    ifc_type = child_cls
                    ifc_guid = child_g.get(f"{{{IFC_NS}}}guid", "")
                    for path_el in child_g.findall("svg:path", self._NS):
                        nc, nh, gs = _handle_path(path_el, "cut", ifc_type, ifc_guid, transform, default_fill=(200, 200, 200), plane=plane)
                        n_curves += nc; n_hatches += nh; drawing_guids.extend(gs)

        for top_g in root.findall("svg:g", self._NS):
            top_cls = top_g.get("class", "")

            if top_cls == "IfcBuildingStorey":
                matrix3_attr = top_g.get(f"{{{IFC_NS}}}matrix3", "")
                transform = _parse_matrix3(matrix3_attr)
                if transform is None:
                    storey_id = top_g.get(f"{{{IFC_NS}}}name") or top_g.get("id", "?")
                    warnings.warn(
                        f"IfcSvgImporter: no ifc:matrix3 on storey '{storey_id}' "
                        f"in drawing '{drawing_name}'; using identity transform."
                    )
                _process_storey_or_section(top_g, transform)

            elif top_cls == "section":
                # drawing_guid mode: parse ifc:matrix3 and ifc:plane from this <g>
                matrix3_attr = top_g.get(f"{{{IFC_NS}}}matrix3", "")
                plane_attr   = top_g.get(f"{{{IFC_NS}}}plane", "")
                transform = _parse_matrix3(matrix3_attr)
                plane     = _parse_ifc_plane(plane_attr)
                _process_storey_or_section(top_g, transform, plane=plane)

        # Group all objects for this drawing
        if drawing_guids:
            try:
                guid_list = System.Collections.Generic.List[System.Guid]()
                for g in drawing_guids:
                    if g is not None:
                        guid_list.Add(g)
                if guid_list.Count > 0:
                    self.doc.Groups.Add(drawing_name, guid_list)
            except Exception as exc:
                warnings.warn(f"IfcSvgImporter: could not create group for '{drawing_name}': {exc}")

        return {"curves": n_curves, "hatches": n_hatches}

    # ------------------------------------------------------------------
    # Object creation
    # ------------------------------------------------------------------

    def _make_attributes(
        self,
        layer_index: int,
        ifc_guid: str,
        colour: Optional[tuple[int, int, int]],
    ) -> Any:
        """Build ``ObjectAttributes`` with layer, GUID tag and colour."""
        import Rhino
        import System.Drawing

        attrs = Rhino.DocObjects.ObjectAttributes()
        attrs.LayerIndex = layer_index
        attrs.SetUserString("ifc_svg",  "1")
        if ifc_guid:
            attrs.SetUserString("ifc_guid", ifc_guid)
        if colour is not None:
            r, g, b = colour
            attrs.ColorSource = (
                Rhino.DocObjects.ObjectColorSource.ColorFromObject
            )
            attrs.ObjectColor = System.Drawing.Color.FromArgb(255, r, g, b)
        return attrs

    def _add_curve(
        self,
        crv: Any,
        layer_index: int,
        ifc_guid: str,
        colour: Optional[tuple[int, int, int]],
    ) -> Any:
        """Add a single curve to the document.

        Returns:
            Rhino object ``Guid``, or ``None`` on failure.
        """
        attrs = self._make_attributes(layer_index, ifc_guid, colour)
        return self.doc.Objects.AddCurve(crv, attrs)

    def _add_hatches(
        self,
        boundaries: list,
        layer_index: int,
        ifc_guid: str,
        colour: tuple[int, int, int],
    ) -> int:
        """Create Rhino hatches from a list of closed boundary curves.

        Args:
            boundaries:  Closed ``Curve`` objects to use as hatch boundaries.
            layer_index: Target layer.
            ifc_guid:    IFC GUID for user-string tagging.
            colour:      RGB fill colour.

        Returns:
            Number of hatch objects successfully added.
        """
        import Rhino

        added = 0
        pat_idx = self._hatch_pattern_index if self._hatch_pattern_index is not None else 0
        # Per-element override from EPset_IfcKit.HatchPattern
        if ifc_guid and ifc_guid in self._guid_hatch_index:
            pat_idx = self._guid_hatch_index[ifc_guid]
        tol = max(self.doc.ModelAbsoluteTolerance, 0.1)

        guids: list = []
        for boundary in boundaries:
            try:
                # Rhino.Geometry.Hatch.Create silently fails for curves not on
                # the World XY plane.  Project to Z=0, create the hatch, then
                # translate it back to the original elevation.
                bbox = boundary.GetBoundingBox(True)
                z_elev = (bbox.Min.Z + bbox.Max.Z) * 0.5

                flat = boundary.Duplicate()
                flat.Transform(
                    Rhino.Geometry.Transform.Translation(0.0, 0.0, -z_elev)
                )

                hatches = Rhino.Geometry.Hatch.Create(
                    flat,
                    pat_idx,
                    0.0,
                    1.0,
                    tol,
                )
            except Exception as exc:
                import warnings
                warnings.warn(f"_add_hatches exception: {exc}")
                hatches = None

            if hatches is None or len(hatches) == 0:
                continue

            move_up = Rhino.Geometry.Transform.Translation(0.0, 0.0, z_elev)
            attrs = self._make_attributes(layer_index, ifc_guid, colour)
            for hatch in hatches:
                if hatch and hatch.IsValid:
                    hatch.Transform(move_up)
                    g = self.doc.Objects.AddHatch(hatch, attrs)
                    if g is not None:
                        guids.append(g)
                    added += 1

        return added, guids

