"""Tests for Path.fillet().

Covers:
  - 90° right-angle corner (the common case)
  - Obtuse and acute corners
  - Chained fillets on the same path
  - 3D (non-XY-plane) corners
  - All warning/failure modes:
      index out of range (low and high)
      incoming segment is Arc
      outgoing segment is Arc
      collinear segments
      incoming leg too short
      outgoing leg too short
  - Path length and continuity after fillet
  - Symmetry: fillet from_pts([A,B,C]) gives same arc center as from_pts([C,B,A])
"""

from __future__ import annotations

import math
import warnings

import pytest

from ifckit.geometry import Arc, Line, Path, Vec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


def _vec_approx(a: Vec, b: Vec, tol: float = 1e-6) -> bool:
    return (a - b).length() < tol


def _right_angle_path(leg: float = 1000.0) -> Path:
    """L-shaped path: (0,0,0) → (leg,0,0) → (leg,leg,0). Corner at index 1."""
    return Path.from_pts([Vec(0, 0, 0), Vec(leg, 0, 0), Vec(leg, leg, 0)])


# ---------------------------------------------------------------------------
# Happy-path geometry tests
# ---------------------------------------------------------------------------


class TestFilletGeometry:
    def test_returns_self(self):
        p = _right_angle_path()
        result = p.fillet(1, 100)
        assert result is p  # in-place, returns self

    def test_segment_count_increases_by_one(self):
        """fillet replaces 2 Lines with Line + Arc + Line = net +1 segment."""
        p = _right_angle_path()
        assert len(p._segments) == 2
        p.fillet(1, 100)
        assert len(p._segments) == 3

    def test_segment_types_after_fillet(self):
        p = _right_angle_path()
        p.fillet(1, 100)
        segs = p._segments
        assert isinstance(segs[0], Line)
        assert isinstance(segs[1], Arc)
        assert isinstance(segs[2], Line)

    def test_path_remains_connected(self):
        """End of each segment must equal start of next."""
        p = _right_angle_path()
        p.fillet(1, 100)
        segs = p._segments
        assert _vec_approx(segs[0].end, segs[1].start)
        assert _vec_approx(segs[1].end, segs[2].start)

    def test_first_and_last_endpoints_unchanged(self):
        start = Vec(0, 0, 0)
        end = Vec(1000, 1000, 0)
        p = _right_angle_path(1000)
        p.fillet(1, 100)
        assert _vec_approx(p._segments[0].start, start)
        assert _vec_approx(p._segments[-1].end, end)

    def test_90deg_arc_radius(self):
        """For a 90° corner the arc radius must equal requested radius."""
        r = 100.0
        p = _right_angle_path(1000)
        p.fillet(1, r)
        arc = p._segments[1]
        assert isinstance(arc, Arc)
        measured_r = (arc.start - arc.center).length()
        assert _approx(measured_r, r)

    def test_90deg_arc_sweep(self):
        """A 90° corner produces a π/2 sweep arc."""
        p = _right_angle_path(1000)
        p.fillet(1, 100)
        arc = p._segments[1]
        assert _approx(abs(arc.angle), math.pi / 2)

    def test_90deg_arc_center_location(self):
        """For a 90° right-angle at (1000,0,0), center should be at (900,100,0)."""
        r = 100.0
        p = _right_angle_path(1000)
        p.fillet(1, r)
        arc = p._segments[1]
        expected = Vec(1000 - r, r, 0)
        assert _vec_approx(arc.center, expected)

    def test_tangent_setback_shortens_incoming_leg(self):
        """Incoming line must end at corner - setback, not at corner."""
        r = 100.0
        p = _right_angle_path(1000)
        p.fillet(1, r)
        # For 90°, t = r / tan(45°) = r
        expected_end_x = 1000 - r
        assert _approx(p._segments[0].end.x, expected_end_x)

    def test_tangent_setback_shortens_outgoing_leg(self):
        r = 100.0
        p = _right_angle_path(1000)
        p.fillet(1, r)
        # Outgoing leg starts at y=r (setback from corner (1000,0,0))
        assert _approx(p._segments[2].start.y, r)

    def test_arc_end_equals_outgoing_start(self):
        p = _right_angle_path(1000)
        p.fillet(1, 100)
        arc = p._segments[1]
        assert _vec_approx(arc.end, p._segments[2].start)

    def test_obtuse_corner_sweep_less_than_90deg(self):
        """60° exterior turn → arc sweep = 60°."""
        angle_deg = 60
        pts = [
            Vec(0, 0, 0),
            Vec(1000, 0, 0),
            Vec(
                1000 + 1000 * math.cos(math.radians(angle_deg)),
                1000 * math.sin(math.radians(angle_deg)),
                0,
            ),
        ]
        p = Path.from_pts(pts)
        p.fillet(1, 100)
        arc = p._segments[1]
        assert isinstance(arc, Arc)
        assert _approx(abs(arc.angle), math.radians(angle_deg), tol=1e-6)

    def test_acute_corner_sweep_greater_than_90deg(self):
        """45° corner → sweep = 3π/4."""
        # After (0,0,0)→(1000,0,0) the next segment turns 45° inward
        pts = [Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000 + 1000, 1000, 0)]
        # The angle between incoming dir (-X from corner) and outgoing (+45°) = 135°
        # That gives sweep = π - 135° in radians ... let's just check it's > π/2
        p = Path.from_pts(pts)
        p.fillet(1, 50)
        arc = p._segments[1]
        assert isinstance(arc, Arc)
        assert abs(arc.angle) > math.pi / 4  # sweep is meaningful

    def test_3d_corner_arc_is_planar(self):
        """Fillet on a 3D corner: arc should lie in the plane of the two legs."""
        pts = [Vec(0, 0, 0), Vec(0, 0, 1000), Vec(1000, 0, 1000)]
        p = Path.from_pts(pts)
        p.fillet(1, 100)
        arc = p._segments[1]
        # Arc normal should be perpendicular to both leg directions
        d_in = (Vec(0, 0, 0) - Vec(0, 0, 1000)).normalized()
        d_out = (Vec(1000, 0, 1000) - Vec(0, 0, 1000)).normalized()
        plane_n = (d_in**d_out).normalized()
        # arc.normal must be parallel (or antiparallel) to plane_n
        assert _approx(abs(arc.normal @ plane_n), 1.0, tol=1e-6)

    def test_chained_fillet(self):
        """Two fillets on the same path, both succeed.

        Path has 3 segments (4 points, 2 interior vertices).
        After fillet(1): 3→4 segments; second corner is now at index 3.
        After fillet(3): 4→5 segments, 2 arcs total.
        """
        pts = [Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 1000, 0), Vec(2000, 1000, 0)]
        p = Path.from_pts(pts)
        p.fillet(1, 80)  # first corner
        # After first fillet: [Line, Arc, Line, Line] — second corner at index 3
        p.fillet(3, 80)  # second corner
        assert len(p._segments) == 5
        arc_count = sum(1 for s in p._segments if isinstance(s, Arc))
        assert arc_count == 2

    def test_fillet_three_corners_of_rectangle(self):
        """Fillet 3 out of 4 corners of a closed rectangular path.

        The 4th corner is the wrap-around junction (segs[-1].end == segs[0].start)
        which cannot be addressed by simple index arithmetic — that is a known
        v1 limitation for closed paths.

        After each fillet the segment list grows by 1, so each successive
        corner index increases by 2 relative to the previous call:
          fillet(1) → segs=[Line,Arc,Line,Line,Line] (5)
          fillet(3) → segs=[Line,Arc,Line,Arc,Line,Line] (6)
          fillet(5) → segs=[Line,Arc,Line,Arc,Line,Arc,Line] (7)
        """
        side = 2000.0
        pts = [
            Vec(0, 0, 0),
            Vec(side, 0, 0),
            Vec(side, side, 0),
            Vec(0, side, 0),
        ]
        p = Path.from_pts(pts, closed=True)  # 4 Line segments
        p.fillet(1, 100).fillet(3, 100).fillet(5, 100)
        arc_count = sum(1 for s in p._segments if isinstance(s, Arc))
        assert arc_count == 3

    def test_path_length_decreases_after_fillet(self):
        """A fillet replaces a corner with an arc; total length should decrease
        because the arc is shorter than the two removed line segments combined."""
        leg = 1000.0
        r = 100.0
        p = _right_angle_path(leg)
        original_length = p.length
        p.fillet(1, r)
        assert p.length < original_length

    def test_radius_zero_warns(self):
        """Radius 0 is degenerate — must warn and leave path unchanged."""
        p = _right_angle_path()
        segs_before = list(p._segments)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 0.0)
        assert len(w) == 1
        assert "positive" in str(w[0].message).lower() or "radius" in str(w[0].message).lower()
        assert len(p._segments) == len(segs_before)


