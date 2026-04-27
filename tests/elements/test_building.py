"""Tests for PendingWall and PendingSlab."""
import pytest
from ifckit.geometry import Vec, Plane
from ifckit.elements.building import PendingWall, PendingSlab


FOOTPRINT = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.3, 0), Vec(0, 0.3, 0)]
PLANE = Plane.world_xy()


class TestPendingWall:
    def test_element_type(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0)
        assert w.element_type == "basic_wall"

    def test_fields(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, name="W1")
        assert w.name == "W1"
        assert w.height == pytest.approx(3.0)
        assert len(w.footprint) == 4
        assert w.clip_data is None

    def test_clip_data(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, clip_data={"plane": [0, 0, 1, 2]})
        assert w.clip_data is not None

    def test_to_dict(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, name="W1")
        d = w.to_dict()
        assert d["type"] == "basic_wall"
        assert d["name"] == "W1"
        assert d["height"] == pytest.approx(3.0)
        assert len(d["footprint"]) == 4
        assert isinstance(d["footprint"][0], tuple)

    def test_to_dict_with_clip(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, clip_data={"x": 1})
        d = w.to_dict()
        assert "clip_data" in d

    def test_from_dict_roundtrip(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, name="W1")
        d = w.to_dict()
        w2 = PendingWall.from_dict(d)
        assert w2.name == "W1"
        assert w2.height == pytest.approx(3.0)
        assert len(w2.footprint) == 4
        assert w2.footprint[0].equals(FOOTPRINT[0])

    def test_from_dict_missing_footprint_raises(self):
        with pytest.raises(ValueError, match="footprint"):
            PendingWall.from_dict({"height": 3.0})

    def test_from_dict_missing_height_raises(self):
        with pytest.raises(ValueError, match="height"):
            PendingWall.from_dict({"footprint": [(0, 0, 0)]})

    def test_repr(self):
        w = PendingWall(FOOTPRINT, PLANE, 3.0, name="W1")
        assert "PendingWall" in repr(w)

    def test_footprint_is_copy(self):
        pts = list(FOOTPRINT)
        w = PendingWall(pts, PLANE, 3.0)
        pts.append(Vec(99, 99, 0))
        assert len(w.footprint) == 4


class TestPendingSlab:
    def test_element_type(self):
        s = PendingSlab(FOOTPRINT, PLANE, 0.2)
        assert s.element_type == "basic_slab"

    def test_fields(self):
        s = PendingSlab(FOOTPRINT, PLANE, 0.2, name="S1")
        assert s.name == "S1"
        assert s.thickness == pytest.approx(0.2)
        assert len(s.footprint) == 4

    def test_to_dict(self):
        s = PendingSlab(FOOTPRINT, PLANE, 0.2, name="S1")
        d = s.to_dict()
        assert d["type"] == "basic_slab"
        assert d["thickness"] == pytest.approx(0.2)

    def test_from_dict_roundtrip(self):
        s = PendingSlab(FOOTPRINT, PLANE, 0.2, name="S1")
        d = s.to_dict()
        s2 = PendingSlab.from_dict(d)
        assert s2.name == "S1"
        assert s2.thickness == pytest.approx(0.2)

    def test_from_dict_missing_footprint_raises(self):
        with pytest.raises(ValueError, match="footprint"):
            PendingSlab.from_dict({"thickness": 0.2})

    def test_from_dict_missing_thickness_raises(self):
        with pytest.raises(ValueError, match="thickness"):
            PendingSlab.from_dict({"footprint": [(0, 0, 0)]})

    def test_clip_data_optional(self):
        s = PendingSlab(FOOTPRINT, PLANE, 0.2)
        assert s.clip_data is None
