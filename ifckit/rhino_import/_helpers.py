"""Shared utility functions for ifckit.rhino_import submodules."""

from __future__ import annotations

from typing import Any, Optional

# (linear_deflection, angular_deflection)
# linear_deflection: max chord deviation in metres
# angular_deflection: max angle between facet normals in radians
MESH_QUALITY: dict[str, tuple[float, float]] = {
    "superfine": (0.0001, 0.05),  # ~2.9°  — slowest, highest fidelity
    "fine": (0.0005, 0.1),  # ~5.7°
    "default": (0.001, 0.5),  # ~28.6° — ifcopenshell default
    "coarse": (0.005, 1.0),  # ~57.3°
    "supercoarse": (0.01, 1.5),  # ~85.9° — fastest, lowest fidelity
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
    if name.endswith("y") and name[-2] not in "aeiou":
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

        # Layer may already exist (e.g. from a previous run); find it first.
        existing = doc.Layers.FindByFullPath(current_path, -1)
        if existing >= 0:
            index = existing
        else:
            index = doc.Layers.Add(layer)
        if index < 0:
            raise RuntimeError(f"Failed to create Rhino layer: {current_path!r}")
        cache[current_path] = index

    result = cache[path]
    return result if result >= 0 else 0


def _delete_layer_recursive(doc: Any, layer_index: int) -> None:
    """Recursively delete a Rhino layer and all its children.

    Args:
        doc:         Rhino document (``RhinoDoc``).
        layer_index: Index of the layer to delete.  No-op when negative.
    """
    if layer_index < 0:
        return
    children = doc.Layers[layer_index].GetChildren()
    for child in children or []:
        _delete_layer_recursive(doc, child.Index)
    doc.Layers.Delete(layer_index, False)


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
