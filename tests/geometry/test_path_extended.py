"""Tests for extended Path functionality (M8)."""

import pytest

from ifckit.geometry import Arc, Line, Path, Plane, Vec


class TestIsClosed:
    def test_is_closed_false_open(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        p.add_line(Vec(1, 0, 0), Vec(2, 0, 0))
        assert not p.is_closed

    def test_is_closed_true(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        p.add_line(Vec(1, 0, 0), Vec(0, 0, 0))
        assert p.is_closed

    def test_is_closed_single_segment(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert not p.is_closed


class TestFromPts:
    def test_from_pts_open(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)]
        p = Path.from_pts(pts)
        assert len(p.segments) == 2
        assert not p.is_closed

    def test_from_pts_closed(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        p = Path.from_pts(pts, closed=True)
        assert len(p.segments) == 4
        assert p.is_closed

    def test_from_pts_too_few_raises(self):
        with pytest.raises(ValueError):
            Path.from_pts([Vec(0, 0, 0)])

    def test_from_pts_stores_plane(self):
        pl = Plane.world_xy()
        pts = [Vec(0, 0, 0), Vec(1, 0, 0)]
        p = Path.from_pts(pts, plane=pl)
        assert p._plane is pl


class TestRect:
    def test_rect_is_closed(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
        assert p.is_closed
        assert len(p.segments) == 4

    def test_rect_stores_plane(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(1, 1, 0))
        assert p._plane is pl

    def test_rect_world_coords(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
        pts = [seg.start for seg in p.segments]
        xs = sorted(set(round(v.x, 9) for v in pts))
        ys = sorted(set(round(v.y, 9) for v in pts))
        assert xs == [0.0, 4.0]
        assert ys == [0.0, 3.0]

    def test_rect_local_coords_offset_plane(self):
        pl = Plane(Vec(10, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        p = Path.rect(pl, Vec(0, 0, 0), Vec(2, 2, 0))
        pts = [seg.start for seg in p.segments]
        xs = sorted(set(round(v.x, 9) for v in pts))
        assert xs == [10.0, 12.0]


class TestMutators:
    def test_close_appends_segment(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0)])
        assert not p.is_closed
        result = p.close()
        assert result is p
        assert p.is_closed

    def test_close_noop_if_already_closed(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 0)])
        n_before = len(p.segments)
        p.close()
        assert len(p.segments) == n_before

    def test_reverse_mutates(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)])
        p.reverse()
        assert p.start_point().equals(Vec(2, 0, 0))
        assert p.end_point().equals(Vec(0, 0, 0))

    def test_reverse_returns_self(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        assert p.reverse() is p

    def test_make_planar_raises_without_plane(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        with pytest.raises(ValueError):
            p.make_planar()

    def test_make_planar_projects_points(self):
        pl = Plane.world_xy()
        p = Path.from_pts([Vec(0, 0, 5), Vec(1, 0, 3)])
        p.make_planar(plane=pl)
        for seg in p.segments:
            assert abs(seg.start.z) < 1e-9
            assert abs(seg.end.z) < 1e-9

    def test_assert_ccw_noop_on_ccw(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(1, 1, 0))
        pts_before = [seg.start for seg in p.segments]
        p.assert_ccw()
        pts_after = [seg.start for seg in p.segments]
        for a, b in zip(pts_before, pts_after):
            assert a.equals(b)

    def test_assert_ccw_flips_cw(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(1, 1, 0))
        p.reverse()
        p.assert_ccw()
        pts = [seg.start for seg in p.segments]
        from ifckit.geometry import _polygon_normal, _signed_area

        n = _polygon_normal(pts)
        area = _signed_area(pts, n)
        assert area > 0

    def test_assert_ccw_raises_on_open(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        with pytest.raises(ValueError):
            p.assert_ccw()


class TestDuplicate:
    def test_duplicate_is_independent(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)])
        q = p.duplicate()
        q.add_line(Vec(2, 0, 0), Vec(3, 0, 0))
        assert len(p.segments) == 2
        assert len(q.segments) == 3


class TestOffset:
    def test_offset_rect(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(1000, 1000, 0))
        q = p.offset(55)
        assert q.is_closed
        pts = [seg.start for seg in q.segments]
        xs = sorted(set(round(v.x, 6) for v in pts))
        ys = sorted(set(round(v.y, 6) for v in pts))
        assert abs(xs[0] - 55) < 1e-6
        assert abs(xs[1] - 945) < 1e-6
        assert abs(ys[0] - 55) < 1e-6
        assert abs(ys[1] - 945) < 1e-6

    def test_offset_raises_open(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)], plane=Plane.world_xy())
        # Open paths are now supported.  cap=False → parallel curve, cap=True → closed footprint.
        o = p.offset(10)
        assert not o.is_closed
        assert o.start_point().equals(Vec(0, 10, 0))
        assert o.end_point().equals(Vec(2, 10, 0))

        o_cap = p.offset(10, cap=True)
        assert o_cap.is_closed

    def test_offset_raises_arc(self):
        p = Path()
        p._segments.append(Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), 1.57))
        p._segments.append(Line(p.end_point(), p.start_point()))
        # Arc segments are preserved — offset produces 2 segments (arc + line)
        result = p.offset(0.1)
        assert result.is_closed
        assert any(isinstance(s, Arc) for s in result.segments)

    def test_offset_does_not_mutate_original(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(100, 100, 0))
        pts_before = [seg.start for seg in p.segments]
        p.offset(10)
        pts_after = [seg.start for seg in p.segments]
        for a, b in zip(pts_before, pts_after):
            assert a.equals(b)

    def test_offset_filleted_rect_preserves_arc_segments(self):
        """Offset of a filleted rectangle must keep Arc segments, not tessellate."""
        import math
        from ifckit.geometry.primitives import Arc as _Arc
        pl = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p = Path.from_pts(
            [Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 800, 0), Vec(0, 800, 0)],
            pl, closed=True,
        )
        p.fillet([0, 1, 2, 3], 100)
        off = p.offset(27)
        assert off.is_closed
        assert len(off.segments) == len(p.segments), "segment count must be preserved"
        arc_segs = [s for s in off.segments if isinstance(s, _Arc)]
        assert len(arc_segs) == 4, "all 4 arc corners must be preserved"
        for s in arc_segs:
            assert abs(s.radius - 73.0) < 0.01, f"expected r=73, got {s.radius}"

    def test_offset_arc_radius_decreases_inward(self):
        """Inward offset of a CCW arc reduces its radius."""
        import math
        from ifckit.geometry.primitives import Arc as _Arc
        pl = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p = Path.from_pts(
            [Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 800, 0), Vec(0, 800, 0)],
            pl, closed=True,
        )
        p.fillet([0, 1, 2, 3], 100)
        off = p.offset(50)
        for s in off.segments:
            if isinstance(s, _Arc):
                assert abs(s.radius - 50.0) < 0.01

    def test_offset_arc_continuity(self):
        """All consecutive segment pairs in offset result must share an endpoint."""
        from ifckit.geometry.primitives import Arc as _Arc
        pl = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p = Path.from_pts(
            [Vec(0, 0, 0), Vec(600, 0, 0), Vec(600, 600, 0), Vec(0, 600, 0)],
            pl, closed=True,
        )
        p.fillet([0, 1, 2, 3], 80)
        off = p.offset(30)
        segs = off.segments
        for i, s in enumerate(segs):
            nxt = segs[(i + 1) % len(segs)]
            gap = s.end.distance_to(nxt.start)
            assert gap < 1e-6, f"gap {gap:.2e} between seg {i} and {i+1}"

    def test_offset_preserves_plane(self):
        """Offset result must carry the same _plane as the original."""
        pl = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p = Path.from_pts(
            [Vec(0, 0, 0), Vec(500, 0, 0), Vec(500, 400, 0), Vec(0, 400, 0)],
            pl, closed=True,
        )
        p.fillet([0, 1, 2, 3], 60)
        off = p.offset(20)
        assert off._plane is not None
        assert off._plane.x_axis.equals(Vec(1, 0, 0))
        assert off._plane.y_axis.equals(Vec(0, 1, 0))


