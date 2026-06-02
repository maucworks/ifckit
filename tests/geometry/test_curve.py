"""
Tests for ifckit.geometry.curve — Curve (NURBS/BSpline) evaluation,
transforms, serialisation, and Bezier construction.
"""

from __future__ import annotations

import math

import pytest

from ifckit.geometry import Curve, Plane, Transform, Vec

TOL = 1e-6


def _linear_curve() -> Curve:
    return Curve(
        control_points=[Vec(0, 0, 0), Vec(10, 0, 0)],
        knots=[0.0, 1.0],
        multiplicities=[2, 2],
        degree=1,
    )


def _bezier_curve() -> Curve:
    return Curve.from_tangents(
        Vec(0, 0, 0), Vec(1, 0, 0),
        Vec(1, 1, 0), Vec(0, 1, 0),
    )


def _rational_curve() -> Curve:
    return Curve(
        control_points=[Vec(1, 0, 0), Vec(0, 1, 0), Vec(-1, 0, 0)],
        knots=[0.0, 0.5, 1.0],
        multiplicities=[3, 1, 2],
        degree=2,
        weights=[1.0, 2.0, 1.0],
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_linear_curve(self):
        c = _linear_curve()
        assert c.degree == 1

    def test_degree_lt_1_raises(self):
        # knot check runs first — must be valid to reach degree check
        with pytest.raises(ValueError, match="Degree"):
            Curve(
                control_points=[Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)],
                knots=[0.0, 1.0],
                multiplicities=[3, 1],
                degree=0,
            )

    def test_knot_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="Knot vector length"):
            Curve(
                control_points=[Vec(0, 0, 0), Vec(1, 0, 0)],
                knots=[0.0, 1.0],
                multiplicities=[3, 3],
                degree=1,
            )


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_rational(self):
        assert _linear_curve().rational is False
        assert _rational_curve().rational is True

    def test_knot_domain(self):
        u0, u1 = _linear_curve().knot_domain
        assert u0 == pytest.approx(0.0)
        assert u1 == pytest.approx(1.0)

    def test_start_end_point(self):
        c = _linear_curve()
        assert (c.start_point - Vec(0, 0, 0)).length() < TOL
        assert (c.end_point - Vec(10, 0, 0)).length() < TOL

    def test_length_approximation(self):
        c = _linear_curve()
        assert c.length == pytest.approx(10.0, rel=0.05)

    def test_bezier_has_reasonable_length(self):
        c = _bezier_curve()
        assert c.length > 0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class TestEvaluation:
    def test_point_at_endpoints(self):
        c = _linear_curve()
        assert (c.point_at(0) - Vec(0, 0, 0)).length() < TOL
        assert (c.point_at(1) - Vec(10, 0, 0)).length() < TOL

    def test_point_at_midpoint(self):
        c = _linear_curve()
        mid = c.point_at(0.5)
        assert (mid - Vec(5, 0, 0)).length() < TOL

    def test_point_at_clamped(self):
        c = _linear_curve()
        assert (c.point_at(-0.5) - Vec(0, 0, 0)).length() < TOL
        assert (c.point_at(1.5) - Vec(10, 0, 0)).length() < TOL

    def test_tangent_at_linear(self):
        c = _linear_curve()
        tan = c.tangent_at(0.5)
        assert abs(tan.x - 1.0) < TOL
        assert abs(tan.y) < TOL

    def test_tangent_at_endpoint(self):
        c = _linear_curve()
        tan = c.tangent_at(0)
        assert abs(tan.x - 1.0) < TOL

    def test_sample(self):
        pts = _linear_curve().sample(5)
        assert len(pts) == 5

    def test_sample_single(self):
        pts = _linear_curve().sample(1)
        assert len(pts) == 1

    def test_rational_point_at(self):
        c = _rational_curve()
        pt = c.point_at(0.5)
        assert pt.y > 0

    def test_bezier_point_at_endpoints(self):
        c = _bezier_curve()
        assert (c.point_at(0) - Vec(0, 0, 0)).length() < TOL
        assert (c.point_at(1) - Vec(1, 1, 0)).length() < TOL


# ---------------------------------------------------------------------------
# Reverse
# ---------------------------------------------------------------------------


