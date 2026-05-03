"""Tests for PendingSpace."""
import pytest
from ifckit.geometry import Vec
from ifckit.elements.space import PendingSpace
from ifckit.elements.style import RenderStyle


FOOTPRINT = [Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)]


class TestPendingSpace:
    def test_element_type(self):
        s = PendingSpace(FOOTPRINT, 3.0)
        assert s.element_type == "basic_space"

    def test_fields_defaults(self):
        s = PendingSpace(FOOTPRINT, 3.0)
        assert s.height == pytest.approx(3.0)
        assert len(s.footprint) == 4
        assert s.name == ""
        assert s.long_name == ""
        assert s.predefined_type == "SPACE"
        assert s.style is None
        assert s.hatch_pattern == ""

    def test_fields_explicit(self):
        s = PendingSpace(FOOTPRINT, 2.7, name="1.01", long_name="Office",
                         predefined_type="PARKING")
        assert s.name == "1.01"
        assert s.long_name == "Office"
        assert s.predefined_type == "PARKING"

    def test_to_dict_minimal(self):
        s = PendingSpace(FOOTPRINT, 3.0)
        d = s.to_dict()
        assert d["type"] == "basic_space"
        assert d["height"] == pytest.approx(3.0)
        assert len(d["footprint"]) == 4
        assert isinstance(d["footprint"][0], tuple)
        assert "long_name" not in d        # not written when empty
        assert "predefined_type" not in d  # not written when default

    def test_to_dict_full(self):
        s = PendingSpace(FOOTPRINT, 2.7, name="1.01", long_name="Office",
                         predefined_type="PARKING", hatch_pattern="ANSI31")
        d = s.to_dict()
        assert d["name"] == "1.01"
        assert d["long_name"] == "Office"
        assert d["predefined_type"] == "PARKING"
        assert d["hatch_pattern"] == "ANSI31"

    def test_roundtrip_minimal(self):
        s = PendingSpace(FOOTPRINT, 3.0)
        d = s.to_dict()
        s2 = PendingSpace.from_dict(d)
        assert s2.height == pytest.approx(3.0)
        assert len(s2.footprint) == 4
        assert s2.footprint[0].equals(FOOTPRINT[0])
        assert s2.predefined_type == "SPACE"
        assert s2.long_name == ""

    def test_roundtrip_full(self):
        style = RenderStyle((200, 100, 50))
        s = PendingSpace(FOOTPRINT, 2.7, name="1.01", long_name="Meeting",
                         predefined_type="PARKING", style=style,
                         hatch_pattern="ANSI31")
        d = s.to_dict()
        s2 = PendingSpace.from_dict(d)
        assert s2.name == "1.01"
        assert s2.long_name == "Meeting"
        assert s2.predefined_type == "PARKING"
        assert s2.hatch_pattern == "ANSI31"
        assert s2.style is not None
        assert s2.style.r == pytest.approx(200 / 255, abs=1e-3)

    def test_from_dict_missing_footprint_raises(self):
        with pytest.raises((KeyError, ValueError)):
            PendingSpace.from_dict({"height": 3.0})

    def test_from_dict_missing_height_raises(self):
        with pytest.raises((KeyError, ValueError)):
            PendingSpace.from_dict({"footprint": [[0, 0, 0], [1, 0, 0], [1, 1, 0]]})

    def test_registered_as_basic_space(self):
        from ifckit.elements.registry import ElementRegistry
        cls = ElementRegistry.get("basic_space")
        assert cls is PendingSpace

    def test_from_json_polymorphic(self):
        import json
        from ifckit.elements.base import PendingElement
        d = PendingSpace(FOOTPRINT, 3.0, name="R1").to_dict()
        s = PendingElement.from_json(json.dumps(d))
        assert isinstance(s, PendingSpace)
        assert s.name == "R1"
