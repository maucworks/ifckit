# This file was generated with the assistance of an AI coding tool.
"""Tests for Path.tween (interpolation between paths, holes included)."""

import math

import pytest

from ifckit.geometry import Path, Plane, Vec


def _rect(w, h):
    """Closed 4-line rectangle at the origin."""
    p = Path()
    p.add_line(Vec(0, 0, 0), Vec(w, 0, 0)).add_line(Vec(w, 0, 0), Vec(w, h, 0))
    p.add_line(Vec(w, h, 0), Vec(0, h, 0)).add_line(Vec(0, h, 0), Vec(0, 0, 0))
    return p


def _line_arc(length, rise):
    """Open line + 90° arc path."""
    p = Path()
    p.add_line(Vec(0, 0, 0), Vec(length, 0, 0))
    p.add_arc(Vec(length, rise, 0), Vec(0, 0, 1), Vec(length, 0, 0), math.pi / 2)
    return p


def test_tween_line_rect_count_and_spacing():
    mids = Path.tween(_rect(4, 2), _rect(6, 3), 3)
    assert len(mids) == 3
    assert [m.endpoints[1].x for m in mids] == pytest.approx([4.5, 5.0, 5.5])
    assert [m.endpoints[2].y for m in mids] == pytest.approx([2.25, 2.5, 2.75])
    for m in mids:
        assert [type(s).__name__ for s in m.segments] == ["Line"] * 4
        assert m.is_closed


def test_tween_endpoints_excluded():
    (mid,) = Path.tween(_rect(4, 2), _rect(6, 3), 1)
    assert mid.endpoints[1].x == pytest.approx(5.0)


def test_tween_arc_stays_arc():
    (mid,) = Path.tween(_line_arc(4, 1), _line_arc(6, 1.5), 1)
    assert [type(s).__name__ for s in mid.segments] == ["Line", "Arc"]
    arc = mid.segments[1]
    assert arc.radius == pytest.approx(1.25)
    assert math.degrees(arc.angle) == pytest.approx(90.0)
    assert mid.segments[0].end.equals(arc.start, tol=1e-12)


def test_tween_holes_pairwise():
    h0 = _rect(4, 2).with_hole(_rect(1, 1))
    h1 = _rect(6, 3).with_hole(_rect(2, 2))
    (mid,) = Path.tween(h0, h1, 1)
    assert len(mid.holes) == 1
    hole_verts = [(v.x, v.y) for v in mid.holes[0].endpoints]
    assert hole_verts == pytest.approx([(0, 0), (1.5, 0), (1.5, 1.5), (0, 1.5), (0, 0)])
    assert mid.holes[0].is_closed


def test_tween_full_circle_fallback():
    def circ(r):
        p = Path()
        p.add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(r, 0, 0), 2 * math.pi)
        return p

    (mid,) = Path.tween(circ(1.0), circ(2.0), 1)
    assert mid.segments[0].radius == pytest.approx(1.5)
    assert mid.is_closed


def test_tween_structure_mismatch_raises():
    with pytest.raises(ValueError, match="identical path structures"):
        Path.tween(_rect(4, 2), Path(), 1)
    other_types = Path()
    other_types.add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi)
    other_types.add_line(Vec(-1, 0, 0), Vec(0, 0, 0))
    line_line = Path()
    line_line.add_line(Vec(0, 0, 0), Vec(1, 0, 0)).add_line(Vec(1, 0, 0), Vec(2, 0, 0))
    with pytest.raises(ValueError, match="identical path structures"):
        Path.tween(line_line, other_types, 1)


def test_tween_open_vs_closed_raises():
    open_path = Path()
    open_path.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
    closed = Path()
    closed.add_line(Vec(0, 0, 0), Vec(1, 0, 0)).add_line(Vec(1, 0, 0), Vec(0, 0, 0))
    with pytest.raises(ValueError, match="identical path structures"):
        Path.tween(open_path, closed, 1)


def test_tween_hole_mismatch_raises():
    with_hole = _rect(4, 2).with_hole(_rect(1, 1))
    with pytest.raises(ValueError, match="identical path structures"):
        Path.tween(with_hole, _rect(4, 2), 1)
    other_hole = _rect(4, 2).with_hole(_line_arc(1, 0.5))
    with pytest.raises(ValueError, match="identical path structures"):
        Path.tween(with_hole, other_hole, 1)


def test_tween_arc_antipodal_normals_raise():
    a0 = Path()
    a0.add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
    a1 = Path()
    a1.add_arc(Vec(0, 0, 0), Vec(0, 0, -1), Vec(1, 0, 0), math.pi / 2)
    with pytest.raises(ValueError, match="180"):
        Path.tween(a0, a1, 1)


def test_tween_planes():
    p0 = Path(plane=Plane.world_xy())
    p0.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
    p1 = Path(plane=Plane.world_xy(origin=Vec(0, 0, 4)))
    p1.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
    (mid,) = Path.tween(p0, p1, 1)
    assert mid._plane is not None
    assert mid._plane.origin.equals(Vec(0, 0, 2))
    no_plane = Path()
    no_plane.add_line(Vec(0, 0, 0), Vec(1, 0, 0))
    with pytest.raises(ValueError, match="with or without a plane"):
        Path.tween(p0, no_plane, 1)


def test_tween_num_must_be_positive():
    with pytest.raises(ValueError, match="positive integer"):
        Path.tween(_rect(4, 2), _rect(6, 3), 0)
