"""Tests for ifckit.geometry — Line, Arc, Polyline, Path"""

import math
import pytest
from ifckit.geometry import Vec, Plane, Line, Arc, Polyline, Path


# ---------------------------------------------------------------------------
# Line
# ---------------------------------------------------------------------------


class TestLine:
    def test_direction(self):
        l = Line(Vec(0, 0, 0), Vec(3, 0, 0))
        assert l.direction.equals(Vec(1, 0, 0))

    def test_length(self):
        l = Line(Vec(0, 0, 0), Vec(0, 0, 5))
        assert l.length == pytest.approx(5.0)

    def test_midpoint(self):
        l = Line(Vec(0, 0, 0), Vec(2, 0, 0))
        assert l.midpoint.equals(Vec(1, 0, 0))

    def test_point_at(self):
        l = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        assert l.point_at(0.0).equals(Vec(0, 0, 0))
        assert l.point_at(1.0).equals(Vec(10, 0, 0))
        assert l.point_at(0.5).equals(Vec(5, 0, 0))

    def test_to_polyline(self):
        l = Line(Vec(0, 0, 0), Vec(1, 0, 0))
        pl = l.to_polyline()
        assert isinstance(pl, Polyline)
        assert len(pl) == 2

    def test_repr(self):
        l = Line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert "Line(" in repr(l)


# ---------------------------------------------------------------------------
# Arc
# ---------------------------------------------------------------------------


class TestArc:
    def _quarter_arc(self):
        """Quarter circle in XY plane, CCW, radius 1."""
        return Arc(
            center=Vec(0, 0, 0),
            normal=Vec(0, 0, 1),
            start=Vec(1, 0, 0),
            angle=math.pi / 2,
        )

    def test_radius(self):
        arc = self._quarter_arc()
        assert arc.radius == pytest.approx(1.0)

    def test_end(self):
        arc = self._quarter_arc()
        assert arc.end.equals(Vec(0, 1, 0))

    def test_midpoint(self):
        arc = self._quarter_arc()
        mid = arc.midpoint
        assert abs(mid) == pytest.approx(1.0)  # on unit circle
        assert mid.equals(Vec(math.cos(math.pi / 4), math.sin(math.pi / 4), 0))

    def test_point_at(self):
        arc = self._quarter_arc()
        assert arc.point_at(0.0).equals(Vec(1, 0, 0))
        assert arc.point_at(1.0).equals(arc.end)

    def test_length(self):
        arc = self._quarter_arc()
        assert arc.length == pytest.approx(math.pi / 2)

    def test_sample_count(self):
        arc = self._quarter_arc()
        pts = arc.sample(angle_step_deg=45.0)
        assert len(pts) == 3  # start, mid, end

    def test_sample_on_circle(self):
        arc = self._quarter_arc()
        for pt in arc.sample(5.0):
            assert abs(pt) == pytest.approx(1.0, abs=1e-6)

    def test_tangent_at_start(self):
        arc = self._quarter_arc()
        t = arc.tangent_at_start()
        # at start (1,0,0) the CCW tangent is (0,1,0)
        assert t.equals(Vec(0, 1, 0))

    def test_tangent_at_end(self):
        arc = self._quarter_arc()
        t = arc.tangent_at_end()
        # at end (0,1,0) the CCW tangent is (-1,0,0)
        assert t.equals(Vec(-1, 0, 0))

    def test_negative_angle(self):
        arc = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), -math.pi / 2)
        assert arc.end.equals(Vec(0, -1, 0))

    def test_repr(self):
        assert "Arc(" in repr(self._quarter_arc())


# ---------------------------------------------------------------------------
# Polyline
# ---------------------------------------------------------------------------


