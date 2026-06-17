"""
Tests for ifckit.geometry.biarc — bi-arc solver and curve approximation.
"""

from __future__ import annotations

import math

import pytest

from ifckit.geometry import Line, Vec
from ifckit.geometry.biarc import (
    _dist_to_line,
    _perp_in_plane,
    _signed_angle,
    build_arc_from_start_tangent,
    estimate_deviation,
    fit_biarcs,
    simplify_biarcs,
    solve_biarc,
)
from ifckit.geometry.primitives import Arc

TOL = 1e-6


# ---------------------------------------------------------------------------
# build_arc_from_start_tangent
# ---------------------------------------------------------------------------


class TestBuildArcFromStartTangent:
    def test_normal_arc(self):
        a, r = build_arc_from_start_tangent(
            Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0)
        )
        assert a is not None
        assert r == pytest.approx(1.0, abs=0.01)
        assert (a.end - Vec(1, 1, 0)).length() < TOL

    def test_flip_normal(self):
        a, r = build_arc_from_start_tangent(
            Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 2, 0), flip_normal=True
        )
        assert a is not None
        assert a.normal.z < 0


# ---------------------------------------------------------------------------
# solve_biarc
# ---------------------------------------------------------------------------


class TestSolveBiarc:
    def test_normal_case(self):
        a0, a1, j = solve_biarc(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(2, 1, 0), Vec(-1, 0.5, 0),
        )
        assert a0 is not None
        assert a1 is not None
        assert (j - a0.end).length() < TOL

    def test_zero_tangent_raises(self):
        from ifckit.geometry.primitives import Vec as _Vec
        with pytest.raises(ValueError):
            _Vec(0, 0, 0).normalized()

    def test_very_short_chord_returns_none(self):
        a0, a1, j = solve_biarc(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(1e-10, 0, 0), Vec(1, 0, 0),
        )
        assert a0 is None
        assert a1 is None

    def test_parallel_tangents(self):
        a0, a1, j = solve_biarc(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(2, 0, 0), Vec(1, 0, 0),
        )
        assert a0 is not None
        assert a1 is not None

    def test_antiparallel_tangents_semicircle(self):
        a0, a1, j = solve_biarc(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(0, 2, 0), Vec(-1, 0, 0),
        )
        assert a0 is not None
        assert a1 is not None


# ---------------------------------------------------------------------------
# fit_biarcs
# ---------------------------------------------------------------------------


class TestFitBiarcs:
    @staticmethod
    def _line(t):
        return Vec(10 * t, 0, 0)

    @staticmethod
    def _arc(t):
        angle = math.pi * t
        return Vec(math.cos(angle), math.sin(angle), 0)

    @staticmethod
    def _s_curve(t):
        return Vec(t * 10, math.sin(t * math.pi * 4) * 2, 0)

    def test_fits_straight_line(self):
        segments = fit_biarcs(self._line, tolerance=0.1, max_depth=5)
        assert len(segments) > 0
        assert isinstance(segments[0], Line)

    def test_fits_arc(self):
        segments = fit_biarcs(self._arc, tolerance=0.05, max_depth=8)
        assert len(segments) > 0

    def test_fits_s_curve(self):
        segments = fit_biarcs(self._s_curve, tolerance=0.5, max_depth=6)
        assert len(segments) > 0

    def test_tolerance_controls_detail(self):
        coarse = fit_biarcs(self._s_curve, tolerance=5.0, max_depth=2)
        fine = fit_biarcs(self._s_curve, tolerance=0.1, max_depth=5)
        assert len(fine) >= len(coarse)


# ---------------------------------------------------------------------------
# estimate_deviation
# ---------------------------------------------------------------------------


