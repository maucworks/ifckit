# This file was generated with the assistance of an AI coding tool.
"""
Tests for ifckit.geometry.spiral — Spiral primitive and plane intersection.
"""

from __future__ import annotations

import math

import pytest

from ifckit.geometry import Arc, Line, Path, Plane, Spiral, Vec

TOL = 1e-6


def _helix() -> Spiral:
    # 2 turns, radius 5, z rises 2 per radian: z(th) = 2*th.
    # ref_direction pins u=(1,0,0), v=(0,1,0).
    return Spiral.from_helix(
        Vec(0, 0, 0), Vec(0, 0, 1), 5.0, 2.0, 0.0, 4.0 * math.pi, ref_direction=Vec(1, 0, 0)
    )


def _archimedean() -> Spiral:
    return Spiral.from_archimedean(
        Vec(0, 0, 0), Vec(0, 0, 1), 1.0, 1.0, 0.0, 4.0 * math.pi, ref_direction=Vec(1, 0, 0)
    )


def _plane(origin: Vec, normal: Vec) -> Plane:
    # Deterministic frame: x = least-aligned world axis trick is inside Spiral;
    # here build an explicit orthonormal frame for the given normal.
    n = normal.normalized()
    ref = Vec(1, 0, 0) if abs(n @ Vec(1, 0, 0)) < 0.9 else Vec(0, 1, 0)
    x = (n**ref).normalized()
    y = (n**x).normalized()
    assert ((x**y) @ n) > 0.0
    return Plane(origin, x, y)


class TestSpiralBasics:
    def test_helix_endpoints_and_rise(self):
        h = _helix()
        assert h.start.equals(Vec(5, 0, 0), TOL)
        assert h.end.equals(Vec(5, 0, 8.0 * math.pi), TOL)
        assert h.length > 0.0
        assert not h.is_planar
        assert h.normal is None

    def test_planar_archimedean(self):
        s = _archimedean()
        assert s.is_planar
        assert s.normal is not None
        assert s.start.equals(Vec(1, 0, 0), TOL)
        assert s.radius_at(0.0) == pytest.approx(1.0, abs=TOL)
        assert s.num_turns == pytest.approx(2.0, abs=TOL)

    def test_reverse_round_trip(self):
        h = _helix()
        rev = h.reverse()
        assert rev.start.equals(h.end, TOL)
        assert rev.end.equals(h.start, TOL)
        assert rev.reverse().start.equals(h.start, TOL)
        assert rev.length == pytest.approx(h.length, rel=1e-6)

    def test_dict_round_trip(self):
        h = _helix()
        clone = Spiral.from_dict(h.to_dict())
        assert clone.start.equals(h.start, TOL)
        assert clone.end.equals(h.end, TOL)
        assert clone.kind == "helix"

    def test_non_uniform_transform_raises(self):
        from ifckit.geometry import Transform

        with pytest.raises(ValueError):
            _helix().transformed(Transform.scaling(1.0, 2.0, 1.0))

    def test_to_biarcs_stays_line_arc(self):
        path = _helix().to_biarcs(tol=0.5)
        assert isinstance(path, Path)
        assert len(path.segments) > 0
        assert all(isinstance(s, (Line, Arc)) for s in path.segments)

    def test_divide_count(self):
        assert len(_helix().divide(num=9)) == 9