class TestPolyline:
    def _square(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        return Polyline(pts)

    def test_from_tuples(self):
        pl = Polyline.from_tuples([(0, 0, 0), (1, 0, 0)])
        assert len(pl) == 2
        assert pl.points[0] == Vec(0, 0, 0)

    def test_is_closed_flag(self):
        pl = Polyline([Vec(0, 0, 0), Vec(1, 0, 0)], closed=True)
        assert pl.is_closed

    def test_is_closed_by_points(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 0)]
        pl = Polyline(pts)
        assert pl.is_closed

    def test_is_not_closed(self):
        pl = self._square()
        assert not pl.is_closed

    def test_length(self):
        pl = Polyline([Vec(0, 0, 0), Vec(3, 0, 0), Vec(3, 4, 0)])
        assert pl.length == pytest.approx(7.0)

    def test_length_closed(self):
        # unit square closed: perimeter = 4
        pl = self._square()
        closed = pl.close()
        assert closed.length == pytest.approx(4.0)

    def test_close(self):
        pl = self._square().close()
        assert pl.is_closed
        assert pl.points[0].equals(pl.points[-1])

    def test_close_already_closed(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 0)]
        pl = Polyline(pts).close()
        # should not duplicate first point again
        assert pl.points.count(Vec(0, 0, 0)) == 2  # at index 0 and last

    def test_ensure_ccw(self):
        # CW square
        pts = [Vec(0, 0, 0), Vec(0, 1, 0), Vec(1, 1, 0), Vec(1, 0, 0)]
        pl = Polyline(pts)
        ccw = pl.ensure_ccw(Vec(0, 0, 1))
        from ifckit.geometry import _signed_area

        assert _signed_area(ccw.points, Vec(0, 0, 1)) > 0

    def test_project_to_plane(self):
        plane = Plane.world_xy()
        pts = [Vec(1, 2, 5), Vec(3, 4, 5)]
        pl = Polyline(pts).project_to_plane(plane)
        assert pl.points[0].equals(Vec(1, 2, 0))
        assert pl.points[1].equals(Vec(3, 4, 0))

    def test_iter(self):
        pl = Polyline([Vec(0, 0, 0), Vec(1, 0, 0)])
        pts = list(pl)
        assert len(pts) == 2

    def test_repr(self):
        assert "Polyline(" in repr(self._square())


# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------


