"""
Tests for ifckit.geometry.intersection — geometric intersection (plane_plane).
"""

from __future__ import annotations

import pytest

from ifckit.geometry import Curve, Intersection, Plane, Transform, Vec

TOL = 1e-6


# ---------------------------------------------------------------------------
# Intersection dataclass
# ---------------------------------------------------------------------------


class TestIntersectionDataclass:
    def test_default_empty(self):
        inter = Intersection()
        assert inter.curves == []
        assert inter.points == []

    def test_transformed_empty(self):
        inter = Intersection()
        t = Transform.translation(Vec(1, 0, 0))
        r = inter.transformed(t)
        assert r.curves == []

    def test_translated(self):
        inter = Intersection(points=[Vec(0, 0, 0)])
        r = inter.translated(Vec(1, 2, 3))
        assert (r.points[0] - Vec(1, 2, 3)).length() < TOL

    def test_mirrored(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        inter = Intersection(points=[Vec(0, 0, 5)])
        r = inter.mirrored(plane)
        assert (r.points[0] - Vec(0, 0, -5)).length() < TOL

    def test_rotated(self):
        inter = Intersection(points=[Vec(1, 0, 0)])
        r = inter.rotated(Vec(0, 0, 1), 3.1415926535)
        assert (r.points[0] - Vec(-1, 0, 0)).length() < 0.01

    def test_scaled(self):
        inter = Intersection(points=[Vec(2, 0, 0)])
        r = inter.scaled(0.5)
        assert (r.points[0] - Vec(1, 0, 0)).length() < TOL


# ---------------------------------------------------------------------------
# plane_plane
# ---------------------------------------------------------------------------


class TestPlanePlane:
    def test_intersecting_planes(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        inter = Intersection.plane_plane(p1, p2)
        assert len(inter.curves) == 1
        assert isinstance(inter.curves[0], Curve)

    def test_coincident_origin(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        inter = Intersection.plane_plane(p1, p2)
        assert len(inter.curves) == 1

    def test_parallel_planes(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 5), Vec(1, 0, 0), Vec(0, 1, 0))
        inter = Intersection.plane_plane(p1, p2)
        assert inter.curves == []
        assert inter.points == []

    def test_identical_planes(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        inter = Intersection.plane_plane(p1, p2)
        assert inter.curves == []

    def test_line_is_degenerate(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))
        inter = Intersection.plane_plane(p1, p2)
        c = inter.curves[0]
        assert c.point_at(0).z == pytest.approx(0.0, abs=TOL)

    def test_curve_points_are_collinear(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        inter = Intersection.plane_plane(p1, p2)
        c = inter.curves[0]
        p0 = c.point_at(0)
        p1_ = c.point_at(0.5)
        p2_ = c.point_at(1)
        d1 = (p1_ - p0).normalized()
        d2 = (p2_ - p0).normalized()
        assert abs(abs(d1 @ d2) - 1.0) < TOL


# ---------------------------------------------------------------------------
# of dispatch
# ---------------------------------------------------------------------------


class TestOf:
    def test_plane_plane_dispatches(self):
        p1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p2 = Plane(Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))
        inter = Intersection.of(p1, p2)
        assert len(inter.curves) == 1

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError):
            Intersection.of(42, Plane.world_xy())

    def test_curve_curve_requires_occ(self):
        pytest.importorskip("OCC")
