"""
tests/test_json_build_openings.py
==================================

Tests for the 2-pass JSON build (Model B):
  - validate_json: structure checks for window/door fills nested in elements
  - build: wall + window/door via component_graph
  - type_ref resolution errors
  - round-trip save/reopen
"""

import json
import pytest

from ifckit.json_build import build, validate_json


# ---------------------------------------------------------------------------
# Minimal valid base fixture
# ---------------------------------------------------------------------------

_BASE = {
    "ifc_version": "IFC4",
    "project": {"name": "TestProject"},
    "unit": "METRE",
    "buildings": [
        {
            "name": "B1",
            "storeys": [
                {
                    "name": "GF",
                    "elevation": 0.0,
                    "elements": [],
                }
            ],
        }
    ],
}


def _vec(x, y, z):
    return {"x": x, "y": y, "z": z}


def _plane(ox, oy, oz, xx=1, xy=0, xz=0, yx=0, yy=0, yz=1):
    """Default y_axis = (0,0,1) — vertical, correct for wall inserts."""
    return {"origin": _vec(ox, oy, oz), "x_axis": _vec(xx, xy, xz), "y_axis": _vec(yx, yy, yz)}


_WALL_FOOTPRINT = [
    [0, 0, 0], [5, 0, 0], [5, 0.2, 0], [0, 0.2, 0],
]
_WALL_PLANE = {"origin": _vec(0, 0, 0), "x_axis": _vec(1, 0, 0), "y_axis": _vec(0, 1, 0)}

_WALL_ELEM = {
    "id": "w1",
    "type": "basic_wall",
    "footprint": _WALL_FOOTPRINT,
    "plane": _WALL_PLANE,
    "height": 3.0,
}

_WIN_PLANE = _plane(1.0, 0.0, 0.5)

_WIN_FILL = {
    "plane": _WIN_PLANE,
    "overall_width": 1.2,
    "overall_height": 1.0,
    "type_ref": "WT1",
}

_DOOR_PLANE = _plane(0.3, 0.0, 0.0)

_DOOR_FILL = {
    "plane": _DOOR_PLANE,
    "overall_width": 0.9,
    "overall_height": 2.1,
    "type_ref": "DT1",
}

_WIN_TYPE = {
    "name": "WT1",
    "overall_width": 1.2,
    "overall_height": 1.0,
    "component_graph": "fixed_casement",
}

_DOOR_TYPE = {
    "name": "DT1",
    "overall_width": 0.9,
    "overall_height": 2.1,
    "component_graph": "door_flush",
}


def _data(elements=None, window_types=None, door_types=None):
    import copy
    d = copy.deepcopy(_BASE)
    storey = d["buildings"][0]["storeys"][0]
    storey["elements"] = elements or []
    if window_types:
        d["window_types"] = window_types
    if door_types:
        d["door_types"] = door_types
    return d


def _wall_with_windows(windows):
    import copy
    w = copy.deepcopy(_WALL_ELEM)
    w["windows"] = windows
    return w


def _wall_with_doors(doors):
    import copy
    w = copy.deepcopy(_WALL_ELEM)
    w["doors"] = doors
    return w


# ===========================================================================
# validate_json
# ===========================================================================


