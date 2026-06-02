"""
Tests for ifckit.geometry.surface — Surface (NURBS/BSpline), pure Python parts.
"""

from __future__ import annotations

import pytest

from ifckit.geometry import Plane, Surface, Transform, Vec

TOL = 1e-6


def _simple_surface() -> Surface:
    return Surface(
        control_points=[
            [Vec(0, 0, 0), Vec(5, 0, 0)],
            [Vec(0, 5, 0), Vec(5, 5, 0)],
            [Vec(0, 10, 1), Vec(5, 10, 1)],
        ],
        uknots=[0.0, 1.0],
        vknots=[0.0, 1.0],
        umults=[3, 3],
        vmults=[2, 2],
        udegree=2,
        vdegree=1,
    )


def _rational_surface() -> Surface:
    return Surface(
        control_points=[
            [Vec(1, 0, 0), Vec(1, 1, 0)],
            [Vec(0, 0, 0), Vec(0, 1, 0)],
            [Vec(-1, 0, 0), Vec(-1, 1, 0)],
        ],
        uknots=[0.0, 0.5, 1.0],
        vknots=[0.0, 1.0],
        umults=[3, 1, 2],
        vmults=[2, 2],
        udegree=2,
        vdegree=1,
        weights=[
            [1.0, 1.0],
            [2.0, 2.0],
            [1.0, 1.0],
        ],
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_simple_surface(self):
        s = _simple_surface()
        assert s.nu == 3
        assert s.nv == 2

    def test_empty_surface(self):
        s = Surface(
            control_points=[],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )
        assert s.nu == 0
        assert s.nv == 0

    def test_tuples_as_control_points(self):
        s = Surface(
            control_points=[[(0, 0, 0), (1, 0, 0)], [(0, 1, 0), (1, 1, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )
        assert s.nu == 2
        assert s.nv == 2


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_rational(self):
        assert _simple_surface().rational is False
        assert _rational_surface().rational is True

    def test_closed_flags(self):
        s = Surface(
            control_points=[[Vec(0, 0, 0)], [Vec(1, 0, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 1],
            udegree=1,
            vdegree=1,
            uclosed=True,
            vclosed=True,
        )
        assert s.uclosed is True
        assert s.vclosed is True


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


class TestTransform:
    def test_translate(self):
        s = _simple_surface()
        r = s.translated(Vec(0, 0, 10))
        assert (r.control_points[0][0] - Vec(0, 0, 10)).length() < TOL

    def test_scale(self):
        s = _simple_surface()
        r = s.scaled(2.0, 2.0, 2.0)
        assert (r.control_points[1][1] - Vec(10, 10, 0)).length() < TOL

    def test_mirror(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        s = _simple_surface()
        r = s.mirrored(plane)
        assert (r.control_points[0][1] - Vec(5, 0, 0)).length() < TOL

    def test_rotate(self):
        s = Surface(
            control_points=[[Vec(1, 0, 0)], [Vec(1, 1, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 1],
            udegree=1,
            vdegree=1,
        )
        r = s.rotated(Vec(0, 0, 1), 1.57079632679)
        assert r.control_points[0][0].y == pytest.approx(1.0, abs=TOL)

    def test_transformed(self):
        s = _simple_surface()
        t = Transform.translation(Vec(1, 2, 3))
        r = s.transformed(t)
        assert (r.control_points[0][0] - Vec(1, 2, 3)).length() < TOL

    def test_copy(self):
        s = _rational_surface()
        c = s.copy()
        assert c.rational is True
        assert c._weights is not s._weights


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_to_dict_from_dict_roundtrip(self):
        s = _simple_surface()
        d = s.to_dict()
        r = Surface.from_dict(d)
        assert r.nu == s.nu
        assert r.nv == s.nv
        assert r.udegree == s.udegree
        assert r.vdegree == s.vdegree

    def test_rational_roundtrip(self):
        s = _rational_surface()
        d = s.to_dict()
        r = Surface.from_dict(d)
        assert r.rational is True
        assert r.uclosed == s.uclosed
        assert r.vclosed == s.vclosed

    def test_closed_roundtrip(self):
        s = Surface(
            control_points=[[Vec(0, 0, 0)], [Vec(1, 0, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 1],
            udegree=1,
            vdegree=1,
            uclosed=True,
            vclosed=False,
        )
        d = s.to_dict()
        r = Surface.from_dict(d)
        assert r.uclosed is True
        assert r.vclosed is False
