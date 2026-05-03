"""
tests/test_json_build_openings.py
==================================

Tests for the 3-pass JSON build: openings, doors, windows, types.

Openings are nested inside elements. Fills (doors/windows) are nested
inside openings. n:1 supported — multiple fills per opening.
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


def _plane(ox, oy, oz, xx=1, xy=0, xz=0, yx=0, yy=1, yz=0):
    return {"origin": _vec(ox, oy, oz), "x_axis": _vec(xx, xy, xz), "y_axis": _vec(yx, yy, yz)}


_WALL_FOOTPRINT = [
    [0, 0, 0], [5, 0, 0], [5, 0.2, 0], [0, 0.2, 0],
]
_WALL_PLANE = _plane(0, 0, 0)

_WALL_ELEM = {
    "id": "w1",
    "type": "basic_wall",
    "footprint": _WALL_FOOTPRINT,
    "plane": _WALL_PLANE,
    "height": 3.0,
}

_OPENING_PLANE = _plane(1, 0, 0)

_OPENING = {
    "plane": _OPENING_PLANE,
    "width": 0.9,
    "height": 2.1,
}

_DOOR = {
    "overall_width": 0.9,
    "overall_height": 2.1,
}

_WINDOW = {
    "overall_width": 1.2,
    "overall_height": 1.4,
}


def _wall_with_opening(opening):
    """Wall element dict with one opening."""
    return dict(_WALL_ELEM, openings=[opening])


def _data(elements=None):
    """Deep-copy base and set storey elements."""
    import copy
    d = copy.deepcopy(_BASE)
    storey = d["buildings"][0]["storeys"][0]
    storey["elements"] = elements or []
    return d


# ===========================================================================
# validate_json — new nested sections
# ===========================================================================


class TestValidateJsonNewSections:
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

    def test_valid_window_type_section(self):
        d = dict(_BASE)
        d["window_types"] = [{"overall_width": 1.2, "overall_height": 1.4}]
        assert validate_json(d).ok

    def test_opening_missing_plane(self):
        wall = dict(_WALL_ELEM, openings=[{"width": 0.9, "height": 2.1}])
        d = _data(elements=[wall])
        result = validate_json(d)
        assert not result.ok
        assert any("plane" in e for e in result.errors)

    def test_opening_missing_width(self):
        wall = dict(_WALL_ELEM, openings=[{"plane": _OPENING_PLANE, "height": 2.1}])
        d = _data(elements=[wall])
        result = validate_json(d)
        assert not result.ok
        assert any("width" in e for e in result.errors)

    def test_door_missing_overall_width(self):
        op = dict(_OPENING, doors=[{"overall_height": 2.1}])
        d = _data(elements=[_wall_with_opening(op)])
        result = validate_json(d)
        assert not result.ok
        assert any("overall_width" in e for e in result.errors)

    def test_window_missing_overall_height(self):
        op = dict(_OPENING, windows=[{"overall_width": 1.2}])
        d = _data(elements=[_wall_with_opening(op)])
        result = validate_json(d)
        assert not result.ok
        assert any("overall_height" in e for e in result.errors)


# ===========================================================================
# build — wall + opening + door
# ===========================================================================


class TestBuildWallOpeningDoor:
    def _make(self):
        op = dict(_OPENING, doors=[_DOOR])
        return _data(elements=[_wall_with_opening(op)])

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

    def test_no_type_by_default(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcDoorType")) == 0
        assert len(m._file.by_type("IfcRelDefinesByType")) == 0


# ===========================================================================
# build — wall + opening + window
# ===========================================================================


class TestBuildWallOpeningWindow:
    def _make(self):
        op = dict(_OPENING, width=1.2, height=1.4, windows=[_WINDOW])
        return _data(elements=[_wall_with_opening(op)])

    def test_creates_ifc_entities(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcWindow")) == 1
        assert len(m._file.by_type("IfcOpeningElement")) == 1

    def test_rel_voids_and_fills(self):
        m = build(self._make())
        assert len(m._file.by_type("IfcRelVoidsElement")) == 1
        assert len(m._file.by_type("IfcRelFillsElement")) == 1


# ===========================================================================
# build — n:1 multiple fills per opening
# ===========================================================================


class TestBuildMultipleFillsPerOpening:
    def test_two_doors_in_one_opening(self):
        op = dict(_OPENING, doors=[_DOOR, _DOOR])
        m = build(_data(elements=[_wall_with_opening(op)]))
        assert len(m._file.by_type("IfcDoor")) == 2
        assert len(m._file.by_type("IfcOpeningElement")) == 1
        assert len(m._file.by_type("IfcRelFillsElement")) == 2

    def test_door_and_window_in_one_opening(self):
        op = dict(_OPENING, doors=[_DOOR], windows=[_WINDOW])
        m = build(_data(elements=[_wall_with_opening(op)]))
        assert len(m._file.by_type("IfcDoor")) == 1
        assert len(m._file.by_type("IfcWindow")) == 1
        assert len(m._file.by_type("IfcOpeningElement")) == 1
        assert len(m._file.by_type("IfcRelFillsElement")) == 2


# ===========================================================================
# build — door_types at root level
# ===========================================================================


class TestBuildDoorTypes:
    def _make(self, n_doors=1):
        import copy
        d = copy.deepcopy(_BASE)
        d["door_types"] = [
            {"name": "DT1", "overall_width": 0.9, "overall_height": 2.1}
        ]
        elements = []
        for i in range(n_doors):
            op = {
                "plane": _plane(i * 2 + 0.3, 0, 0),
                "width": 0.9,
                "height": 2.1,
                "doors": [{"overall_width": 0.9, "overall_height": 2.1, "type_ref": "DT1"}],
            }
            elements.append({
                "id": f"w{i}",
                "type": "basic_wall",
                "footprint": [[i*2,0,0],[i*2+1.5,0,0],[i*2+1.5,0.2,0],[i*2,0.2,0]],
                "plane": _plane(i*2, 0, 0),
                "height": 3.0,
                "openings": [op],
            })
        d["buildings"][0]["storeys"][0]["elements"] = elements
        return d

    def test_single_door_type_created(self):
        m = build(self._make(n_doors=3))
        assert len(m._file.by_type("IfcDoorType")) == 1

    def test_rel_defines_by_type_covers_all_doors(self):
        m = build(self._make(n_doors=3))
        rels = m._file.by_type("IfcRelDefinesByType")
        assert len(rels) == 1
        assert len(rels[0].RelatedObjects) == 3

    def test_ten_doors_one_type(self):
        m = build(self._make(n_doors=10))
        assert len(m._file.by_type("IfcDoor")) == 10
        assert len(m._file.by_type("IfcDoorType")) == 1


# ===========================================================================
# build — window_types at root level
# ===========================================================================


class TestBuildWindowTypes:
    def _make(self, n_windows=1):
        import copy
        d = copy.deepcopy(_BASE)
        d["window_types"] = [
            {"name": "WT1", "overall_width": 1.2, "overall_height": 1.4}
        ]
        elements = []
        for i in range(n_windows):
            op = {
                "plane": _plane(i * 2 + 0.4, 0, 0),
                "width": 1.2,
                "height": 1.4,
                "windows": [{"overall_width": 1.2, "overall_height": 1.4, "type_ref": "WT1"}],
            }
            elements.append({
                "id": f"w{i}",
                "type": "basic_wall",
                "footprint": [[i*2,0,0],[i*2+2,0,0],[i*2+2,0.2,0],[i*2,0.2,0]],
                "plane": _plane(i*2, 0, 0),
                "height": 3.0,
                "openings": [op],
            })
        d["buildings"][0]["storeys"][0]["elements"] = elements
        return d

    def test_single_window_type_created(self):
        m = build(self._make(n_windows=5))
        assert len(m._file.by_type("IfcWindowType")) == 1

    def test_rel_defines_by_type_covers_all_windows(self):
        m = build(self._make(n_windows=5))
        rels = m._file.by_type("IfcRelDefinesByType")
        assert len(rels) == 1
        assert len(rels[0].RelatedObjects) == 5


# ===========================================================================
# build — ref resolution errors
# ===========================================================================


class TestBuildRefErrors:
    def test_element_with_openings_but_no_id_raises(self):
        wall_no_id = {
            "type": "basic_wall",
            "footprint": _WALL_FOOTPRINT,
            "plane": _WALL_PLANE,
            "height": 3.0,
            "openings": [_OPENING],
        }
        with pytest.raises(ValueError, match="no 'id'"):
            build(_data(elements=[wall_no_id]))

    def test_unknown_type_ref_raises(self):
        op = dict(_OPENING, doors=[dict(_DOOR, type_ref="NO_SUCH_TYPE")])
        with pytest.raises(ValueError, match="type_ref"):
            build(_data(elements=[_wall_with_opening(op)]))

    def test_duplicate_element_id_raises(self):
        wall2 = dict(_WALL_ELEM)  # same id "w1"
        with pytest.raises(ValueError, match="Duplicate element id"):
            build(_data(elements=[_WALL_ELEM, wall2]))


# ===========================================================================
# build — round-trip save/reopen
# ===========================================================================


class TestBuildRoundtrip:
    def test_save_and_reopen(self, tmp_path):
        import copy, ifcopenshell
        d = copy.deepcopy(_BASE)
        d["door_types"] = [{"name": "DT1", "overall_width": 0.9, "overall_height": 2.1}]
        op = dict(_OPENING, doors=[dict(_DOOR, type_ref="DT1")])
        d["buildings"][0]["storeys"][0]["elements"] = [_wall_with_opening(op)]

        out = str(tmp_path / "out.ifc")
        build(d, output_path=out)

        f2 = ifcopenshell.open(out)
        assert len(f2.by_type("IfcOpeningElement")) == 1
        assert len(f2.by_type("IfcDoor")) == 1
        assert len(f2.by_type("IfcDoorType")) == 1
        assert len(f2.by_type("IfcRelVoidsElement")) == 1
        assert len(f2.by_type("IfcRelFillsElement")) == 1
        assert len(f2.by_type("IfcRelDefinesByType")) == 1

    def test_build_from_json_string(self):
        import copy
        d = copy.deepcopy(_BASE)
        op = dict(_OPENING, doors=[_DOOR])
        d["buildings"][0]["storeys"][0]["elements"] = [_wall_with_opening(op)]
        from ifckit.json_build import build_from_json
        m = build_from_json(json.dumps(d))
        assert len(m._file.by_type("IfcDoor")) == 1
