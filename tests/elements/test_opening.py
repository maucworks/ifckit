"""
tests/elements/test_opening.py
==============================

Tests for PendingOpening, PendingDoor, PendingWindow.
"""

import pytest

from ifckit.elements.opening import (
    DOOR_OPERATION_TYPES,
    OPENING_HOST_IFC_CLASSES,
    WINDOW_TYPES,
    PendingDoor,
    PendingOpening,
    PendingWindow,
)
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _world_plane() -> Plane:
    return Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))


def _opening(**kwargs) -> PendingOpening:
    defaults = dict(plane=_world_plane(), width=1.0, height=2.1)
    defaults.update(kwargs)
    return PendingOpening(**defaults)


def _door(**kwargs) -> PendingDoor:
    defaults = dict(overall_width=0.9, overall_height=2.1)
    defaults.update(kwargs)
    return PendingDoor(**defaults)


def _window(**kwargs) -> PendingWindow:
    defaults = dict(overall_width=1.2, overall_height=1.4)
    defaults.update(kwargs)
    return PendingWindow(**defaults)


# ===========================================================================
# PendingOpening
# ===========================================================================


class TestPendingOpeningConstructor:
    def test_basic_fields(self):
        o = _opening(name="W01")
        assert o.name == "W01"
        assert o.width == 1.0
        assert o.height == 2.1
        assert o.element_type == "basic_opening"

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="width must be positive"):
            _opening(width=0.0)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError, match="height must be positive"):
            _opening(height=-1.0)

    def test_clips_default_empty(self):
        assert _opening().clips == []

    def test_properties_default_empty(self):
        assert _opening().properties == {}

    def test_custom_properties(self):
        o = _opening(properties={"FireRating": "EI30"})
        assert o.properties["FireRating"] == "EI30"


class TestPendingOpeningRoundtrip:
    def test_minimal_roundtrip(self):
        o = _opening()
        d = o.to_dict()
        o2 = PendingOpening.from_dict(d)
        assert o2.width == o.width
        assert o2.height == o.height

    def test_full_roundtrip(self):
        plane = Plane(Vec(1, 2, 0), Vec(0, 1, 0), Vec(0, 0, 1))
        o = PendingOpening(
            plane=plane,
            width=1.5,
            height=2.2,
            name="Door Opening",
            properties={"tag": "O1"},
        )
        d = o.to_dict()
        o2 = PendingOpening.from_dict(d)
        assert o2.name == "Door Opening"
        assert o2.width == 1.5
        assert o2.height == 2.2
        assert o2.properties == {"tag": "O1"}
        # Plane round-trip
        assert o2.plane.origin.x == pytest.approx(1.0)
        assert o2.plane.origin.y == pytest.approx(2.0)

    def test_type_field_in_dict(self):
        d = _opening().to_dict()
        assert d["type"] == "basic_opening"

    def test_missing_plane_raises(self):
        d = _opening().to_dict()
        del d["plane"]
        with pytest.raises((ValueError, KeyError)):
            PendingOpening.from_dict(d)

    def test_missing_width_raises(self):
        d = _opening().to_dict()
        del d["width"]
        with pytest.raises(ValueError, match="missing required field 'width'"):
            PendingOpening.from_dict(d)

    def test_clips_roundtrip(self):
        clip_plane = Plane(Vec(0, 0, 1), Vec(1, 0, 0), Vec(0, 1, 0))
        o = _opening(clips=[clip_plane])
        d = o.to_dict()
        o2 = PendingOpening.from_dict(d)
        assert len(o2.clips) == 1
        assert o2.clips[0].origin.z == pytest.approx(1.0)

    def test_json_roundtrip(self):
        import json

        o = _opening(name="json-test")
        s = o.to_json()
        d = json.loads(s)
        o2 = PendingOpening.from_dict(d)
        assert o2.name == "json-test"


# ===========================================================================
# PendingDoor
# ===========================================================================


class TestPendingDoorConstructor:
    def test_basic_fields(self):
        d = _door(name="D01", operation_type="SINGLE_SWING_LEFT")
        assert d.name == "D01"
        assert d.overall_width == 0.9
        assert d.overall_height == 2.1
        assert d.operation_type == "SINGLE_SWING_LEFT"
        assert d.element_type == "basic_door"

    def test_default_operation_type(self):
        assert _door().operation_type == "NOTDEFINED"

    def test_operation_type_normalised_to_upper(self):
        d = _door(operation_type="single_swing_right")
        assert d.operation_type == "SINGLE_SWING_RIGHT"

    def test_unknown_operation_type_raises(self):
        with pytest.raises(ValueError, match="unknown operation_type"):
            _door(operation_type="REVOLVING")

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="overall_width must be positive"):
            _door(overall_width=0.0)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError, match="overall_height must be positive"):
            _door(overall_height=-0.1)

    def test_type_ref(self):
        d = _door(type_ref="door_type:A1")
        assert d.type_ref == "door_type:A1"

    @pytest.mark.parametrize("op", sorted(DOOR_OPERATION_TYPES))
    def test_all_allowed_operation_types(self, op):
        d = _door(operation_type=op)
        assert d.operation_type == op