class TestIntersectPlane:
    def test_helix_horizontal_plane_single_hit(self):
        hits = _helix().intersect_plane(_plane(Vec(0, 0, 2 * math.pi), Vec(0, 0, 1)))
        assert len(hits) == 1
        t, pt = hits[0]
        assert 0.0 <= t <= 1.0
        assert pt.equals(Vec(-5, 0, 2 * math.pi), 1e-4)

    def test_helix_vertical_plane_multi_hit(self):
        hits = _helix().intersect_plane(_plane(Vec(0, 0, 0), Vec(1, 0, 0)))
        assert len(hits) == 4
        expected = [
            Vec(0, 5, math.pi),
            Vec(0, -5, 3 * math.pi),
            Vec(0, 5, 5 * math.pi),
            Vec(0, -5, 7 * math.pi),
        ]
        for (_, pt), exp in zip(hits, expected):
            assert pt.equals(exp, 1e-4)
        ts = [t for t, _ in hits]
        assert ts == sorted(ts)
        assert all(0.0 <= t <= 1.0 for t in ts)

    def test_tangent_touch(self):
        # Plane x=5 touches the helix (radius 5) at th = 0, 2π, 4π.
        hits = _helix().intersect_plane(_plane(Vec(5, 0, 0), Vec(1, 0, 0)))
        assert len(hits) == 3
        expected = [Vec(5, 0, 0), Vec(5, 0, 4 * math.pi), Vec(5, 0, 8 * math.pi)]
        for (_, pt), exp in zip(hits, expected):
            assert pt.equals(exp, 1e-4)

    def test_coplanar_returns_empty(self):
        s = _archimedean()
        assert s.intersect_plane(Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))) == []

    def test_miss_returns_empty(self):
        assert _helix().intersect_plane(_plane(Vec(0, 0, 1000), Vec(0, 0, 1))) == []

    def test_archimedean_through_center(self):
        s = _archimedean()
        hits = s.intersect_plane(_plane(Vec(0, 0, 0), Vec(0, 1, 0)))
        assert len(hits) == 5
        radii = [1.0, 1 + math.pi, 1 + 2 * math.pi, 1 + 3 * math.pi, 1 + 4 * math.pi]
        signs = [1.0, -1.0, 1.0, -1.0, 1.0]
        for (_, pt), r, sgn in zip(hits, radii, signs):
            assert pt.equals(Vec(sgn * r, 0, 0), 1e-4)

    def test_offgrid_touch(self):
        # Helix shifted by 0.3 rad: touches at th=2π,4π fall between samples,
        # so only recursive valley descent finds them.
        h = Spiral.from_helix(
            Vec(0, 0, 0),
            Vec(0, 0, 1),
            5.0,
            2.0,
            0.3,
            0.3 + 4.0 * math.pi,
            ref_direction=Vec(1, 0, 0),
        )
        hits = h.intersect_plane(_plane(Vec(5, 0, 0), Vec(1, 0, 0)))
        assert len(hits) == 2
        for th in (2 * math.pi, 4 * math.pi):
            exp = Vec(5, 0, 2.0 * (th - 0.3))
            assert any(pt.equals(exp, 1e-4) for _, pt in hits)

    def test_many_turns_all_crossings_found(self):
        # 40 turns: scan resolution must scale (fixed 256 steps would merge).
        h = Spiral.from_helix(
            Vec(0, 0, 0), Vec(0, 0, 1), 5.0, 0.1, 0.0, 80.0 * math.pi, ref_direction=Vec(1, 0, 0)
        )
        hits = h.intersect_plane(_plane(Vec(0, 0, 0), Vec(1, 0, 0)))
        assert len(hits) == 80
        _, first = hits[0]
        _, last = hits[-1]
        assert first.equals(Vec(0, 5, 0.1 * math.pi / 2), 1e-3)
        assert last.equals(Vec(0, -5, 0.1 * (80 * math.pi - math.pi / 2)), 1e-3)

    def test_reverse_same_points(self):
        fwd = _helix().intersect_plane(_plane(Vec(0, 0, 0), Vec(1, 0, 0)))
        rev = _helix().reverse().intersect_plane(_plane(Vec(0, 0, 0), Vec(1, 0, 0)))
        assert len(fwd) == len(rev) == 4
        fwd_pts = sorted((round(p.x, 4), round(p.y, 4), round(p.z, 4)) for _, p in fwd)
        rev_pts = sorted((round(p.x, 4), round(p.y, 4), round(p.z, 4)) for _, p in rev)
        assert fwd_pts == rev_pts
