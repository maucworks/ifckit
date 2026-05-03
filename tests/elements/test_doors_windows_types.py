"""
tests/elements/test_doors_windows_types.py
==========================================

Tests for PendingTypeObject, PendingDoorType, PendingWindowType.
"""

import pytest

from ifckit.elements.types import PendingDoorType, PendingTypeObject, PendingWindowType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _door_type(**kwargs) -> PendingDoorType:
    defaults = dict(overall_width=0.9, overall_height=2.1)
    defaults.update(kwargs)
    return PendingDoorType(**defaults)


def _window_type(**kwargs) -> PendingWindowType:
    defaults = dict(overall_width=1.2, overall_height=1.4)
    defaults.update(kwargs)
    return PendingWindowType(**defaults)


# ===========================================================================
# PendingDoorType — constructor
# ===========================================================================


class TestPendingDoorTypeConstructor:
    def test_basic_fields(self):
        dt = _door_type(name="DT-01", operation_type="SINGLE_SWING_LEFT")
        assert dt.name == "DT-01"
        assert dt.overall_width == 0.9
        assert dt.overall_height == 2.1
        assert dt.operation_type == "SINGLE_SWING_LEFT"
        assert dt.type_object_type == "door_type"

    def test_default_operation_type(self):
        assert _door_type().operation_type == "NOTDEFINED"

    def test_operation_type_upper(self):
        dt = _door_type(operation_type="single_swing_right")
        assert dt.operation_type == "SINGLE_SWING_RIGHT"

    def test_invalid_operation_type(self):
        with pytest.raises(ValueError, match="unknown operation_type"):
            _door_type(operation_type="REVOLVING")

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="overall_width must be positive"):
            _door_type(overall_width=0.0)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError, match="overall_height must be positive"):
            _door_type(overall_height=-1.0)

    def test_lining_fields_default_none(self):
        dt = _door_type()
        for f in (
            "lining_depth", "lining_thickness", "threshold_depth",
            "threshold_thickness", "threshold_offset", "transom_thickness",
            "transom_offset", "lining_offset", "casing_thickness",
            "casing_depth", "lining_to_panel_offset_x", "lining_to_panel_offset_y",
        ):
            assert getattr(dt, f) is None, f"Expected {f} to be None"

    def test_panel_fields_default_none(self):
        dt = _door_type()
        for f in ("panel_depth", "panel_width", "panel_operation"):
            assert getattr(dt, f) is None

    def test_all_lining_fields_set(self):
        dt = _door_type(
            lining_depth=0.1,
            lining_thickness=0.05,
            threshold_depth=0.02,
            threshold_thickness=0.01,
            threshold_offset=0.005,
            transom_thickness=0.04,
            transom_offset=2.0,
            lining_offset=0.005,
            casing_thickness=0.02,
            casing_depth=0.06,
            lining_to_panel_offset_x=0.01,
            lining_to_panel_offset_y=0.01,
        )
        assert dt.lining_depth == pytest.approx(0.1)
        assert dt.casing_depth == pytest.approx(0.06)

    def test_panel_fields_set(self):
        dt = _door_type(panel_depth=0.04, panel_width=0.95, panel_operation="SWINGING")
        assert dt.panel_depth == pytest.approx(0.04)
        assert dt.panel_width == pytest.approx(0.95)
        assert dt.panel_operation == "SWINGING"

    def test_properties_default_empty(self):
        assert _door_type().properties == {}

    def test_custom_properties(self):
        dt = _door_type(properties={"material": "oak"})
        assert dt.properties["material"] == "oak"


# ===========================================================================
# PendingDoorType — type_key
# ===========================================================================


class TestPendingDoorTypeKey:
    def test_explicit_key_honoured(self):
        dt = _door_type(type_key="my-door-key")
        assert dt.type_key == "my-door-key"

    def test_auto_key_generated(self):
        dt = _door_type()
        assert dt.type_key.startswith("door_type:")

    def test_same_params_same_key(self):
        dt1 = _door_type(overall_width=0.9, overall_height=2.1, operation_type="NOTDEFINED")
        dt2 = _door_type(overall_width=0.9, overall_height=2.1, operation_type="NOTDEFINED")
        assert dt1.type_key == dt2.type_key

    def test_different_width_different_key(self):
        dt1 = _door_type(overall_width=0.9)
        dt2 = _door_type(overall_width=1.0)
        assert dt1.type_key != dt2.type_key

    def test_different_operation_different_key(self):
        dt1 = _door_type(operation_type="SINGLE_SWING_LEFT")
        dt2 = _door_type(operation_type="SINGLE_SWING_RIGHT")
        assert dt1.type_key != dt2.type_key

    def test_lining_params_affect_key(self):
        dt1 = _door_type()
        dt2 = _door_type(lining_depth=0.1)
        assert dt1.type_key != dt2.type_key

    def test_key_stable_across_instances(self):
        """Same params always produce the same key — no randomness."""
        keys = {
            _door_type(overall_width=0.9, overall_height=2.1, lining_depth=0.1).type_key
            for _ in range(10)
        }
        assert len(keys) == 1