class TestPendingDoorRoundtrip:
    def test_minimal_roundtrip(self):
        d = _door()
        d2 = PendingDoor.from_dict(d.to_dict())
        assert d2.overall_width == d.overall_width
        assert d2.operation_type == "NOTDEFINED"
        assert d2.type_ref is None

    def test_full_roundtrip(self):
        door = PendingDoor(
            overall_width=0.9,
            overall_height=2.1,
            operation_type="SLIDING_TO_LEFT",
            type_ref="my-type",
            name="D-01",
            properties={"frame": "aluminium"},
        )
        d = door.to_dict()
        door2 = PendingDoor.from_dict(d)
        assert door2.overall_width == 0.9
        assert door2.operation_type == "SLIDING_TO_LEFT"
        assert door2.type_ref == "my-type"
        assert door2.properties == {"frame": "aluminium"}

    def test_type_field_in_dict(self):
        assert _door().to_dict()["type"] == "basic_door"

    def test_missing_overall_width_raises(self):
        d = _door().to_dict()
        del d["overall_width"]
        with pytest.raises(ValueError, match="overall_width"):
            PendingDoor.from_dict(d)


# ===========================================================================
# PendingWindow
# ===========================================================================


class TestPendingWindowConstructor:
    def test_basic_fields(self):
        w = _window(name="W01", window_type="FIXED_CASEMENT")
        assert w.name == "W01"
        assert w.overall_width == 1.2
        assert w.overall_height == 1.4
        assert w.window_type == "FIXED_CASEMENT"
        assert w.element_type == "basic_window"

    def test_default_window_type(self):
        assert _window().window_type == "NOTDEFINED"

    def test_window_type_normalised_to_upper(self):
        w = _window(window_type="side_hung_left_hand")
        assert w.window_type == "SIDE_HUNG_LEFT_HAND"

    def test_unknown_window_type_raises(self):
        with pytest.raises(ValueError, match="unknown window_type"):
            _window(window_type="DOUBLE_HUNG")

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="overall_width must be positive"):
            _window(overall_width=0.0)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError, match="overall_height must be positive"):
            _window(overall_height=-1.0)

    @pytest.mark.parametrize("wt", sorted(WINDOW_TYPES))
    def test_all_allowed_window_types(self, wt):
        w = _window(window_type=wt)
        assert w.window_type == wt


class TestPendingWindowRoundtrip:
    def test_minimal_roundtrip(self):
        w = _window()
        w2 = PendingWindow.from_dict(w.to_dict())
        assert w2.overall_width == w.overall_width
        assert w2.window_type == "NOTDEFINED"

    def test_full_roundtrip(self):
        win = PendingWindow(
            overall_width=1.2,
            overall_height=1.4,
            window_type="TILT_AND_TURN_RIGHT_HAND",
            type_ref="wt-01",
            name="W-01",
            properties={"glazing": "double"},
        )
        d = win.to_dict()
        win2 = PendingWindow.from_dict(d)
        assert win2.window_type == "TILT_AND_TURN_RIGHT_HAND"
        assert win2.type_ref == "wt-01"
        assert win2.properties == {"glazing": "double"}

    def test_type_field_in_dict(self):
        assert _window().to_dict()["type"] == "basic_window"

    def test_missing_overall_height_raises(self):
        d = _window().to_dict()
        del d["overall_height"]
        with pytest.raises(ValueError, match="overall_height"):
            PendingWindow.from_dict(d)


# ===========================================================================
# Registry auto-registration
# ===========================================================================


class TestElementRegistration:
    def test_opening_registered(self):
        from ifckit.elements.registry import ElementRegistry
        assert ElementRegistry.has("basic_opening")

    def test_door_registered(self):
        from ifckit.elements.registry import ElementRegistry
        assert ElementRegistry.has("basic_door")

    def test_window_registered(self):
        from ifckit.elements.registry import ElementRegistry
        assert ElementRegistry.has("basic_window")

    def test_from_json_dispatch_opening(self):
        import json
        o = _opening(name="dispatch-test")
        s = o.to_json()
        from ifckit.elements.base import PendingElement
        o2 = PendingElement.from_json(s)
        assert isinstance(o2, PendingOpening)
        assert o2.name == "dispatch-test"

    def test_from_json_dispatch_door(self):
        from ifckit.elements.base import PendingElement
        d = _door(name="door-dispatch")
        d2 = PendingElement.from_json(d.to_json())
        assert isinstance(d2, PendingDoor)

    def test_from_json_dispatch_window(self):
        from ifckit.elements.base import PendingElement
        w = _window(name="win-dispatch")
        w2 = PendingElement.from_json(w.to_json())
        assert isinstance(w2, PendingWindow)


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    def test_door_operation_types_is_frozenset(self):
        assert isinstance(DOOR_OPERATION_TYPES, frozenset)

    def test_window_types_is_frozenset(self):
        assert isinstance(WINDOW_TYPES, frozenset)

    def test_opening_host_ifc_classes(self):
        assert "IfcWall" in OPENING_HOST_IFC_CLASSES
        assert "IfcSlab" in OPENING_HOST_IFC_CLASSES
        assert "IfcRoof" in OPENING_HOST_IFC_CLASSES

    def test_notdefined_in_both(self):
        assert "NOTDEFINED" in DOOR_OPERATION_TYPES
        assert "NOTDEFINED" in WINDOW_TYPES

    def test_userdefined_in_both(self):
        assert "USERDEFINED" in DOOR_OPERATION_TYPES
        assert "USERDEFINED" in WINDOW_TYPES