class TestValidateJsonNewSections:
    def test_valid_window_type_section(self):
        d = dict(_BASE)
        d["window_types"] = [{"overall_width": 1.2, "overall_height": 1.4}]
        assert validate_json(d).ok

    def test_valid_door_type_section(self):
        d = dict(_BASE)
        d["door_types"] = [{"overall_width": 0.9, "overall_height": 2.1}]
        assert validate_json(d).ok

    def test_door_type_missing_overall_width(self):
        d = dict(_BASE)
        d["door_types"] = [{"overall_height": 2.1}]
        result = validate_json(d)
        assert not result.ok
        assert any("overall_width" in e for e in result.errors)

    def test_window_fill_missing_plane(self):
        wall = dict(_WALL_ELEM, windows=[{
            "overall_width": 1.2, "overall_height": 1.0, "type_ref": "WT1"
        }])
        result = validate_json(_data(elements=[wall]))
        assert not result.ok
        assert any("plane" in e for e in result.errors)

    def test_window_fill_missing_overall_width(self):
        wall = dict(_WALL_ELEM, windows=[{
            "plane": _WIN_PLANE, "overall_height": 1.0, "type_ref": "WT1"
        }])
        result = validate_json(_data(elements=[wall]))
        assert not result.ok
        assert any("overall_width" in e for e in result.errors)

    def test_window_fill_missing_type_ref(self):
        wall = dict(_WALL_ELEM, windows=[{
            "plane": _WIN_PLANE, "overall_width": 1.2, "overall_height": 1.0
        }])
        result = validate_json(_data(elements=[wall]))
        assert not result.ok
        assert any("type_ref" in e for e in result.errors)

    def test_door_fill_missing_overall_width(self):
        wall = dict(_WALL_ELEM, doors=[{
            "plane": _DOOR_PLANE, "overall_height": 2.1, "type_ref": "DT1"
        }])
        result = validate_json(_data(elements=[wall]))
        assert not result.ok
        assert any("overall_width" in e for e in result.errors)

    def test_window_fill_missing_overall_height(self):
        wall = dict(_WALL_ELEM, windows=[{
            "plane": _WIN_PLANE, "overall_width": 1.2, "type_ref": "WT1"
        }])
        result = validate_json(_data(elements=[wall]))
        assert not result.ok
        assert any("overall_height" in e for e in result.errors)


# ===========================================================================
# build — wall + window (Model B)
# ===========================================================================