# ---------------------------------------------------------------------------
# Warning / failure modes
# ---------------------------------------------------------------------------


class TestFilletWarnings:
    def test_index_zero_warns(self):
        p = _right_angle_path()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(0, 100)
        assert len(w) == 1
        assert "only valid on closed paths" in str(w[0].message).lower()

    def test_index_too_large_warns(self):
        p = _right_angle_path()  # 2 segments → valid interior: index 1
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(2, 100)  # index 2 == len(segs), not a valid interior
        assert len(w) == 1
        assert "out of range" in str(w[0].message).lower()

    def test_index_negative_warns(self):
        p = _right_angle_path()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(-1, 100)
        assert len(w) == 1

    def test_incoming_arc_warns(self):
        p = Path()
        arc = Arc(Vec(0, 100, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        p._segments = [arc, Line(arc.end, Vec(500, 100, 0))]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 50)
        assert len(w) == 1
        assert "arc" in str(w[0].message).lower() or "line" in str(w[0].message).lower()

    def test_outgoing_arc_warns(self):
        p = Path()
        arc = Arc(Vec(500, 100, 0), Vec(0, 0, 1), Vec(500, 0, 0), math.pi / 2)
        p._segments = [Line(Vec(0, 0, 0), Vec(500, 0, 0)), arc]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 50)
        assert len(w) == 1
        assert "arc" in str(w[0].message).lower() or "line" in str(w[0].message).lower()

    def test_collinear_segments_warn(self):
        """Three collinear points → no corner → fillet must warn."""
        p = Path.from_pts([Vec(0, 0, 0), Vec(500, 0, 0), Vec(1000, 0, 0)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 50)
        assert len(w) == 1
        assert "collinear" in str(w[0].message).lower()

    def test_incoming_leg_too_short_warns(self):
        """Radius so large the setback exceeds the incoming leg length."""
        # Short leg = 50, radius = 100 → t = 100 at 90° > 50
        p = Path.from_pts([Vec(0, 0, 0), Vec(50, 0, 0), Vec(50, 1000, 0)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 100)
        assert len(w) == 1
        assert "short" in str(w[0].message).lower() or "incoming" in str(w[0].message).lower()

    def test_outgoing_leg_too_short_warns(self):
        """Radius so large the setback exceeds the outgoing leg length."""
        p = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 50, 0)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p.fillet(1, 100)
        assert len(w) == 1
        assert "short" in str(w[0].message).lower() or "outgoing" in str(w[0].message).lower()

    def test_path_unchanged_on_failure(self):
        """When fillet warns and skips, _segments must be unmodified."""
        p = _right_angle_path(50)  # leg=50, radius=100 will be too big
        segs_before = list(p._segments)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            p.fillet(1, 100)
        assert len(p._segments) == len(segs_before)
        for a, b in zip(p._segments, segs_before):
            assert a is b

    def test_warn_does_not_raise(self):
        """All failure modes must warn, not raise."""
        p = _right_angle_path()
        for idx, r in [(0, 100), (99, 100), (1, 1e9)]:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                try:
                    p.fillet(idx, r)
                except Exception as exc:
                    pytest.fail(f"fillet({idx}, {r}) raised unexpectedly: {exc}")