class TestEstimateDeviation:
    def test_zero_deviation_on_identity(self):
        segs = (Line(Vec(0, 0, 0), Vec(10, 0, 0)),)
        def f(t):
            return Vec(10 * t, 0, 0)
        dev = estimate_deviation(f, segs, 0.0, 1.0, samples=9)
        assert dev < 1e-6

    def test_nonzero_deviation(self):
        segs = (Line(Vec(0, 0, 0), Vec(5, 0, 0)),)
        def f(t):
            return Vec(10 * t, 2, 0)
        dev = estimate_deviation(f, segs, 0.0, 1.0, samples=20)
        assert dev > 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_perp_in_plane(self):
        t = Vec(1, 0, 0)
        n = Vec(0, 0, 1)
        p = _perp_in_plane(t, n)
        assert abs(p.x) < TOL
        assert abs(p.y - 1.0) < TOL
        assert abs(p.z) < TOL

    def test_perp_in_plane_parallel_vectors_zero(self):
        p = _perp_in_plane(Vec(1, 0, 0), Vec(1, 0, 0))
        assert p.length() < TOL

    def test_signed_angle(self):
        a = Vec(1, 0, 0)
        b = Vec(0, 1, 0)
        axis = Vec(0, 0, 1)
        assert _signed_angle(a, b, axis) == pytest.approx(math.pi / 2)

    def test_signed_angle_negative(self):
        a = Vec(0, 1, 0)
        b = Vec(1, 0, 0)
        axis = Vec(0, 0, 1)
        assert _signed_angle(a, b, axis) == pytest.approx(-math.pi / 2)

    def test_dist_to_line_normal(self):
        line = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        assert _dist_to_line(Vec(5, 3, 0), line) == pytest.approx(3.0)

    def test_dist_to_line_endpoint(self):
        line = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        assert _dist_to_line(Vec(12, 0, 0), line) == pytest.approx(2.0)

    def test_dist_to_line_zero_length(self):
        line = Line(Vec(5, 0, 0), Vec(5, 0, 0))
        d = _dist_to_line(Vec(10, 0, 0), line)
        assert d == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# simplify_biarcs
# ---------------------------------------------------------------------------


class TestSimplifyBiarcs:
    def test_no_change_when_no_tiny_arcs(self):
        segs = [
            Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 4),
            Arc(Vec(2, 1, 0), Vec(0, 0, 1), Vec(3, 1, 0), math.pi / 3),
        ]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert len(result) == len(segs)
        for r, s in zip(result, segs):
            assert isinstance(r, Arc)

    def test_collapses_tiny_arc_to_line(self):
        segs = [Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(101, 0, 0), 0.0005)]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert len(result) == 1
        assert isinstance(result[0], Line)

    def test_large_arc_unchanged(self):
        segs = [Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), 1.0)]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert isinstance(result[0], Arc)

    def test_merges_adjacent_lines(self):
        segs = [
            Line(Vec(0, 0, 0), Vec(1, 0, 0)),
            Line(Vec(1, 0, 0), Vec(2, 0, 0)),
            Line(Vec(2, 0, 0), Vec(3, 0, 0)),
        ]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert len(result) == 1
        assert isinstance(result[0], Line)
        assert (result[0].end - Vec(3, 0, 0)).length() < TOL

    def test_collapse_then_merge_creates_single_line(self):
        segs = [
            Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(100.5, 0, 0), 0.0005),
            Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(101.0, 0, 0), 0.0005),
        ]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert len(result) == 1
        assert isinstance(result[0], Line)

    def test_g1_on_boundary_after_collapse(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        tiny = Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(101, 0, 0), 0.0001)
        segs = [a, tiny]
        result = simplify_biarcs(segs, min_angle=0.001)
        assert len(result) >= 1
        tan_end = result[0].tangent_at_end() if isinstance(result[0], Arc) else (
            (result[0].end - result[0].start).normalized()
        )
        if len(result) >= 2:
            tan_start = result[1].tangent_at_start() if isinstance(result[1], Arc) else (
                (result[1].end - result[1].start).normalized()
            )
            assert abs(tan_end.angle_to(tan_start)) < 0.01

    def test_min_angle_zero_returns_unchanged(self):
        tiny = Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(101, 0, 0), 0.0001)
        segs = [tiny]
        result = simplify_biarcs(segs, min_angle=0.0)
        assert isinstance(result[0], Arc)

    def test_empty_list(self):
        result = simplify_biarcs([], min_angle=0.001)
        assert result == []

    def test_two_adjacent_tiny_arcs_collapsed_iterative(self):
        tiny1 = Arc(Vec(100, 0, 0), Vec(0, 0, 1), Vec(100.5, 0, 0), 0.0002)
        tiny2 = Arc(Vec(100.5, 0, 0), Vec(0, 0, 1), Vec(101.0, 0, 0), 0.0003)
        normal = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 3)
        segs = [tiny1, tiny2, normal]
        result = simplify_biarcs(segs, min_angle=0.001)
        for seg in result:
            if isinstance(seg, Arc):
                assert abs(seg.angle) >= 0.001
