"""IfcSpaceImporter — import IfcSpace entities into Rhino."""

from __future__ import annotations

from typing import Any

from ifckit.rhino_import._helpers import (
    MESH_QUALITY,
    _delete_layer_recursive,
    _ensure_layer,
)

# ---------------------------------------------------------------------------
# IfcSpaceImporter
# ---------------------------------------------------------------------------


class IfcSpaceImporter:
    """Import ``IfcSpace`` entities from an IFC file into Rhino.

    For each space this importer can create:

    * **2-D footprint curves** on a per-storey layer hierarchy.
    * **Hatch fills** using the space's ``RenderStyle`` colour (or a
      configurable default colour).
    * **TextDot annotations** with space name, long name and area.
    * **3-D mesh body** via ``ifcopenshell.geom.iterator``
      (same pipeline as ``IfcMeshImporter``).

    Layer hierarchy::

        IFC-Spaces
         └── <StoreyName>
              ├── footprint   ← 2-D boundary curves
              ├── hatch       ← filled hatches
              ├── annotation  ← TextDot labels
              └── mesh        ← 3-D mesh bodies

    Args:
        doc:             Rhino document.  Defaults to ``RhinoDoc.ActiveDoc``.
        layer_root:      Root layer name.  Default ``"IFC-Spaces"``.
        default_color:   ``System.Drawing.Color`` used when the space has no
                         ``RenderStyle``.  Default: light yellow.
        hatch_pattern:   Rhino hatch pattern name for all spaces.
                         Default ``"Solid"``.
        import_footprint: Draw 2-D footprint curves.  Default ``True``.
        import_hatch:    Draw hatch fills.  Default ``True``.
        import_annotation: Draw TextDot labels.  Default ``True``.
        import_mesh:     Tessellate and draw 3-D bodies.  Default ``False``.
        mesh_quality:    Tessellation quality preset for mesh bodies.
                         One of ``superfine/fine/default/coarse/supercoarse``.
    """

    def __init__(
        self,
        doc: Any = None,
        layer_root: str = "IFC-Spaces",
        default_color: Any = None,
        hatch_pattern: str = "Solid",
        import_footprint: bool = True,
        import_hatch: bool = True,
        import_annotation: bool = True,
        import_mesh: bool = False,
        mesh_quality: str = "default",
    ) -> None:
        import Rhino
        import System.Drawing

        self.doc = doc if doc is not None else Rhino.RhinoDoc.ActiveDoc
        self.layer_root = layer_root
        self.default_color = (
            default_color
            if default_color is not None
            else System.Drawing.Color.FromArgb(255, 255, 220)
        )
        self.hatch_pattern = hatch_pattern
        self.import_footprint = import_footprint
        self.import_hatch = import_hatch
        self.import_annotation = import_annotation
        self.import_mesh = import_mesh
        if mesh_quality not in MESH_QUALITY:
            raise ValueError(f"mesh_quality must be one of {list(MESH_QUALITY)}")
        self._mesh_linear_defl, self._mesh_angular_defl = MESH_QUALITY[mesh_quality]
        self._layer_cache: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_file(self, ifc_path: str) -> dict:
        """Import all ``IfcSpace`` entities from *ifc_path* into Rhino.

        Args:
            ifc_path: Absolute path to the ``.ifc`` file.

        Returns:
            Dict with keys ``"spaces"``, ``"footprints"``, ``"hatches"``,
            ``"annotations"``, ``"meshes"``.
        """
        import ifcopenshell

        ifc = ifcopenshell.open(ifc_path)
        return self._import_ifc(ifc)

    def import_model(self, model: Any) -> dict:
        """Import ``IfcSpace`` entities from an ``IfcModel`` instance.

        Args:
            model: ``ifckit.model.IfcModel`` instance.

        Returns:
            Same dict as :meth:`import_file`.
        """
        return self._import_ifc(model._file)

    def clear(self) -> int:
        """Remove all objects on layers under *layer_root*.

        Returns:
            Number of objects deleted.
        """

        root_idx = self.doc.Layers.FindByFullPath(self.layer_root, -1)
        if root_idx < 0:
            return 0
        removed = _delete_layer_recursive(self.doc, root_idx)
        self._layer_cache.clear()
        return removed

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _import_ifc(self, ifc: Any) -> dict:
        import Rhino
        import Rhino.Geometry as rg

        spaces = ifc.by_type("IfcSpace")
        if not spaces:
            return {"spaces": 0, "footprints": 0, "hatches": 0, "annotations": 0, "meshes": 0}

        uf = self._unit_factor(ifc)

        n_footprints = 0
        n_hatches = 0
        n_annotations = 0
        n_meshes = 0

        for space in spaces:
            storey_name = self._storey_name(space)
            name = space.Name or ""
            long_name = getattr(space, "LongName", None) or ""
            color = self._space_color(space)

            # Layer paths
            fp_layer = f"{self.layer_root}::{storey_name}::footprint"
            ht_layer = f"{self.layer_root}::{storey_name}::hatch"
            ann_layer = f"{self.layer_root}::{storey_name}::annotation"
            mesh_layer = f"{self.layer_root}::{storey_name}::mesh"

            # Footprint curves
            pts = self._footprint_points(space, uf)
            if pts and self.import_footprint:
                curve = self._pts_to_curve(pts)
                if curve is not None:
                    idx = _ensure_layer(self.doc, fp_layer, self._layer_cache)
                    attr = Rhino.DocObjects.ObjectAttributes()
                    attr.LayerIndex = idx
                    self.doc.Objects.AddCurve(curve, attr)
                    n_footprints += 1

            # Hatch
            if pts and self.import_hatch:
                area = self._polygon_area(pts)
                n_hatches += self._add_hatch(pts, ht_layer, color)

            # TextDot annotation
            if pts and self.import_annotation:
                cx, cy = self._centroid(pts)
                area = self._polygon_area(pts)
                area_uf = uf * uf  # length² → area unit conversion
                area_m2 = area / area_uf  # footprint pts are in Rhino units
                label_parts = [p for p in [name, long_name] if p]
                label_parts.append(f"{area_m2:.1f} m²")
                label = "\n".join(label_parts)
                dot = rg.TextDot(label, rg.Point3d(cx, cy, 0.0))
                idx = _ensure_layer(self.doc, ann_layer, self._layer_cache)
                attr = Rhino.DocObjects.ObjectAttributes()
                attr.LayerIndex = idx
                self.doc.Objects.AddTextDot(dot, attr)
                n_annotations += 1

            # 3-D mesh
            if self.import_mesh:
                n_meshes += self._add_mesh(ifc, space, mesh_layer, uf)

        return {
            "spaces": len(spaces),
            "footprints": n_footprints,
            "hatches": n_hatches,
            "annotations": n_annotations,
            "meshes": n_meshes,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unit_factor(self, ifc: Any) -> float:
        """Return scale factor: IFC file units → Rhino document units."""
        import ifcopenshell.util.unit as ifc_unit
        import Rhino

        rhino_unit = self.doc.ModelUnitSystem
        unit_map = {
            Rhino.UnitSystem.Millimeters: 1000.0,
            Rhino.UnitSystem.Centimeters: 100.0,
            Rhino.UnitSystem.Meters: 1.0,
            Rhino.UnitSystem.Feet: 3.28084,
            Rhino.UnitSystem.Inches: 39.3701,
        }
        rhino_factor = unit_map.get(rhino_unit, 1.0)
        try:
            prefix = ifc_unit.get_prefix_multiplier(
                ifc_unit.get_project_unit(ifc, "LENGTHUNIT").Prefix
            )
        except Exception:
            prefix = 1.0
        return (prefix or 1.0) * rhino_factor

    def _storey_name(self, space: Any) -> str:
        """Return the containing storey name for a space, or 'Unknown'."""
        try:
            for rel in space.Decomposes or []:
                obj = rel.RelatingObject
                if obj.is_a("IfcBuildingStorey"):
                    return obj.Name or "Storey"
        except Exception:
            pass
        try:
            for rel in space.ContainedInStructure or []:
                obj = rel.RelatingStructure
                if obj.is_a("IfcBuildingStorey"):
                    return obj.Name or "Storey"
        except Exception:
            pass
        return "Unknown"

    def _space_color(self, space: Any) -> Any:
        """Return ``System.Drawing.Color`` for a space from its style pset or default."""
        import System.Drawing

        try:
            for rel in space.IsDefinedBy or []:
                if not rel.is_a("IfcRelDefinesByProperties"):
                    continue
                pset = rel.RelatingPropertyDefinition
                if not hasattr(pset, "HasProperties"):
                    continue
                for prop in pset.HasProperties:
                    if prop.Name == "Color" and hasattr(prop, "NominalValue"):
                        val = prop.NominalValue.wrappedValue
                        # Expect "R,G,B" string
                        parts = str(val).split(",")
                        if len(parts) == 3:
                            r, g, b = (int(p.strip()) for p in parts)
                            return System.Drawing.Color.FromArgb(r, g, b)
        except Exception:
            pass
        return self.default_color

    def _footprint_points(self, space: Any, uf: float) -> list:
        """Extract 2-D footprint polygon from IfcSpace geometry (world XY).

        Returns a list of ``(x, y)`` tuples in Rhino document units, or ``[]``
        if no footprint can be extracted.
        """
        try:
            import ifcopenshell.geom

            s = ifcopenshell.geom.settings()
            s.set(s.USE_WORLD_COORDS, True)
            shape = ifcopenshell.geom.create_shape(s, space)
            verts = shape.geometry.verts  # flat list x0,y0,z0, x1,y1,z1, …
            faces = shape.geometry.faces  # noqa: F841 flat list of triangle indices

            # Find the lowest Z face (floor boundary) as the footprint.
            pts3 = [
                (verts[i * 3] * uf, verts[i * 3 + 1] * uf, verts[i * 3 + 2] * uf)
                for i in range(len(verts) // 3)
            ]

            if not pts3:
                return []

            min_z = min(p[2] for p in pts3)
            floor_pts = [(p[0], p[1]) for p in pts3 if abs(p[2] - min_z) < 1e-3 * uf]

            # Deduplicate while preserving rough order (convex hull order not needed).
            seen = set()
            unique = []
            for p in floor_pts:
                key = (round(p[0], 4), round(p[1], 4))
                if key not in seen:
                    seen.add(key)
                    unique.append(p)

            return unique if len(unique) >= 3 else []

        except Exception:
            return []

    def _pts_to_curve(self, pts: list) -> Any:
        """Convert (x,y) list to a closed Rhino NurbsCurve."""
        import Rhino.Geometry as rg

        rhino_pts = [rg.Point3d(x, y, 0.0) for x, y in pts]
        rhino_pts.append(rhino_pts[0])  # close
        return rg.NurbsCurve.CreateFromPoints(rhino_pts, degree=1)

    def _polygon_area(self, pts: list) -> float:
        """Shoelace area of a 2-D polygon [(x,y), …] (absolute value)."""
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return abs(area) / 2.0

    def _centroid(self, pts: list) -> tuple:
        """Return the centroid (cx, cy) of a polygon."""
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return cx, cy

    def _add_hatch(self, pts: list, layer_path: str, color: Any) -> int:
        """Add a hatch fill for a footprint polygon.  Returns 1 on success."""
        import Rhino
        import Rhino.Geometry as rg

        try:
            curve = self._pts_to_curve(pts)
            if curve is None or not curve.IsValid:
                return 0

            hp_index = self.doc.HatchPatterns.Find(self.hatch_pattern, True)
            if hp_index < 0:
                hp_index = 0  # fallback to first pattern

            hatches = rg.Hatch.Create(curve, hp_index, 0.0, 1.0, 1e-6)
            if not hatches:
                return 0

            idx = _ensure_layer(self.doc, layer_path, self._layer_cache)
            attr = Rhino.DocObjects.ObjectAttributes()
            attr.LayerIndex = idx
            attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            attr.ObjectColor = color

            for h in hatches:
                if h and h.IsValid:
                    self.doc.Objects.AddHatch(h, attr)
            return 1
        except Exception:
            return 0

    def _add_mesh(self, ifc: Any, space: Any, layer_path: str, uf: float) -> int:
        """Tessellate and add the 3-D mesh body of a space.  Returns 1 on success."""
        import Rhino
        import Rhino.Geometry as rg

        try:
            import ifcopenshell.geom

            s = ifcopenshell.geom.settings()
            s.set(s.USE_WORLD_COORDS, True)
            s.set(s.WELD_VERTICES, True)

            shape = ifcopenshell.geom.create_shape(s, space)
            verts = shape.geometry.verts
            faces = shape.geometry.faces

            mesh = rg.Mesh()
            for i in range(0, len(verts), 3):
                mesh.Vertices.Add(
                    verts[i] * uf,
                    verts[i + 1] * uf,
                    verts[i + 2] * uf,
                )
            for i in range(0, len(faces), 3):
                mesh.Faces.AddFace(faces[i], faces[i + 1], faces[i + 2])
            mesh.Normals.ComputeNormals()

            if not mesh.IsValid:
                return 0

            idx = _ensure_layer(self.doc, layer_path, self._layer_cache)
            attr = Rhino.DocObjects.ObjectAttributes()
            attr.LayerIndex = idx
            self.doc.Objects.AddMesh(mesh, attr)
            return 1
        except Exception:
            return 0
