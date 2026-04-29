"""Tests for ifckit.elements.style — RenderStyle parsing and serialisation."""

import pytest
from ifckit.elements.style import RenderStyle


class TestHexInput:
    def test_basic_hex(self):
        s = RenderStyle("#FF8000")
        assert s.r == pytest.approx(1.0)
        assert s.g == pytest.approx(128 / 255)
        assert s.b == pytest.approx(0.0)
        assert s.transparency == pytest.approx(0.0)

    def test_hex_case_insensitive(self):
        assert RenderStyle("#ff8000") == RenderStyle("#FF8000")

    def test_hex_without_hash(self):
        s = RenderStyle("FF8000")
        assert s.r == pytest.approx(1.0)

    def test_hex_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            RenderStyle("#FF80")

    def test_hex_invalid_chars_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            RenderStyle("#GGHH00")


class TestIntTupleInput:
    def test_int_tuple(self):
        s = RenderStyle((255, 128, 0))
        assert s.r == pytest.approx(1.0)
        assert s.g == pytest.approx(128 / 255)
        assert s.b == pytest.approx(0.0)

    def test_int_tuple_equals_hex(self):
        assert RenderStyle((255, 128, 0)) == RenderStyle("#FF8000")

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="3 elements"):
            RenderStyle((255, 128))


class TestFloatTupleInput:
    def test_float_tuple(self):
        s = RenderStyle((1.0, 0.5, 0.0))
        assert s.r == pytest.approx(1.0)
        assert s.g == pytest.approx(0.5)
        assert s.b == pytest.approx(0.0)

    def test_float_tuple_all_zero(self):
        s = RenderStyle((0.0, 0.0, 0.0))
        assert s.r == 0.0 and s.g == 0.0 and s.b == 0.0

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="3 elements"):
            RenderStyle((0.5, 0.5))


class TestTransparency:
    def test_default_opaque(self):
        assert RenderStyle("#FF0000").transparency == pytest.approx(0.0)

    def test_explicit_transparency(self):
        s = RenderStyle("#FF0000", transparency=0.5)
        assert s.transparency == pytest.approx(0.5)

    def test_transparency_out_of_range_raises(self):
        with pytest.raises(ValueError, match="transparency"):
            RenderStyle("#FF0000", transparency=1.5)

    def test_rgba_255_alpha_from_transparency(self):
        s = RenderStyle("#FF0000", transparency=0.5)
        r, g, b, a = s.rgba_255
        assert r == 255
        assert a == pytest.approx(128, abs=1)


class TestSerialisation:
    def test_round_trip(self):
        original = RenderStyle("#3399FF", transparency=0.2)
        restored = RenderStyle.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        d = RenderStyle("#FFFFFF").to_dict()
        assert set(d.keys()) == {"r", "g", "b", "transparency"}


class TestPendingElementStyle:
    """Style field on PendingElement base class round-trips via to_dict/from_dict."""

    def _make_wall(self, style=None):
        from ifckit.elements.building import PendingWall
        from ifckit.geometry import Plane, Vec

        return PendingWall(
            name="Test Wall",
            footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 4, 0), Vec(0, 4, 0)],
            plane=Plane.world_xy(),
            height=3.0,
            style=style,
        )

    def test_wall_with_style_round_trips(self):
        from ifckit.elements.building import PendingWall
        style = RenderStyle("#CC4400")
        wall = self._make_wall(style=style)
        d = wall.to_dict()
        assert "style" in d
        restored = PendingWall.from_dict(d)
        assert restored.style == style

    def test_wall_without_style_omits_key(self):
        wall = self._make_wall()
        assert "style" not in wall.to_dict()
        assert wall.style is None
