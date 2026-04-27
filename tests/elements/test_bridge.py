"""Tests for AlignmentSegment, PendingAlignment, PendingBridgePart, PendingBridge."""
import math
import pytest
from ifckit.geometry import Vec, Line, Arc
from ifckit.elements.bridge import (
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBridge,
    PendingBridgePart,
)


LINE_SEG = Line(Vec(0, 0, 0), Vec(10, 0, 0))
ARC_SEG = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)


class TestAlignmentSegment:
    def test_line_segment_length(self):
        s = AlignmentSegment(LINE_SEG)
        assert s.length == pytest.approx(10.0)

    def test_arc_segment_length(self):
        s = AlignmentSegment(ARC_SEG)
        assert s.length == pytest.approx(math.pi / 2)

    def test_station_start_default(self):
        s = AlignmentSegment(LINE_SEG)
        assert s.station_start == pytest.approx(0.0)

    def test_station_start_set(self):
        s = AlignmentSegment(LINE_SEG, station_start=50.0)
        assert s.station_start == pytest.approx(50.0)

    def test_to_dict_line(self):
        s = AlignmentSegment(LINE_SEG, station_start=5.0)
        d = s.to_dict()
        assert d["geometry"]["segment_type"] == "line"
        assert d["station_start"] == pytest.approx(5.0)

    def test_to_dict_arc(self):
        s = AlignmentSegment(ARC_SEG)
        d = s.to_dict()
        assert d["geometry"]["segment_type"] == "arc"
        assert abs(d["geometry"]["angle_deg"] - 90.0) < 1e-6

    def test_from_dict_line_roundtrip(self):
        s = AlignmentSegment(LINE_SEG, station_start=3.0)
        d = s.to_dict()
        s2 = AlignmentSegment.from_dict(d)
        assert isinstance(s2.geometry, Line)
        assert s2.station_start == pytest.approx(3.0)

    def test_from_dict_arc_roundtrip(self):
        s = AlignmentSegment(ARC_SEG)
        d = s.to_dict()
        s2 = AlignmentSegment.from_dict(d)
        assert isinstance(s2.geometry, Arc)
        assert s2.geometry.radius == pytest.approx(ARC_SEG.radius)


class TestPendingAlignment:
    def _make(self):
        segs = [
            AlignmentSegment(LINE_SEG),
            AlignmentSegment(ARC_SEG, station_start=10.0),
        ]
        return PendingAlignment(segs, name="A1")

    def test_element_type(self):
        assert self._make().element_type == "alignment"

    def test_fields(self):
        a = self._make()
        assert a.name == "A1"
        assert len(a.segments) == 2

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["type"] == "alignment"
        assert len(d["segments"]) == 2

    def test_from_dict_roundtrip(self):
        a = self._make()
        d = a.to_dict()
        a2 = PendingAlignment.from_dict(d)
        assert a2.name == "A1"
        assert len(a2.segments) == 2

    def test_from_dict_missing_segments_raises(self):
        with pytest.raises(ValueError, match="segments"):
            PendingAlignment.from_dict({"name": "A"})

    def test_segments_is_copy(self):
        segs = [AlignmentSegment(LINE_SEG)]
        a = PendingAlignment(segs)
        segs.append(AlignmentSegment(ARC_SEG))
        assert len(a.segments) == 1


class TestPendingBridgePart:
    def test_element_type(self):
        p = PendingBridgePart(BridgePartType.DECK)
        assert p.element_type == "bridge_part"

    def test_fields(self):
        p = PendingBridgePart(BridgePartType.DECK, name="D1")
        assert p.part_type == BridgePartType.DECK
        assert p.name == "D1"
        assert p.elements == []
        assert p.alignment is None

    def test_with_alignment(self):
        a = PendingAlignment([AlignmentSegment(LINE_SEG)])
        p = PendingBridgePart(BridgePartType.DECK, alignment=a)
        assert p.alignment is a

    def test_to_dict(self):
        p = PendingBridgePart(BridgePartType.SUBSTRUCTURE, name="P1")
        d = p.to_dict()
        assert d["part_type"] == "SUBSTRUCTURE"

    def test_from_dict_roundtrip(self):
        p = PendingBridgePart(BridgePartType.FOUNDATION, name="F1")
        d = p.to_dict()
        p2 = PendingBridgePart.from_dict(d)
        assert p2.part_type == BridgePartType.FOUNDATION
        assert p2.name == "F1"

    def test_from_dict_missing_part_type_raises(self):
        with pytest.raises(ValueError):
            PendingBridgePart.from_dict({"name": "X"})


class TestPendingBridge:
    def _make(self):
        parts = [
            PendingBridgePart(BridgePartType.DECK, name="Deck"),
            PendingBridgePart(BridgePartType.SUBSTRUCTURE, name="Sub"),
        ]
        return PendingBridge(parts, name="B1")

    def test_element_type(self):
        assert self._make().element_type == "bridge"

    def test_fields(self):
        b = self._make()
        assert b.name == "B1"
        assert len(b.parts) == 2
        assert b.alignment is None

    def test_with_alignment(self):
        a = PendingAlignment([AlignmentSegment(LINE_SEG)])
        b = PendingBridge([], alignment=a, name="B")
        assert b.alignment is a

    def test_to_dict(self):
        d = self._make().to_dict()
        assert d["type"] == "bridge"
        assert len(d["parts"]) == 2

    def test_from_dict_roundtrip(self):
        b = self._make()
        d = b.to_dict()
        b2 = PendingBridge.from_dict(d)
        assert b2.name == "B1"
        assert len(b2.parts) == 2

    def test_from_dict_missing_parts_raises(self):
        with pytest.raises(ValueError, match="parts"):
            PendingBridge.from_dict({"name": "B"})

    def test_parts_is_copy(self):
        parts = [PendingBridgePart(BridgePartType.DECK)]
        b = PendingBridge(parts)
        parts.append(PendingBridgePart(BridgePartType.FOUNDATION))
        assert len(b.parts) == 1