class TestReverse:
    def test_reverse_endpoints_swap(self):
        c = _linear_curve()
        r = c.reverse()
        assert (r.start_point - c.end_point).length() < TOL
        assert (r.end_point - c.start_point).length() < TOL

    def test_reverse_preserves_degree(self):
        c = _bezier_curve()
        r = c.reverse()
        assert r.degree == c.degree

    def test_reverse_twice_is_identity(self):
        c = _bezier_curve()
        r2 = c.reverse().reverse()
        for t in (0.0, 0.33, 0.67, 1.0):
            assert (c.point_at(t) - r2.point_at(t)).length() < 0.01


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


class TestTransform:
    def test_translate(self):
        c = _linear_curve()
        t = c.translated(Vec(0, 5, 0))
        assert (t.start_point - Vec(0, 5, 0)).length() < TOL

    def test_rotate(self):
        c = Curve.from_tangents(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(1, 0, 0), Vec(0, 0, 1),
        )
        r = c.rotated(Vec(0, 1, 0), math.pi / 2)
        assert (r.end_point - Vec(0, 0, -1)).length() < 0.01

    def test_scale(self):
        c = _linear_curve()
        s = c.scaled(2.0)
        assert (s.end_point - Vec(20, 0, 0)).length() < TOL

    def test_mirror(self):
        c = _linear_curve()
        m = c.mirrored(Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)))
        assert (m.end_point - Vec(10, 0, 0)).length() < TOL

    def test_transformed(self):
        c = _linear_curve()
        t = Transform.translation(Vec(0, 2, 0))
        r = c.transformed(t)
        assert (r.start_point - Vec(0, 2, 0)).length() < TOL

    def test_copy_is_independent(self):
        c = _linear_curve()
        cp = c.copy()
        assert (cp.point_at(0.5) - c.point_at(0.5)).length() < TOL
        assert cp is not c
        assert cp.points is not c.points


# ---------------------------------------------------------------------------
# from_tangents (Bezier)
# ---------------------------------------------------------------------------


class TestFromTangents:
    def test_default_scale(self):
        c = Curve.from_tangents(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(3, 0, 0), Vec(1, 0, 0),
        )
        assert c.degree == 3

    def test_custom_scale(self):
        c = Curve.from_tangents(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(1, 1, 0), Vec(0, 1, 0),
            scale=0.2,
        )
        assert c.degree == 3
        assert (c.point_at(0) - Vec(0, 0, 0)).length() < TOL

    def test_zero_scale(self):
        c = Curve.from_tangents(
            Vec(1, 0, 0), Vec(1, 0, 0),
            Vec(1, 0, 0), Vec(0, 1, 0),
            scale=0,
        )
        assert c.point_at(0.5).x == pytest.approx(1.0)

    def test_valid_bezier(self):
        c = Curve.from_tangents(
            Vec(0, 0, 0), Vec(1, 0, 0),
            Vec(0, 2, 0), Vec(0, 1, 0),
        )
        assert c.degree == 3
        assert len(c.points) == 4


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_to_dict_from_dict_roundtrip(self):
        c = _bezier_curve()
        d = c.to_dict()
        r = Curve.from_dict(d)
        assert r.degree == c.degree
        for i in range(len(c.points)):
            assert (r.points[i] - c.points[i]).length() < TOL

    def test_rational_roundtrip(self):
        c = _rational_curve()
        d = c.to_dict()
        r = Curve.from_dict(d)
        assert r.rational is True
        assert (r.point_at(0.5) - c.point_at(0.5)).length() < TOL

    def test_closed_flag_roundtrip(self):
        c = Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0)],
            knots=[0.0, 1.0],
            multiplicities=[5, 1],
            degree=2,
            closed=True,
        )
        d = c.to_dict()
        r = Curve.from_dict(d)
        assert r.closed is True

    def test_repr(self):
        r = repr(_linear_curve())
        assert "Curve(" in r


# ---------------------------------------------------------------------------
# to_biarcs / to_path
# ---------------------------------------------------------------------------


class TestToBiarcs:
    def test_linear_to_path(self):
        c = _linear_curve()
        p = c.to_path(tolerance=0.01)
        segs = p.segments
        assert len(segs) > 0

    def test_bezier_to_biarcs(self):
        c = _bezier_curve()
        p = c.to_biarcs(tol=0.1)
        assert len(p.segments) > 0

    def test_bezier_to_path(self):
        c = _bezier_curve()
        p = c.to_path(tolerance=0.1)
        assert len(p.segments) > 0