class TestToProfilePoints:
    def test_to_profile_points_square(self):
        pl = Plane.world_xy()
        p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
        pts = p.to_profile_points()
        assert len(pts) == 4
        xs = sorted(set(round(x, 6) for x, y in pts))
        ys = sorted(set(round(y, 6) for x, y in pts))
        assert xs == [0.0, 4.0]
        assert ys == [0.0, 3.0]

    def test_to_profile_points_raises_open(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        with pytest.raises(ValueError, match="closed"):
            p.to_profile_points(plane=Plane.world_xy())

    def test_to_profile_points_raises_no_plane(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        p.add_line(Vec(1, 0, 0), Vec(1, 1, 0))
        p.add_line(Vec(1, 1, 0), Vec(0, 1, 0))
        p.add_line(Vec(0, 1, 0), Vec(0, 0, 0))
        with pytest.raises(ValueError):
            p.to_profile_points()


class TestAssembleClassmethod:
    def test_assemble_classmethod_matches_module_function(self):
        from ifckit.geometry import assemble_path

        segs = [Line(Vec(0, 0, 0), Vec(1, 0, 0)), Line(Vec(1, 0, 0), Vec(2, 0, 0))]
        via_classmethod = Path.assemble(segs)
        via_function = assemble_path(segs)
        assert len(via_classmethod) == len(via_function)
        assert len(via_classmethod[0].segments) == len(via_function[0].segments)
