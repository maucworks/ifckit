"""Tests for AlignmentBuilder (IFC4X3)."""
from __future__ import annotations

import math
import pytest
import ifcopenshell

from ifckit.elements.bridge import AlignmentSegment, PendingAlignment
from ifckit.geometry import Arc, Line, Vec
from ifckit.builders.bridge import AlignmentBuilder, _start_direction_rad, _start_point_2d
from ifckit.builders import default_registry
from ifckit.model import IfcModel
from ifckit.schema import IfcSchema


@pytest.fixture
def ifc4x3_model():
    return IfcModel(name="BridgeTest", schema=IfcSchema.IFC4X3, author="pytest")


@pytest.fixture
def bridge_handle(ifc4x3_model):
    site = ifc4x3_model.add_site("Site")
    return ifc4x3_model.add_bridge(site, "TestBridge")


@pytest.fixture
def alignment_handle(ifc4x3_model, bridge_handle):
    site = ifc4x3_model.add_site("Site")  # add_alignment requires SiteHandle
    return ifc4x3_model.add_alignment(site, "TestAlignment")


def _line_seg() -> AlignmentSegment:
    line = Line(start=Vec(0, 0, 0), end=Vec(10, 0, 0))
    return AlignmentSegment(geometry=line)


def _arc_seg() -> AlignmentSegment:
    # CCW arc, 90 degrees, radius 5
    # center=(0,5,0), normal=Z, start=(0,0,0) (bottom of circle), CCW 90°
    arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1), start=Vec(0, 0, 0), angle=math.radians(90))
    return AlignmentSegment(geometry=arc)


def _arc_seg_cw() -> AlignmentSegment:
    # CW arc (negative angle), radius 5
    # center=(0,-5,0), normal=Z, start=(0,0,0), CW 90°
    arc = Arc(center=Vec(0, -5, 0), normal=Vec(0, 0, 1), start=Vec(0, 0, 0), angle=math.radians(-90))
    return AlignmentSegment(geometry=arc)


# --- helper function tests ---

class TestHelpers:
    def test_start_direction_line(self):
        seg = _line_seg()
        angle = _start_direction_rad(seg)
        assert angle == pytest.approx(0.0)

    def test_start_direction_line_diagonal(self):
        line = Line(start=Vec(0, 0, 0), end=Vec(1, 1, 0))
        seg = AlignmentSegment(geometry=line)
        angle = _start_direction_rad(seg)
        assert angle == pytest.approx(math.pi / 4)

    def test_start_direction_arc(self):
        seg = _arc_seg()
        angle = _start_direction_rad(seg)
        # Arc center (0,5), start at bottom of circle (0,0), tangent points +X
        assert angle == pytest.approx(0.0, abs=1e-9)

    def test_start_point_2d_line(self):
        seg = _line_seg()
        pt = _start_point_2d(seg)
        assert pt == (0.0, 0.0)

    def test_start_point_2d_arc(self):
        seg = _arc_seg()
        pt = _start_point_2d(seg)
        # Arc start: center(0,5) + r*(-sin(90°), -cos(90°)+...) — check actual start
        geom = seg.geometry
        assert pt == pytest.approx((geom.start.x, geom.start.y))


# --- AlignmentBuilder tests ---

class TestAlignmentBuilder:
    def test_returns_alignment_entity(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_line_seg()])
        builder = AlignmentBuilder()
        result = builder.build(
            ifc4x3_model.ifc_file,
            pending,
            alignment_handle.entity,
            None,
        )
        assert result.is_a("IfcAlignment")

    def test_creates_alignment_horizontal(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_line_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        horizontals = ifc4x3_model.ifc_file.by_type("IfcAlignmentHorizontal")
        assert len(horizontals) == 1
        assert horizontals[0].Name == "A1_H"

    def test_line_segment_created(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_line_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        segs = ifc4x3_model.ifc_file.by_type("IfcAlignmentSegment")
        assert len(segs) == 1
        params = segs[0].DesignParameters
        assert params.PredefinedType == "LINE"
        assert params.SegmentLength == pytest.approx(10.0)

    def test_arc_segment_ccw(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_arc_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        segs = ifc4x3_model.ifc_file.by_type("IfcAlignmentSegment")
        assert len(segs) == 1
        params = segs[0].DesignParameters
        assert params.PredefinedType == "CIRCULARARC"
        assert params.StartRadiusOfCurvature == pytest.approx(5.0)

    def test_arc_segment_cw_negative_radius(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_arc_seg_cw()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        segs = ifc4x3_model.ifc_file.by_type("IfcAlignmentSegment")
        params = segs[0].DesignParameters
        # CW turn → negative radius
        assert params.StartRadiusOfCurvature == pytest.approx(-5.0)

    def test_multiple_segments(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_line_seg(), _arc_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        segs = ifc4x3_model.ifc_file.by_type("IfcAlignmentSegment")
        assert len(segs) == 2

    def test_nested_under_horizontal(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="A1", segments=[_line_seg(), _arc_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        nests = ifc4x3_model.ifc_file.by_type("IfcRelNests")
        # One nesting: alignment→horizontal, one: horizontal→segments
        horiz = ifc4x3_model.ifc_file.by_type("IfcAlignmentHorizontal")[0]
        nested_to_horiz = [
            r for r in nests if r.RelatingObject == horiz
        ]
        assert len(nested_to_horiz) == 1
        assert len(nested_to_horiz[0].RelatedObjects) == 2

    def test_no_name_alignment(self, ifc4x3_model, alignment_handle):
        pending = PendingAlignment(name="", segments=[_line_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        horizontals = ifc4x3_model.ifc_file.by_type("IfcAlignmentHorizontal")
        # When name is None, builder passes "" which IFC stores as None
        assert horizontals[0].Name in ("", None)

    def test_file_parses_after_save(self, ifc4x3_model, alignment_handle, tmp_path):
        pending = PendingAlignment(name="A1", segments=[_line_seg(), _arc_seg()])
        builder = AlignmentBuilder()
        builder.build(ifc4x3_model.ifc_file, pending, alignment_handle.entity, None)
        path = str(tmp_path / "alignment.ifc")
        ifc4x3_model.save(path)
        reloaded = ifcopenshell.open(path)
        assert len(reloaded.by_type("IfcAlignmentSegment")) == 2

    def test_entity_type(self):
        assert AlignmentBuilder.entity_type == "alignment"

    def test_in_default_registry(self):
        reg = default_registry()
        builder = reg.get("alignment")
        assert isinstance(builder, AlignmentBuilder)
