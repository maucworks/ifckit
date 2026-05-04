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


def build_preview_meshes(
    json_str: str, unit: str = "MILLIMETRE", skip_voids: bool = False
) -> List[Any]:
    """Build ephemeral Rhino meshes from any ifckit JSON format.

    Args:
        json_str:    JSON string — envelope, storey bundle, or full project JSON.
        unit:        ``"MILLIMETRE"`` (default) or ``"METRE"``.
        skip_voids:  If True, skip IfcOpeningElement geometry.

    Returns:
        List of ``Rhino.Geometry.Mesh`` objects.
    """
    return build_preview_meshes_merged([json_str], unit=unit, skip_voids=skip_voids)


def build_preview_meshes_merged(
    json_strs: List[str], unit: str = "MILLIMETRE", skip_voids: bool = False
) -> List[Any]:
    """Build ephemeral Rhino meshes from multiple ifckit JSON strings.

    All inputs are merged via ``rhinokit.merge_envelopes`` before building,
    so that ``window_types`` / ``door_types`` defined in a storey bundle are
    visible to openings that reference them via ``type_ref``, regardless of
    input order.

    Args:
        json_strs:   List of JSON strings (envelopes, storey bundles, or
                     full project JSONs).  A single string is also accepted.
        unit:        ``"MILLIMETRE"`` (default) or ``"METRE"``.
        skip_voids:  If True, skip IfcOpeningElement geometry.

    Returns:
        List of ``Rhino.Geometry.Mesh`` objects.

    Raises:
        ImportError: when called outside Rhino / Grasshopper.
        ValueError:  for malformed JSON or unknown element types.
    """
    _require_rhino()

    import ifcopenshell.geom

    from ifckit.json_build import build
    from ifckit.rhinokit import merge_envelopes

    # Normalise to list of strings.
    if isinstance(json_strs, str):
        json_strs = [json_strs]

    # Separate full project JSONs from envelopes/bundles.
    # A full project JSON goes straight to build(); everything else is merged.
    project_dict = None
    envelope_strs: List[str] = []

    for s in json_strs:
        if not s:
            continue
        d = json.loads(s)
        if "buildings" in d and "ifc_version" in d:
            # Already a full project — use as-is (last one wins).
            project_dict = d
        else:
            envelope_strs.append(s)

    if project_dict is None:
        if not envelope_strs:
            return []
        merged = merge_envelopes(envelope_strs)
        project_dict = _to_project_dict(merged, unit.upper())
    elif envelope_strs:
        # Envelopes alongside a full project dict — rare, ignore envelopes.
        pass

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
            entity = model.ifc_file.by_guid(shape.guid)
            entity_type = entity.is_a() if entity else None
            if skip_voids and entity_type == "IfcOpeningElement":
                if not iterator.next():
                    break
                continue
            geom = shape.geometry
            if geom.verts and geom.faces:
                mesh = _verts_faces_to_mesh(geom.verts, geom.faces, scale)
                meshes.append(mesh)
            if not iterator.next():
                break
    return meshes
