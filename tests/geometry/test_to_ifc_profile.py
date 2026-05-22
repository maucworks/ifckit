# This file was generated with the assistance of an AI coding tool.
"""Tests for Path.to_ifc_profile() — arc-preserving IFC profile conversion."""

import math

import ifcopenshell
import pytest

from ifckit.geometry import Path, Plane, Vec
from ifckit.geometry.primitives import Arc


@pytest.fixture
def ifc():
    return ifcopenshell.file(schema="IFC4")


def _rect_spine(wx=1000.0, wy=800.0):
    return Path.from_pts(
        [Vec(0, 0, 0), Vec(wx, 0, 0), Vec(wx, wy, 0), Vec(0, wy, 0)],
        Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        closed=True,
    )


class TestToIfcProfileRectangle:
    """Plain rectangle — no arcs, lines only."""

    def test_profile_type(self, ifc):
        prof = _rect_spine().to_ifc_profile(ifc)
        assert prof.is_a("IfcArbitraryClosedProfileDef")

    def test_outer_curve_is_composite(self, ifc):
        prof = _rect_spine().to_ifc_profile(ifc)
        assert prof.OuterCurve.is_a("IfcCompositeCurve")

    def test_segment_count(self, ifc):
        prof = _rect_spine().to_ifc_profile(ifc)
        assert len(prof.OuterCurve.Segments) == 4

    def test_all_segments_are_polylines(self, ifc):
        prof = _rect_spine().to_ifc_profile(ifc)
        for seg in prof.OuterCurve.Segments:
            assert seg.ParentCurve.is_a("IfcPolyline")

    def test_requires_closed_path(self, ifc):
        open_path = Path.from_pts(
            [Vec(0, 0, 0), Vec(100, 0, 0)],
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=False,
        )
        with pytest.raises(ValueError, match="closed"):
            open_path.to_ifc_profile(ifc)


class TestToIfcProfileArcs:
    """Filleted rectangle — 4 arcs + 4 lines."""

    @pytest.fixture
    def filleted(self):
        spine = _rect_spine()
        spine.fillet([0, 1, 2, 3], 100)
        return spine

    def test_segment_count(self, ifc, filleted):
        prof = filleted.to_ifc_profile(ifc)
        segs = prof.OuterCurve.Segments
        assert len(segs) == 8

    def test_arc_count(self, ifc, filleted):
        prof = filleted.to_ifc_profile(ifc)
        arcs = [s for s in prof.OuterCurve.Segments if s.ParentCurve.is_a("IfcTrimmedCurve")]
        assert len(arcs) == 4

    def test_arc_trim_angles_in_radians(self, ifc, filleted):
        """IFC IfcTrimmedCurve PARAMETER trim values are in radians."""
        prof = filleted.to_ifc_profile(ifc)
        for seg in prof.OuterCurve.Segments:
            pc = seg.ParentCurve
            if not pc.is_a("IfcTrimmedCurve"):
                continue
            t1 = pc.Trim1[0].wrappedValue
            t2 = pc.Trim2[0].wrappedValue
            assert t1 == pytest.approx(0.0)
            # right-angle corner fillet → π/2 radians
            assert t2 == pytest.approx(math.pi / 2, abs=0.001)
            assert pc.MasterRepresentation == "PARAMETER"

    def test_arc_radius(self, ifc, filleted):
        prof = filleted.to_ifc_profile(ifc)
        for seg in prof.OuterCurve.Segments:
            pc = seg.ParentCurve
            if pc.is_a("IfcTrimmedCurve"):
                assert pc.BasisCurve.Radius == pytest.approx(100.0)

    def test_arc_center_matches_segment(self, ifc):
        """Circle center in IFC must match Arc.center."""
        spine = _rect_spine(wx=500, wy=400)
        spine.fillet([0, 1, 2, 3], 50)
        prof = spine.to_ifc_profile(ifc)
        arc_segs_ifc = [
            s for s in prof.OuterCurve.Segments if s.ParentCurve.is_a("IfcTrimmedCurve")
        ]
        arc_segs_py = [s for s in spine.segments if isinstance(s, Arc)]
        assert len(arc_segs_ifc) == len(arc_segs_py)
        for ifc_seg, py_seg in zip(arc_segs_ifc, arc_segs_py):
            loc = ifc_seg.ParentCurve.BasisCurve.Position.Location.Coordinates
            assert loc[0] == pytest.approx(py_seg.center.x, abs=0.01)
            assert loc[1] == pytest.approx(py_seg.center.y, abs=0.01)

    def test_arc_ref_dir_points_to_start(self, ifc):
        """RefDirection of IfcCircle placement must point from center to arc.start."""
        spine = _rect_spine(wx=600, wy=500)
        spine.fillet([0, 1, 2, 3], 60)
        prof = spine.to_ifc_profile(ifc)
        arc_segs_ifc = [
            s for s in prof.OuterCurve.Segments if s.ParentCurve.is_a("IfcTrimmedCurve")
        ]
        arc_segs_py = [s for s in spine.segments if isinstance(s, Arc)]
        for ifc_seg, py_seg in zip(arc_segs_ifc, arc_segs_py):
            ref = ifc_seg.ParentCurve.BasisCurve.Position.RefDirection.DirectionRatios
            to_start = (py_seg.start - py_seg.center).normalized()
            assert ref[0] == pytest.approx(to_start.x, abs=0.001)
            assert ref[1] == pytest.approx(to_start.y, abs=0.001)


class TestToIfcProfileNegativeArc:
    """Negative-angle arc (CW) must produce positive trim with flipped normal."""

    def test_negative_arc_trim_positive(self, ifc):
        center = Vec(100, 0, 0)
        normal = Vec(0, 0, 1)
        start_pt = Vec(200, 0, 0)
        neg_arc = Arc(center=center, normal=normal, start=start_pt, angle=-math.pi / 2)
        ifc_seg = Path._seg_to_ifc(ifc, neg_arc)
        t2 = ifc_seg.Trim2[0].wrappedValue
        assert t2 == pytest.approx(math.pi / 2, abs=0.001)

    def test_negative_arc_normal_flipped(self, ifc):
        center = Vec(100, 0, 0)
        normal = Vec(0, 0, 1)
        start_pt = Vec(200, 0, 0)
        neg_arc = Arc(center=center, normal=normal, start=start_pt, angle=-math.pi / 2)
        ifc_seg = Path._seg_to_ifc(ifc, neg_arc)
        axis = ifc_seg.BasisCurve.Position.Axis.DirectionRatios
        assert axis[2] == pytest.approx(-1.0)


class TestToIfcProfileWithHoles:
    """Profile with a hole → IfcArbitraryProfileDefWithVoids."""

    def test_profile_type_with_voids(self, ifc):
        outer = _rect_spine(wx=1000, wy=800).with_hole(_rect_spine(wx=200, wy=200))
        prof = outer.to_ifc_profile(ifc)
        assert prof.is_a("IfcArbitraryProfileDefWithVoids")

    def test_inner_curve_count(self, ifc):
        outer = _rect_spine(wx=1000, wy=800).with_hole(_rect_spine(wx=200, wy=200))
        prof = outer.to_ifc_profile(ifc)
        assert len(prof.InnerCurves) == 1