class TestBuildWallOpeningWindow:
    def _make(self):
        return _data(
            elements=[_wall_with_windows([_WIN_FILL])],
            window_types=[_WIN_TYPE],
        )

    def test_creates_ifc_entities(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcWall")) == 1
        assert len(m._file.by_type("IfcOpeningElement")) == 1
        assert len(m._file.by_type("IfcWindow")) == 1

    def test_rel_voids_element(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcRelVoidsElement")) == 1

    def test_rel_fills_element(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcRelFillsElement")) == 1


# ===========================================================================
# build — wall + door (Model B)
# ===========================================================================


class TestBuildWallOpeningDoor:
    def _make(self):
        return _data(
            elements=[_wall_with_doors([_DOOR_FILL])],
            door_types=[_DOOR_TYPE],
        )

    def test_creates_ifc_entities(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcWall")) == 1
        assert len(m._file.by_type("IfcOpeningElement")) == 1
        assert len(m._file.by_type("IfcDoor")) == 1

    def test_rel_voids_element(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcRelVoidsElement")) == 1

    def test_rel_fills_element(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcRelFillsElement")) == 1


# ===========================================================================
# build — multiple fills on one wall
# ===========================================================================


class TestBuildMultipleFills:
    def test_two_windows_on_one_wall(self):
        import copy
        w2 = copy.deepcopy(_WIN_FILL)
        w2["plane"] = _plane(3.0, 0.0, 0.5)
        wall = dict(copy.deepcopy(_WALL_ELEM), windows=[_WIN_FILL, w2])
        m = build(_data(elements=[wall], window_types=[_WIN_TYPE]))
        assert len(m._file.by_type("IfcWindow")) == 2
        assert len(m._file.by_type("IfcOpeningElement")) == 2
        assert len(m._file.by_type("IfcRelVoidsElement")) == 2

    def test_window_and_door_on_one_wall(self):
        import copy
        wall = copy.deepcopy(_WALL_ELEM)
        wall["windows"] = [_WIN_FILL]
        wall["doors"] = [_DOOR_FILL]
        m = build(_data(
            elements=[wall],
            window_types=[_WIN_TYPE],
            door_types=[_DOOR_TYPE],
        ))
        assert len(m._file.by_type("IfcWindow")) == 1
        assert len(m._file.by_type("IfcDoor")) == 1
        assert len(m._file.by_type("IfcOpeningElement")) == 2


# ===========================================================================
# build — window_types at root level
# ===========================================================================


class TestBuildWindowTypes:
    def test_single_window_type_registered(self):
        m = build(_data(
            elements=[_wall_with_windows([_WIN_FILL])],
            window_types=[_WIN_TYPE],
        ))
        assert len(m._file.by_type("IfcWindowType")) == 1

    def test_rel_defines_by_type_covers_all_windows(self):
        import copy
        fills = []
        for i in range(3):
            f = copy.deepcopy(_WIN_FILL)
            f["plane"] = _plane(i * 1.5 + 0.3, 0.0, 0.5)
            fills.append(f)
        wall = dict(copy.deepcopy(_WALL_ELEM),
                    footprint=[[0,0,0],[8,0,0],[8,0.2,0],[0,0.2,0]],
                    windows=fills)
        m = build(_data(elements=[wall], window_types=[_WIN_TYPE]))
        assert len(m._file.by_type("IfcWindow")) == 3


# ===========================================================================
# build — door_types at root level
# ===========================================================================


class TestBuildDoorTypes:
    def test_single_door_type_registered(self):
        m = build(_data(
            elements=[_wall_with_doors([_DOOR_FILL])],
            door_types=[_DOOR_TYPE],
        ))
        assert len(m._file.by_type("IfcDoorType")) == 1

    def test_ten_doors_one_type(self):
        import copy
        elements = []
        for i in range(10):
            f = copy.deepcopy(_DOOR_FILL)
            f["plane"] = _plane(i * 0.5 + 0.1, 0.0, 0.0)
            wall = {
                "id": f"wall-{i}",
                "type": "basic_wall",
                "footprint": [[i*0.5, 0, 0], [i*0.5+0.4, 0, 0],
                               [i*0.5+0.4, 0.2, 0], [i*0.5, 0.2, 0]],
                "plane": {"origin": _vec(i*0.5, 0, 0), "x_axis": _vec(1,0,0), "y_axis": _vec(0,1,0)},
                "height": 3.0,
                "doors": [f],
            }
            elements.append(wall)
        m = build(_data(elements=elements, door_types=[_DOOR_TYPE]))
        assert len(m._file.by_type("IfcDoor")) == 10
        assert len(m._file.by_type("IfcDoorType")) == 1


# ===========================================================================
# build — ref resolution errors
# ===========================================================================


class TestBuildRefErrors:
    def test_unknown_window_type_ref_raises(self):
        import copy
        fill = copy.deepcopy(_WIN_FILL)
        fill["type_ref"] = "NO_SUCH_TYPE"
        with pytest.raises(ValueError, match="type_ref"):
            build(_data(elements=[_wall_with_windows([fill])], window_types=[_WIN_TYPE]))

    def test_unknown_door_type_ref_raises(self):
        import copy
        fill = copy.deepcopy(_DOOR_FILL)
        fill["type_ref"] = "NO_SUCH_TYPE"
        with pytest.raises(ValueError, match="type_ref"):
            build(_data(elements=[_wall_with_doors([fill])], door_types=[_DOOR_TYPE]))

    def test_window_type_without_component_graph_raises(self):
        wt_no_graph = {"name": "WT_BARE", "overall_width": 1.2, "overall_height": 1.0}
        import copy
        fill = copy.deepcopy(_WIN_FILL)
        fill["type_ref"] = "WT_BARE"
        with pytest.raises(ValueError, match="component_graph"):
            build(_data(elements=[_wall_with_windows([fill])], window_types=[wt_no_graph]))

    def test_duplicate_element_id_raises(self):
        import copy
        wall2 = copy.deepcopy(_WALL_ELEM)  # same id "w1"
        with pytest.raises(ValueError, match="Duplicate element id"):
            build(_data(elements=[_WALL_ELEM, wall2]))


# ===========================================================================
# build — round-trip save/reopen
# ===========================================================================


class TestBuildRoundtrip:
    def test_save_and_reopen(self, tmp_path):
        import ifcopenshell
        out = str(tmp_path / "out.ifc")
        build(
            _data(elements=[_wall_with_windows([_WIN_FILL])], window_types=[_WIN_TYPE]),
            output_path=out,
        )
        f2 = ifcopenshell.open(out)
        assert len(f2.by_type("IfcOpeningElement")) == 1
        assert len(f2.by_type("IfcWindow")) == 1
        assert len(f2.by_type("IfcRelVoidsElement")) == 1
        assert len(f2.by_type("IfcRelFillsElement")) == 1

    def test_build_from_json_string(self):
        from ifckit.json_build import build_from_json
        d = _data(elements=[_wall_with_windows([_WIN_FILL])], window_types=[_WIN_TYPE])
        m = build_from_json(json.dumps(d))
        assert len(m._file.by_type("IfcWindow")) == 1
