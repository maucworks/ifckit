"""
tests/test_element_hatch_pattern.py
====================================

Tests for EPset_IfcKit.HatchPattern written by BaseBuilder when
pending.hatch_pattern is set — M3.
"""
import pytest
import ifcopenshell.util.element as ifc_util

from ifckit.json_build import build


BASE = {
    "ifc_version": "IFC4",
    "project": {"name": "HatchTest"},
    "unit": "MILLIMETRE",
    "buildings": [
        {
            "name": "Building A",
            "storeys": [
                {
                    "name": "Ground Floor",
                    "elevation": 0.0,
                    "elements": [],
                }
            ],
        }
    ],
}

def _vec(x, y, z):
    return {"x": x, "y": y, "z": z}


_WALL = {
    "type": "basic_wall",
    "name": "W1",
    "footprint": [[0,0,0], [200,0,0], [200,300,0], [0,300,0]],
    "plane": {
        "origin": _vec(0, 0, 0),
        "x_axis": _vec(1, 0, 0),
        "y_axis": _vec(0, 1, 0),
        "z_axis": _vec(0, 0, 1),
    },
    "height": 3000.0,
}


def _build_with_wall(extra=None):
    import copy
    data = copy.deepcopy(BASE)
    wall = dict(_WALL)
    if extra:
        wall.update(extra)
    data["buildings"][0]["storeys"][0]["elements"] = [wall]
    return build(data)


def test_no_hatch_pattern_no_pset():
    model = _build_with_wall()
    wall = next(e for e in model.ifc_file.by_type("IfcWall"))
    psets = ifc_util.get_psets(wall)
    assert "EPset_IfcKit" not in psets


def test_hatch_pattern_pset_written():
    model = _build_with_wall({"hatch_pattern": "Hatch"})
    wall = next(e for e in model.ifc_file.by_type("IfcWall"))
    psets = ifc_util.get_psets(wall)
    assert psets["EPset_IfcKit"]["HatchPattern"] == "Hatch"


def test_hatch_pattern_solid():
    model = _build_with_wall({"hatch_pattern": "Solid"})
    wall = next(e for e in model.ifc_file.by_type("IfcWall"))
    psets = ifc_util.get_psets(wall)
    assert psets["EPset_IfcKit"]["HatchPattern"] == "Solid"


def test_empty_hatch_pattern_no_pset():
    """Explicitly empty string → no pset."""
    model = _build_with_wall({"hatch_pattern": ""})
    wall = next(e for e in model.ifc_file.by_type("IfcWall"))
    psets = ifc_util.get_psets(wall)
    assert "EPset_IfcKit" not in psets


def test_hatch_pattern_multiple_walls():
    """Each wall gets its own HatchPattern."""
    import copy
    data = copy.deepcopy(BASE)
    data["buildings"][0]["storeys"][0]["elements"] = [
        dict(_WALL, name="W1", hatch_pattern="Hatch"),
        dict(_WALL, name="W2", hatch_pattern="Solid"),
    ]
    model = build(data)
    walls = {w.Name: w for w in model.ifc_file.by_type("IfcWall")}
    assert ifc_util.get_psets(walls["W1"])["EPset_IfcKit"]["HatchPattern"] == "Hatch"
    assert ifc_util.get_psets(walls["W2"])["EPset_IfcKit"]["HatchPattern"] == "Solid"