# ===========================================================================
# PendingDoorType — roundtrip
# ===========================================================================


class TestPendingDoorTypeRoundtrip:
    def test_minimal_roundtrip(self):
        dt = _door_type()
        dt2 = PendingDoorType.from_dict(dt.to_dict())
        assert dt2.overall_width == dt.overall_width
        assert dt2.overall_height == dt.overall_height
        assert dt2.operation_type == dt.operation_type
        # Explicit key is preserved in dict so roundtrip keeps the same key
        assert dt2.type_key == dt.type_key

    def test_full_lining_roundtrip(self):
        dt = _door_type(
            lining_depth=0.1,
            lining_thickness=0.05,
            casing_depth=0.06,
            panel_depth=0.04,
            panel_width=0.95,
            panel_operation="SWINGING",
        )
        dt2 = PendingDoorType.from_dict(dt.to_dict())
        assert dt2.lining_depth == pytest.approx(0.1)
        assert dt2.casing_depth == pytest.approx(0.06)
        assert dt2.panel_operation == "SWINGING"

    def test_none_fields_absent_from_dict(self):
        d = _door_type().to_dict()
        assert "lining_depth" not in d
        assert "panel_depth" not in d

    def test_set_fields_present_in_dict(self):
        d = _door_type(lining_depth=0.1, panel_depth=0.04).to_dict()
        assert "lining_depth" in d
        assert "panel_depth" in d

    def test_type_field_in_dict(self):
        assert _door_type().to_dict()["type"] == "door_type"

    def test_missing_overall_width_raises(self):
        d = _door_type().to_dict()
        del d["overall_width"]
        with pytest.raises(ValueError, match="overall_width"):
            PendingDoorType.from_dict(d)

    def test_properties_roundtrip(self):
        dt = _door_type(properties={"material": "steel"})
        dt2 = PendingDoorType.from_dict(dt.to_dict())
        assert dt2.properties == {"material": "steel"}

    def test_json_roundtrip(self):
        import json
        dt = _door_type(name="json-door-type", lining_depth=0.12)
        s = dt.to_json()
        d = json.loads(s)
        dt2 = PendingDoorType.from_dict(d)
        assert dt2.name == "json-door-type"
        assert dt2.lining_depth == pytest.approx(0.12)


# ===========================================================================
# PendingWindowType — constructor
# ===========================================================================


class TestPendingWindowTypeConstructor:
    def test_basic_fields(self):
        wt = _window_type(name="WT-01", window_type="FIXED_CASEMENT")
        assert wt.name == "WT-01"
        assert wt.overall_width == 1.2
        assert wt.overall_height == 1.4
        assert wt.window_type == "FIXED_CASEMENT"
        assert wt.type_object_type == "window_type"

    def test_default_window_type(self):
        assert _window_type().window_type == "NOTDEFINED"

    def test_window_type_upper(self):
        wt = _window_type(window_type="side_hung_right_hand")
        assert wt.window_type == "SIDE_HUNG_RIGHT_HAND"

    def test_invalid_window_type(self):
        with pytest.raises(ValueError, match="unknown window_type"):
            _window_type(window_type="DOUBLE_HUNG")

    def test_zero_width_raises(self):
        with pytest.raises(ValueError, match="overall_width must be positive"):
            _window_type(overall_width=0.0)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError, match="overall_height must be positive"):
            _window_type(overall_height=-0.5)

    def test_lining_fields_default_none(self):
        wt = _window_type()
        for f in (
            "lining_depth", "lining_thickness", "transom_thickness",
            "mullion_thickness", "first_transom_offset", "second_transom_offset",
            "first_mullion_offset", "second_mullion_offset", "lining_offset",
            "lining_to_panel_offset_x", "lining_to_panel_offset_y",
        ):
            assert getattr(wt, f) is None, f"Expected {f} to be None"

    def test_panel_fields_default_none(self):
        wt = _window_type()
        for f in ("panel_depth", "panel_width", "panel_height", "panel_operation"):
            assert getattr(wt, f) is None

    def test_all_lining_fields(self):
        wt = _window_type(
            lining_depth=0.08,
            lining_thickness=0.04,
            transom_thickness=0.03,
            mullion_thickness=0.03,
            first_transom_offset=0.5,
            second_transom_offset=0.7,
            first_mullion_offset=0.4,
            second_mullion_offset=0.6,
            lining_offset=0.005,
            lining_to_panel_offset_x=0.01,
            lining_to_panel_offset_y=0.01,
        )
        assert wt.lining_depth == pytest.approx(0.08)
        assert wt.mullion_thickness == pytest.approx(0.03)
        assert wt.second_mullion_offset == pytest.approx(0.6)