class TestPath:
    def test_empty_path_length(self):
        p = Path()
        assert p.length == pytest.approx(0.0)

    def test_add_line(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0))
        assert len(p.segments) == 1
        assert p.length == pytest.approx(5.0)

    def test_add_arc(self):
        p = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        assert len(p.segments) == 1
        assert p.length == pytest.approx(math.pi / 2)

    def test_mixed_path_length(self):
        p = (
            Path()
            .add_line(Vec(0, 0, 0), Vec(5, 0, 0))
            .add_arc(Vec(5, 1, 0), Vec(0, 0, 1), Vec(5, 0, 0), math.pi / 2)
        )
        expected = 5.0 + (math.pi / 2) * 1.0
        assert p.length == pytest.approx(expected, rel=1e-3)

    def test_start_point(self):
        p = Path().add_line(Vec(1, 2, 3), Vec(4, 5, 6))
        assert p.start_point().equals(Vec(1, 2, 3))

    def test_end_point(self):
        p = Path().add_line(Vec(1, 2, 3), Vec(4, 5, 6))
        assert p.end_point().equals(Vec(4, 5, 6))

    def test_start_end_none_empty(self):
        p = Path()
        assert p.start_point() is None
        assert p.end_point() is None
        assert p.start_tangent() is None
        assert p.end_tangent() is None

    def test_start_tangent_line(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert p.start_tangent().equals(Vec(1, 0, 0))

    def test_end_tangent_line(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert p.end_tangent().equals(Vec(1, 0, 0))

    def test_sample_dedup(self):
        """Consecutive segments sharing endpoint must not duplicate it."""
        p = Path().add_line(Vec(0, 0, 0), Vec(1, 0, 0)).add_line(Vec(1, 0, 0), Vec(2, 0, 0))
        pl = p.sample()
        # should be 3 points, not 4
        assert len(pl.points) == 3

    def test_repr(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert "Path(" in repr(p)


# ---------------------------------------------------------------------------
# Coverage gap fillers
# ---------------------------------------------------------------------------


def test_polyline_single_point_not_closed():
    pl = Polyline([Vec(0, 0, 0)])
    assert not pl.is_closed


def test_ensure_ccw_already_ccw():
    """ensure_ccw on a CCW polygon returns a copy, not reversed."""
    pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
    pl = Polyline(pts)
    ccw = pl.ensure_ccw(Vec(0, 0, 1))
    from ifckit.geometry import _signed_area

    assert _signed_area(ccw.points, Vec(0, 0, 1)) > 0


def test_path_start_tangent_arc():
    arc_path = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
    t = arc_path.start_tangent()
    assert t is not None
    assert abs(t) == pytest.approx(1.0, abs=1e-6)


def test_path_end_tangent_arc():
    arc_path = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
    t = arc_path.end_tangent()
    assert t is not None
    assert abs(t) == pytest.approx(1.0, abs=1e-6)


def test_polygon_normal_xy_square():
    from ifckit.geometry import _polygon_normal

    pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
    n = _polygon_normal(pts)
    # Newell's method for flat XY polygon → should align with +Z or -Z
    assert abs(n.z) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Path.is_planar + Path.normal
# ---------------------------------------------------------------------------


class TestPathPlanar:
    def test_empty_path_is_planar(self):
        assert Path().is_planar is True

    def test_single_line_is_planar(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0))
        assert p.is_planar is True

    def test_single_arc_is_planar(self):
        p = Path().add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        assert p.is_planar is True

    def test_two_collinear_lines_planar(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0)).add_line(Vec(5, 0, 0), Vec(10, 0, 0))
        assert p.is_planar is True

    def test_two_anti_parallel_lines_planar(self):
        """Lines pointing in exactly opposite directions must still be planar (fixed precedence bug)."""
        p = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0)).add_line(Vec(5, 0, 0), Vec(0, 0, 0))
        assert p.is_planar is True

    def test_two_diverging_lines_not_planar(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(1, 0, 0)).add_line(Vec(1, 0, 0), Vec(1, 1, 0))
        # Not collinear, but still True (single-plane check can't detect 2D turns in lines-only)
        # The expected result is True — the planar check for lines only detects non-collinear case
        # if direction differs AND is not anti-parallel. A 90° turn is not collinear → not planar.
        assert p.is_planar is False

    def test_two_arcs_same_normal_planar(self):
        p = (
            Path()
            .add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
            .add_arc(Vec(2, 1, 0), Vec(0, 0, 1), Vec(2, 0, 0), math.pi / 2)
        )
        assert p.is_planar is True

    def test_two_arcs_different_normal_not_planar(self):
        p = (
            Path()
            .add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
            .add_arc(Vec(1, 0, 1), Vec(1, 0, 0), Vec(1, 0, 0), math.pi / 2)
        )
        assert p.is_planar is False

    def test_normal_arc_path_returns_arc_normal(self):
        normal = Vec(0, 0, 1)
        p = Path().add_arc(Vec(0, 1, 0), normal, Vec(0, 0, 0), math.pi / 2)
        n = p.normal
        assert n is not None
        assert abs(n.normalized() @ normal.normalized()) == pytest.approx(1.0, abs=1e-6)

    def test_normal_line_only_path_perpendicular_to_direction(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0))
        n = p.normal
        assert n is not None
        # Normal must be perpendicular to the line direction
        direction = Vec(1, 0, 0)
        assert abs(n @ direction) == pytest.approx(0.0, abs=1e-6)

    def test_normal_empty_path_is_none(self):
        # Empty path: is_planar=True but no segments → normal returns None
        assert Path().normal is None

    def test_normal_non_planar_path_is_none(self):
        p = (
            Path()
            .add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
            .add_arc(Vec(1, 0, 1), Vec(1, 0, 0), Vec(1, 0, 0), math.pi / 2)
        )
        assert p.normal is None


class TestPathPlane:
    def test_plane_single_arc(self):
        p = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(5, 0, 0), 0.5)
        plane = p.plane
        assert plane.origin.equals(Vec(5, 0, 0))
        assert plane.y_axis.equals(Vec(0, 0, 1))

    def test_plane_lines(self):
        p = Path().add_line(Vec(0, 0, 0), Vec(10, 0, 0))
        plane = p.plane
        assert plane.origin.equals(Vec(0, 0, 0))

    def test_plane_not_planar_raises(self):
        p = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(5, 0, 0), 0.5)
        p.add_arc(Vec(0, 0, 0), Vec(0, 1, 0), Vec(5, 0, 0), 0.5)
        with pytest.raises(ValueError, match="not planar"):
            _ = p.plane

    def test_plane_empty_path_raises(self):
        p = Path()
        with pytest.raises(ValueError, match="no segments"):
            _ = p.plane


