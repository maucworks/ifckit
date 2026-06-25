"""
ifckit.draw
===========

SVG-based IFC model visualisation and export utilities.
"""

import xml.etree.ElementTree as ET
from typing import Optional

import ifcopenshell.draw as ifc_draw
import ifcopenshell.geom as _geom
import ifcopenshell.ifcopenshell_wrapper as _W
import ifcopenshell.util.placement as placement_util

from ifckit.draw._svg import curves_to_svg_d, parse_matrix3, parse_plane_attr
from ifckit.geometry import Plane, Vec
from ifckit.types.footprint import Footprint

_NS = {
    "svg": "http://www.w3.org/2000/svg",
    "ifc": "http://www.ifcopenshell.org/ns",
}

_IFC_NS = "http://www.ifcopenshell.org/ns"

ET.register_namespace("ifc", _IFC_NS)


def generate_svg(
    ifc_model,
    drawing_guid: str = "",
    *,
    door_arcs: bool = True,
    include_curves: bool = True,
    include_projection: bool = True,
    hlr_poly: bool = True,
    mesher_deflection: Optional[float] = 0.01,
    scale: float = 1.0 / 100.0,
    drawing_object_type: str = "DRAWING",
) -> bytes:
    """Generate an SVG visualisation of an IFC model."""
    ifc_file = getattr(ifc_model, "ifc_file", ifc_model)

    svg_geom = _geom.settings(ELEMENT_HIERARCHY=True, REORIENT_SHELLS=True)
    if include_curves:
        svg_geom.set("dimensionality", _W.CURVES_SURFACES_AND_SOLIDS)
    else:
        svg_geom.set("dimensionality", _W.SURFACES_AND_SOLIDS)
    svg_geom.set("iterator-output", _W.NATIVE)
    svg_geom.set("apply-default-materials", True)
    if mesher_deflection is not None:
        svg_geom.set("mesher-linear-deflection", mesher_deflection)

    settings = ifc_draw.draw_settings(
        auto_floorplan=False,
        auto_elevation=False,
        auto_section=False,
        drawing_object_type=drawing_object_type,
        drawing_guid=drawing_guid,
        cells=True,
        merge_cells=False,
        door_arcs=door_arcs,
        hlr_poly=hlr_poly,
        subtract_before_hlr=True,
        include_projection=include_projection,
    )

    svg = ifc_draw.main(settings, files=[ifc_file])
    if isinstance(svg, str):
        svg = svg.encode()
    return svg


def _ifc_unit_factor(ifc_file) -> float:
    import ifcopenshell.util.unit as unit_util

    try:
        lu = unit_util.get_project_unit(ifc_file, "LENGTHUNIT")
        prefix = getattr(lu, "Prefix", None)
        if prefix:
            return unit_util.get_prefix_multiplier(prefix)
    except Exception:
        pass
    return 1.0


def inject_symbols(svg_bytes: bytes, ifc_file) -> bytes:
    """Inject SVG marker/arrowhead definitions."""
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("ifc", _IFC_NS)

    root = ET.fromstring(svg_bytes)

    transform_g = None
    for candidate_g in root.findall(".//{http://www.w3.org/2000/svg}g"):
        m3 = candidate_g.get(f"{{{_IFC_NS}}}matrix3", "")
        if m3:
            transform_g = candidate_g
            break
    if transform_g is None:
        return svg_bytes

    matrix3_attr = transform_g.get(f"{{{_IFC_NS}}}matrix3", "")
    plane_attr = transform_g.get(f"{{{_IFC_NS}}}plane", "")
    if not matrix3_attr:
        return svg_bytes

    svg_transform = parse_matrix3(matrix3_attr)
    if svg_transform is None:
        return svg_bytes
    sc, tx, ty = svg_transform

    plane_mat = parse_plane_attr(plane_attr)
    svg_ns = "http://www.w3.org/2000/svg"
    uf = _ifc_unit_factor(ifc_file)

    projection_g = transform_g.find("svg:g[@class='projection']", _NS)
    if projection_g is None:
        projection_g = transform_g.find(".//{http://www.w3.org/2000/svg}g[@class='projection']")
    if projection_g is None:
        projection_g = ET.SubElement(transform_g, f"{{{svg_ns}}}g")
        projection_g.set("class", "projection")

    count = 0
    for door in ifc_file.by_type("IfcDoor"):
        try:
            leaf_w = door.OverallWidth
        except (AttributeError, TypeError):
            continue
        if not leaf_w or leaf_w <= 0:
            continue

        try:
            door_mat = placement_util.get_local_placement(door.ObjectPlacement)
        except Exception:
            continue

        origin_m = Vec(
            door_mat[0, 3] * uf,
            door_mat[1, 3] * uf,
            door_mat[2, 3] * uf,
        )
        x_axis = Vec(*door_mat[:3, 0])
        swing_dir = Vec(*door_mat[:3, 2])
        world_plane = Plane(origin_m, x_axis, swing_dir)

        curves = Footprint.door_swing(world_plane, leaf_w * uf)
        d_str = curves_to_svg_d(curves, plane_mat, (sc, tx, ty))
        if not d_str:
            continue

        path_el = ET.SubElement(projection_g, f"{{{svg_ns}}}path")
        path_el.set("d", d_str)
        path_el.set("class", "IfcDoor")
        path_el.set(f"{{{_IFC_NS}}}guid", door.GlobalId)
        path_el.set("style", "fill:none;stroke:red;stroke-dasharray:4,2")
        count += 1

    if count == 0:
        return svg_bytes

    svg_bytes_out = ET.tostring(root, xml_declaration=True, encoding="unicode")
    return svg_bytes_out.encode()


def save_svg(svg_bytes: bytes, path: str) -> None:
    """Save an SVG string to a file."""
    with open(path, "wb") as f:
        f.write(svg_bytes)
