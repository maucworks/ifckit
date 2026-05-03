"""
ifckit.preview
==============

Build ephemeral Rhino preview meshes from ifckit element or storey JSON
**without** writing an IFC file to disk and **without** adding anything to
the Rhino document.

Requires Rhino / Grasshopper (uses ``Rhino.Geometry`` and
``ifcopenshell.geom``).

Usage (inside a GH Python Script component)::

    from ifckit.preview import build_preview_meshes
    meshes = build_preview_meshes(json_str)   # list[Rhino.Geometry.Mesh]

Supported input JSON formats
-----------------------------
1. **Collector / storey JSON** (from ``gh_collector.py``)::

       {"storey_name": "Ground Floor", "elevation": 0.0, "elements": [...]}

   Each entry in ``elements`` must be a JSON *string* (as produced by the
   beam/wall/arc GH nodes).

2. **Single element JSON string** — the raw ``json_out`` of a beam, wall or
   arc node.  Wrapped automatically in a dummy storey.

The function builds a throw-away ``IfcModel`` in memory, adds all elements,
then tessellates via ``ifcopenshell.geom.iterator`` and converts the result
to ``Rhino.Geometry.Mesh`` objects.  Nothing is written to disk; nothing is
added to ``sc.doc``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Rhino guard — module import succeeds outside Rhino; only the function call
# will fail when Rhino.Geometry is not available.
# ---------------------------------------------------------------------------
try:
    import Rhino.Geometry as _rg

    _RHINO = True
except ImportError:
    _RHINO = False


def _require_rhino() -> None:
    if not _RHINO:
        raise ImportError(
            "ifckit.preview.build_preview_meshes() requires Rhino — "
            "run inside Rhino 8 / Grasshopper."
        )


# ---------------------------------------------------------------------------
# Unit scale helper (metres → Rhino doc units)
# ---------------------------------------------------------------------------


def _doc_unit_scale() -> float:
    """Return scale factor: ifcopenshell.geom metres → Rhino doc units."""
    try:
        import Rhino
        import scriptcontext as sc

        unit_map = {
            Rhino.UnitSystem.Millimeters: 1000.0,
            Rhino.UnitSystem.Centimeters: 100.0,
            Rhino.UnitSystem.Meters: 1.0,
            Rhino.UnitSystem.Feet: 3.28084,
            Rhino.UnitSystem.Inches: 39.3701,
        }
        return unit_map.get(sc.doc.ModelUnitSystem, 1.0)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Mesh builder (same unwelded technique as IfcMeshImporter)
# ---------------------------------------------------------------------------


def _verts_faces_to_mesh(verts: List[float], faces: List[int], scale: float) -> Any:
    """Convert flat verts/faces arrays from ifcopenshell.geom to a Rhino Mesh.

    Uses unwelded vertices (one set of 3 per triangle) so that
    ``ComputeNormals()`` produces flat (hard-edge) shading rather than
    smooth interpolated normals — which is correct for architectural elements.
    """
    mesh = _rg.Mesh()
    all_verts = [verts[i : i + 3] for i in range(0, len(verts), 3)]

    vi = 0
    for i in range(0, len(faces), 3):
        a, b, c = faces[i], faces[i + 1], faces[i + 2]
        for idx in (a, b, c):
            x, y, z = all_verts[idx]
            mesh.Vertices.Add(x * scale, y * scale, z * scale)
        mesh.Faces.AddFace(vi, vi + 1, vi + 2)
        vi += 3

    mesh.Normals.ComputeNormals()
    mesh.Compact()
    return mesh


# ---------------------------------------------------------------------------
# Normalise input JSON
# ---------------------------------------------------------------------------


def _parse_input(json_str: str) -> Dict[str, Any]:
    """Return a normalised storey dict regardless of input format.

    Accepts:
    - Collector JSON:  {"storey_name": ..., "elevation": ..., "elements": [...]}
    - Element JSON:    {"type": "basic_beam", ...}  (any single element)
    """
    d = json.loads(json_str)

    # Collector / storey format
    if "elements" in d and "storey_name" in d:
        # elements are JSON strings — parse each one
        raw = d["elements"]
        parsed_elements = []
        for e in raw:
            if isinstance(e, str):
                parsed_elements.append(json.loads(e))
            elif isinstance(e, dict):
                parsed_elements.append(e)
        return {
            "storey_name": d.get("storey_name", "Preview"),
            "elevation": float(d.get("elevation", 0.0)),
            "elements": parsed_elements,
        }

    # Single element dict
    if "type" in d:
        return {
            "storey_name": "Preview",
            "elevation": 0.0,
            "elements": [d],
        }

    raise ValueError(
        "Cannot parse input JSON: expected a collector storey dict "
        '(with "storey_name" + "elements") or a single element dict (with "type").'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_preview_meshes(json_str: str, unit: str = "MILLIMETRE") -> List[Any]:
    """Build ephemeral Rhino meshes from a collector or element JSON string.

    Args:
        json_str: JSON string — either a ``gh_collector`` storey JSON or a
                  single element JSON (``json_out`` of a beam/wall/arc node).
        unit:     Length unit used in the input JSON coordinates.
                  ``"MILLIMETRE"`` (default) or ``"METRE"``.  Must match the
                  unit setting in ``gh_build_json`` for this project.

    Returns:
        List of ``Rhino.Geometry.Mesh`` objects.  Empty list if no geometry
        could be tessellated.

    Raises:
        ImportError: when called outside Rhino / Grasshopper.
        ValueError:  for malformed JSON or unknown element types.
    """
    _require_rhino()

    import ifcopenshell.geom

    from ifckit.elements.registry import ElementRegistry
    from ifckit.model import IfcModel
    from ifckit.schema import IfcSchema, LengthUnit

    storey_data = _parse_input(json_str)

    ifc_unit = LengthUnit.MILLIMETRE if unit.upper() == "MILLIMETRE" else LengthUnit.METRE

    # ------------------------------------------------------------------
    # Build a throw-away IfcModel in memory
    # ------------------------------------------------------------------
    model = IfcModel(name="Preview", schema=IfcSchema.IFC4, unit=ifc_unit)
    site = model.add_site("PreviewSite")
    building = site.add_building("PreviewBuilding")
    storey = building.add_storey(
        storey_data["storey_name"],
        elevation=storey_data["elevation"],
    )

    errors: List[str] = []
    built = 0

    for elem_dict in storey_data["elements"]:
        elem_type = elem_dict.get("type")
        # Support both {"type": ..., "data": {...}} and flat {"type": ..., ...}
        data = elem_dict.get("data", elem_dict)
        try:
            cls = ElementRegistry.get(elem_type)
            pending = cls.from_dict(data)
            storey.add(pending)
            built += 1
        except Exception as exc:
            errors.append(f"{elem_type}: {exc}")

    if built == 0:
        return []

    # ------------------------------------------------------------------
    # Tessellate via ifcopenshell.geom (no disk I/O)
    # ------------------------------------------------------------------
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    scale = _doc_unit_scale()
    meshes: List[Any] = []

    iterator = ifcopenshell.geom.iterator(settings, model.ifc_file)
    if iterator.initialize():
        while True:
            shape = iterator.get()
            geom = shape.geometry
            if geom.verts and geom.faces:
                meshes.append(_verts_faces_to_mesh(geom.verts, geom.faces, scale))
            if not iterator.next():
                break

    return meshes
