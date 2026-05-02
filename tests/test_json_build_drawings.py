"""
tests/test_json_build_drawings.py
==================================

Tests for drawings[] key in json_build.
Each drawing is a section plane: origin + x_axis + z_axis (view direction).
"""
import pytest
import ifcopenshell.util.element as ifc_util

from ifckit.json_build import build


BASE_JSON = {
    "ifc_version": "IFC4",
    "project": {"name": "DrawingsTest"},
    "unit": "MILLIMETRE",
    "buildings": [
        {
            "name": "Building A",
            "storeys": [
                {"name": "Ground Floor", "elevation": 0.0,    "elements": []},
                {"name": "Level 1",      "elevation": 3000.0, "elements": []},
            ],
        }
    ],
}


def _with_drawings(drawings):
    data = dict(BASE_JSON)
    data["drawings"] = drawings
    return data


def test_no_drawings_key():
    """No drawings key → no IfcAnnotation created."""
    model = build(BASE_JSON)
    anns = [a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING"]
    assert len(anns) == 0


def test_empty_drawings_list():
    model = build(_with_drawings([]))
    anns = [a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING"]
    assert len(anns) == 0


def test_single_drawing_created():
    data = _with_drawings([
        {"name": "Section A-A", "origin": [0.0, 5000.0, 0.0], "z_axis": [0.0, -1.0, 0.0]}
    ])
    model = build(data)
    anns = [a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING"]
    assert len(anns) == 1
    assert anns[0].Name == "Section A-A"


def test_drawing_origin():
    data = _with_drawings([
        {"name": "Plan", "origin": [0.0, 0.0, 1200.0]}
    ])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    coords = ann.ObjectPlacement.RelativePlacement.Location.Coordinates
    assert abs(coords[0] - 0.0)    < 1e-3
    assert abs(coords[1] - 0.0)    < 1e-3
    assert abs(coords[2] - 1200.0) < 1e-3


def test_drawing_origin_xyz():
    data = _with_drawings([
        {"name": "Section B", "origin": [500.0, 250.0, 0.0], "z_axis": [0.0, -1.0, 0.0]}
    ])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    coords = ann.ObjectPlacement.RelativePlacement.Location.Coordinates
    assert abs(coords[0] - 500.0) < 1e-3
    assert abs(coords[1] - 250.0) < 1e-3
    assert abs(coords[2] - 0.0)   < 1e-3


def test_drawing_z_axis_stored():
    """z_axis (0,-1,0) → IFC placement Axis is negated: (0,+1,0)."""
    data = _with_drawings([
        {"name": "Section A-A",
         "origin": [0.0, 5000.0, 0.0],
         "z_axis": [0.0, -1.0, 0.0],
         "x_axis": [1.0,  0.0, 0.0]}
    ])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    axis = ann.ObjectPlacement.RelativePlacement.Axis
    assert axis is not None
    assert abs(axis.DirectionRatios[0]) < 1e-9
    assert abs(axis.DirectionRatios[1] - 1.0) < 1e-9   # negated
    assert abs(axis.DirectionRatios[2]) < 1e-9


def test_drawing_x_axis_stored():
    """x_axis is stored as RefDirection."""
    data = _with_drawings([
        {"name": "Section B-B",
         "origin": [3000.0, 0.0, 0.0],
         "z_axis": [-1.0, 0.0, 0.0],
         "x_axis": [0.0,  1.0, 0.0]}
    ])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    ref = ann.ObjectPlacement.RelativePlacement.RefDirection
    assert ref is not None
    assert abs(ref.DirectionRatios[0]) < 1e-9
    assert abs(ref.DirectionRatios[1] - 1.0) < 1e-9
    assert abs(ref.DirectionRatios[2]) < 1e-9


def test_drawing_defaults_origin_zero():
    """No origin → (0, 0, 0)."""
    data = _with_drawings([{"name": "Plan"}])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    coords = ann.ObjectPlacement.RelativePlacement.Location.Coordinates
    assert all(abs(c) < 1e-3 for c in coords)


def test_drawing_defaults_z_axis_down():
    """No z_axis → default (0,0,-1) view dir → IFC Axis negated to (0,0,+1)."""
    data = _with_drawings([{"name": "Plan"}])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    axis = ann.ObjectPlacement.RelativePlacement.Axis
    assert abs(axis.DirectionRatios[2] - 1.0) < 1e-9   # negated


def test_drawing_target_view_default():
    data = _with_drawings([{"name": "Plan", "origin": [0.0, 0.0, 1200.0]}])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    psets = ifc_util.get_psets(ann)
    assert psets["EPset_Drawing"]["TargetView"] == "PLAN_VIEW"


def test_drawing_target_view_explicit():
    data = _with_drawings([
        {"name":        "Section A",
         "origin":      [0.0, 5000.0, 0.0],
         "z_axis":      [0.0, -1.0, 0.0],
         "target_view": "SECTION_VIEW"}
    ])
    model = build(data)
    ann = next(a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING")
    psets = ifc_util.get_psets(ann)
    assert psets["EPset_Drawing"]["TargetView"] == "SECTION_VIEW"


def test_multiple_drawings():
    data = _with_drawings([
        {"name": "GF Plan",   "origin": [0.0, 0.0, 1200.0]},
        {"name": "Section A", "origin": [0.0, 5000.0, 0.0], "z_axis": [0.0, -1.0, 0.0]},
    ])
    model = build(data)
    anns = [a for a in model.ifc_file.by_type("IfcAnnotation") if a.ObjectType == "DRAWING"]
    assert len(anns) == 2
    names = {a.Name for a in anns}
    assert names == {"GF Plan", "Section A"}


def test_drawing_group_created():
    data = _with_drawings([
        {"name": "Section A-A", "origin": [0.0, 5000.0, 0.0], "z_axis": [0.0, -1.0, 0.0]}
    ])
    model = build(data)
    groups = [g for g in model.ifc_file.by_type("IfcGroup") if g.ObjectType == "DRAWING"]
    assert len(groups) == 1
    assert groups[0].Name == "Section A-A"


