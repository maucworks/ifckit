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
1. **Keyed envelope** (from any element node)::

       {"elements": [...]}
       {"openings": [...]}
       {"doors": [...]}   etc.

2. **Storey bundle** (from ``gh_storey``)::

       {"storey_name": "GF", "elevation": 0.0, "elements": [...], ...}

3. **Full project JSON** (from ``gh_build_json``)::

       {"ifc_version": "IFC4", "project": {...}, "buildings": [...], ...}

All formats run through the 3-pass ``json_build.build()`` so openings,
doors and windows are properly subtracted/placed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Rhino guard
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
# Mesh builder
# ---------------------------------------------------------------------------


def _verts_faces_to_mesh(verts: List[float], faces: List[int], scale: float) -> Any:
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
# Normalise any input format → full project JSON dict
# ---------------------------------------------------------------------------

_STOREY_KEYS = {"elements", "openings", "doors", "windows", "door_types", "window_types"}


def _to_project_dict(d: Dict[str, Any], unit: str) -> Dict[str, Any]:
    """Wrap envelope / storey bundle / project dict in a minimal project dict."""

    # Already a full project JSON.
    if "buildings" in d and "ifc_version" in d:
        return d

    # Storey bundle: has storey_name or at least one STOREY_KEYS key + elevation.
    if "storey_name" in d or ("elements" in d and "elevation" in d):
        return _storey_bundle_to_project(d, unit)

    # Raw keyed envelope: any of the STOREY_KEYS at top level.
    if _STOREY_KEYS & set(d.keys()):
        fake_bundle: Dict[str, Any] = {
            "storey_name": "Preview",
            "elevation": 0.0,
        }
        for k in _STOREY_KEYS:
            if k in d:
                fake_bundle[k] = d[k]
        return _storey_bundle_to_project(fake_bundle, unit)

    # Single element dict (legacy — {"type": "basic_beam", ...}).
    if "type" in d:
        fake_bundle = {
            "storey_name": "Preview",
            "elevation": 0.0,
            "elements": [d],
        }
        return _storey_bundle_to_project(fake_bundle, unit)

    raise ValueError(
        "Cannot parse preview input: expected envelope, storey bundle, or project JSON."
    )


def _parse_list(lst: list) -> list:
    """Ensure each item is a dict (parse JSON strings if needed)."""
    result = []
    for e in lst or []:
        result.append(json.loads(e) if isinstance(e, str) else e)
    return result


def _storey_bundle_to_project(bundle: Dict[str, Any], unit: str) -> Dict[str, Any]:
    storey = {
        "name": bundle.get("storey_name", "Preview"),
        "elevation": float(bundle.get("elevation", 0.0)),
        "elements": _parse_list(bundle.get("elements", [])),
        "openings": _parse_list(bundle.get("openings", [])),
        "doors": _parse_list(bundle.get("doors", [])),
        "windows": _parse_list(bundle.get("windows", [])),
    }
    project: Dict[str, Any] = {
        "ifc_version": "IFC4",
        "project": {"name": "Preview", "author": "preview"},
        "unit": unit,
        "site": {"name": "Site"},
        "buildings": [{"name": "Building", "storeys": [storey]}],
    }
    # Hoist type arrays.
    if bundle.get("door_types"):
        project["door_types"] = _parse_list(bundle["door_types"])
    if bundle.get("window_types"):
        project["window_types"] = _parse_list(bundle["window_types"])
    return project


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_preview_meshes(json_str: str, unit: str = "MILLIMETRE") -> List[Any]:
    """Build ephemeral Rhino meshes from any ifckit JSON format.

    Args:
        json_str: JSON string — envelope, storey bundle, or full project JSON.
        unit:     ``"MILLIMETRE"`` (default) or ``"METRE"``.

    Returns:
        List of ``Rhino.Geometry.Mesh`` objects.

    Raises:
        ImportError: when called outside Rhino / Grasshopper.
        ValueError:  for malformed JSON or unknown element types.
    """
    _require_rhino()

    import ifcopenshell.geom

    from ifckit.json_build import build

    d = json.loads(json_str)
    project_dict = _to_project_dict(d, unit.upper())

    # Run 3-pass build — no output path → in-memory only.
    model = build(project_dict)

    # Tessellate.
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