# ===========================================================================
# PendingWindowType — type_key
# ===========================================================================


class TestPendingWindowTypeKey:
    def test_explicit_key_honoured(self):
        wt = _window_type(type_key="my-window-key")
        assert wt.type_key == "my-window-key"

    def test_auto_key_generated(self):
        wt = _window_type()
        assert wt.type_key.startswith("window_type:")

    def test_same_params_same_key(self):
        wt1 = _window_type(overall_width=1.2, overall_height=1.4, window_type="NOTDEFINED")
        wt2 = _window_type(overall_width=1.2, overall_height=1.4, window_type="NOTDEFINED")
        assert wt1.type_key == wt2.type_key

    def test_different_height_different_key(self):
        wt1 = _window_type(overall_height=1.4)
        wt2 = _window_type(overall_height=1.5)
        assert wt1.type_key != wt2.type_key

    def test_lining_params_affect_key(self):
        wt1 = _window_type()
        wt2 = _window_type(lining_depth=0.08)
        assert wt1.type_key != wt2.type_key

    def test_key_does_not_collide_with_door_type(self):
        # Same numeric params but door vs window must produce different keys
        dt = _door_type(overall_width=1.2, overall_height=1.4)
        wt = _window_type(overall_width=1.2, overall_height=1.4)
        assert dt.type_key != wt.type_key


# ===========================================================================
# PendingWindowType — roundtrip
# ===========================================================================


class TestPendingWindowTypeRoundtrip:
    def test_minimal_roundtrip(self):
        wt = _window_type()
        wt2 = PendingWindowType.from_dict(wt.to_dict())
        assert wt2.overall_width == wt.overall_width
        assert wt2.window_type == wt.window_type
        assert wt2.type_key == wt.type_key

    def test_full_lining_roundtrip(self):
        wt = _window_type(
            lining_depth=0.08,
            transom_thickness=0.03,
            panel_depth=0.03,
            panel_height=0.5,
            panel_operation="SIDEHUNGRIGHTHAND",
        )
        wt2 = PendingWindowType.from_dict(wt.to_dict())
        assert wt2.lining_depth == pytest.approx(0.08)
        assert wt2.panel_height == pytest.approx(0.5)
        assert wt2.panel_operation == "SIDEHUNGRIGHTHAND"

    def test_none_fields_absent_from_dict(self):
        d = _window_type().to_dict()
        assert "lining_depth" not in d
        assert "panel_depth" not in d

    def test_type_field_in_dict(self):
        assert _window_type().to_dict()["type"] == "window_type"

    def test_missing_overall_height_raises(self):
        d = _window_type().to_dict()
        del d["overall_height"]
        with pytest.raises(ValueError, match="overall_height"):
            PendingWindowType.from_dict(d)

    def test_properties_roundtrip(self):
        wt = _window_type(properties={"frame": "uPVC"})
        wt2 = PendingWindowType.from_dict(wt.to_dict())
        assert wt2.properties == {"frame": "uPVC"}


# ===========================================================================
# PendingTypeObject base
# ===========================================================================


class TestPendingTypeObjectBase:
    def test_door_type_is_pending_type_object(self):
        assert isinstance(_door_type(), PendingTypeObject)

    def test_window_type_is_pending_type_object(self):
        assert isinstance(_window_type(), PendingTypeObject)

    def test_repr_contains_key_and_name(self):
        dt = _door_type(name="mytype", type_key="explicit-k")
        r = repr(dt)
        assert "explicit-k" in r
        assert "mytype" in r
