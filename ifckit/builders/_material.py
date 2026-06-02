"""
ifckit.builders._material
=========================

Material / IfcStyledItem helpers for builder geometry.
"""

from __future__ import annotations

from typing import Optional

import ifcopenshell


def apply_material_to_solid(
    ifc_file: ifcopenshell.file,
    solid: ifcopenshell.entity_instance,
    material_def: Optional[dict],
) -> ifcopenshell.entity_instance:
    """
    Create an IfcStyledItem referencing the solid with color and transparency.

    The IfcStyledItem is created as a standalone entity in the file — it must
    NOT replace the solid in the representation Items list, because SweptSolid
    representations require raw solids as items. Returns the original solid
    unchanged so callers can safely append it to the items list.

    Args:
        ifc_file: IFC file object
        solid: IfcExtrudedAreaSolid or similar representation item
        material_def: Dict with keys:
            - color: {"r": 0.0-1.0, "g": 0.0-1.0, "b": 0.0-1.0}
            - transparency: 0.0-1.0 (0=transparent, 1=opaque)
            - name: optional material name

    Returns:
        The original solid (unchanged).
    """
    if not material_def:
        return solid

    color_def = material_def.get("color", {})
    transparency = material_def.get("transparency", 1.0)
    name = material_def.get("name", "")

    color = ifc_file.create_entity(
        "IfcColourRgb",
        Red=float(color_def.get("r", 1.0)),
        Green=float(color_def.get("g", 1.0)),
        Blue=float(color_def.get("b", 1.0)),
    )

    shading = ifc_file.create_entity(
        "IfcSurfaceStyleRendering",
        SurfaceColour=color,
        Transparency=float(transparency),
        ReflectanceMethod="FLAT",
    )

    # Create a surface style to contain the rendering
    surface_style = ifc_file.create_entity(
        "IfcSurfaceStyle",
        Name=name or "ComponentFill",
        Side="BOTH",
        Styles=[shading],
    )

    # Create IfcStyledItem referencing the solid and style
    ifc_file.create_entity(
        "IfcStyledItem",
        Item=solid,
        Styles=[surface_style],
    )

    return solid


__all__ = [
    "apply_material_to_solid",
]