class TestAssemblePath:
    def test_assemble_single_segment(self):
        from ifckit.geometry import assemble_path, assemble_path_planar
        line = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        paths = assemble_path([line])
        assert len(paths) == 1
        assert paths[0].start_point().equals(Vec(0, 0, 0))
        assert paths[0].end_point().equals(Vec(10, 0, 0))

    def test_assemble_ordered(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        l2 = Line(Vec(10, 0, 0), Vec(10, 10, 0))
        paths = assemble_path([l1, l2])
        assert len(paths) == 1
        assert paths[0].end_point().equals(Vec(10, 10, 0))

    def test_assemble_unordered(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(10, 0, 0), Vec(10, 10, 0))
        l2 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        paths = assemble_path([l1, l2])
        assert len(paths) == 2  # not connected - no shared endpoints

    def test_assemble_ordered_connected(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        l2 = Line(Vec(10, 0, 0), Vec(10, 10, 0))
        l3 = Line(Vec(10, 10, 0), Vec(10, 10, 10))
        paths = assemble_path([l1, l2, l3])  # ordered forward chain
        assert len(paths) == 1
        assert paths[0].end_point().equals(Vec(10, 10, 10))

    def test_assemble_chain_partial_order(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(10, 0, 0), Vec(10, 10, 0))
        l2 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        l3 = Line(Vec(10, 10, 0), Vec(10, 10, 10))
        paths = assemble_path([l3, l2, l1])  # ends chain together
        assert len(paths) >= 1
        p = paths[0] if paths[0].end_point().equals(Vec(10, 10, 10)) else paths[-1]
        assert p.end_point().equals(Vec(10, 10, 10))

    def test_assemble_disconnected_returns_multiple(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        l2 = Line(Vec(100, 0, 0), Vec(110, 0, 0))
        paths = assemble_path([l1, l2])
        assert len(paths) == 2

    def test_assemble_flipped_line(self):
        from ifckit.geometry import assemble_path
        l1 = Line(Vec(0, 0, 0), Vec(10, 0, 0))
        l2 = Line(Vec(20, 0, 0), Vec(10, 0, 0))  # reversed: end at (10,0,0) matches l1.start
        paths = assemble_path([l1, l2])
        assert len(paths) == 1
        assert paths[0].start_point().equals(Vec(0, 0, 0))
        assert paths[0].end_point().equals(Vec(20, 0, 0))

    def test_assemble_empty_raises(self):
        from ifckit.geometry import assemble_path
        with pytest.raises(ValueError, match="must not be empty"):
            assemble_path([])

    def test_assemble_planar_mixed_normals(self):
        from ifckit.geometry import assemble_path_planar
        c = Vec(0, 0, 0)
        n1 = Vec(0, 0, 1)
        n2 = Vec(0, 0, -1)
        a1 = Arc(c, n1, Vec(5, 0, 0), 0.5)
        a2 = Arc(c, n2, a1.end, 0.3)
        paths = assemble_path_planar([a1, a2], Vec(0, 0, 1))
        assert len(paths) == 1
        p = paths[0]
        assert len(p.segments) == 2
        assert p.is_planar
        plane = p.plane
        assert plane.y_axis.dot(Vec(0, 0, 1)) > 0

    def test_assemble_planar_flipped_start(self):
        from ifckit.geometry import assemble_path_planar
        c = Vec(0, 0, 0)
        n1 = Vec(0, 0, 1)
        a1 = Arc(c, n1, Vec(5, 0, 0), 0.5)
        a2 = Arc(c, n1, Vec(0, 5, 0), 0.3)  # not connected
        paths = assemble_path_planar([a2, a1], Vec(0, 0, 1))
        assert len(paths) == 2  # not connected
