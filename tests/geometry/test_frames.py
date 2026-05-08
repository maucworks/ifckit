"""Tests for transport_frames / fixed_ref_frames (polyline parallel transport)."""
import math
import pytest
from ifckit.geometry import Vec, Plane, Path, FrameField, transport_frames, fixed_ref_frames


def _make_pts() -> list[Vec]:
    """Three control points forming a 90° corner in XY plane."""
    return [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 10, 0)]


def _straight_pts(length: float = 10.0) -> list[Vec]:
    return [Vec(0, 0, 0), Vec(length, 0, 0)]


def _straight_path(length: float = 10.0) -> Path:
    return Path().add_line(Vec(0, 0, 0), Vec(length, 0, 0))


def _quarter_arc_path() -> Path:
    """90° arc in XY plane, radius 1."""
    return Path().add_arc(
        center=Vec(0, 1, 0),
        normal=Vec(0, 0, 1),
        start=Vec(0, 0, 0),
        angle=math.pi / 2,
    )


class TestFrameField:
    def test_is_namedtuple(self):
        pts = _straight_pts()
        result = transport_frames(pts, Vec(0, 0, 1))
        assert isinstance(result, FrameField)
        assert hasattr(result, "frames")
        assert hasattr(result, "scales")

    def test_frames_equals_old_behavior(self):
        """transport_frames(...).frames matches old bare List[Plane] return."""
        pts = _straight_pts()
        old = transport_frames(pts, Vec(0, 0, 1), miter_scale=False)
        assert len(old.frames) == 2
        assert old.frames[0].x_axis.equals(old.frames[1].x_axis, tol=1e-6)

    def test_miter_scales_present(self):
        pts = _make_pts()
        result = transport_frames(pts, Vec(0, 0, 1))
        assert len(result.scales) == 3
        # endpoints get (1.0, "")
        assert result.scales[0] == (1.0, "")
        assert result.scales[2] == (1.0, "")

    def test_miter_scales_disabled(self):
        pts = _make_pts()
        result = transport_frames(pts, Vec(0, 0, 1), miter_scale=False)
        for s, a in result.scales:
            assert s == 1.0
            assert a == ""

    def test_fixed_ref_scales(self):
        pts = _make_pts()
        result = fixed_ref_frames(pts, Vec(0, 0, 1))
        assert len(result.scales) == 3
        assert result.scales[0] == (1.0, "")


class TestTransportFrames:
    """transport_frames — polyline parallel transport (Z = tangent, spine convention)."""

    def test_straight_line_two_frames(self):
        pts = _straight_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) == 2

    def test_straight_line_x_identical(self):
        pts = _straight_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert frames[0].x_axis.equals(frames[1].x_axis, tol=1e-6)

    def test_straight_line_z_is_tangent(self):
        pts = _straight_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        tangent = (pts[1] - pts[0]).normalized()
        for f in frames:
            assert f.z_axis.equals(tangent, tol=1e-6)

    def test_three_points(self):
        pts = _make_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) == 3

    def test_bisector_at_corner(self):
        pts = _make_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        bisector = (Vec(1, 1, 0)).normalized()
        assert frames[1].z_axis.equals(bisector, tol=1e-6)

    def test_frames_are_orthonormal(self):
        pts = _make_pts()
        frames = transport_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        for f in frames:
            assert f.x_axis @ f.y_axis == pytest.approx(0.0, abs=1e-6)
            assert f.x_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)
            assert f.y_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)
            assert abs(f.x_axis) == pytest.approx(1.0, abs=1e-6)
            assert abs(f.y_axis) == pytest.approx(1.0, abs=1e-6)
            assert abs(f.z_axis) == pytest.approx(1.0, abs=1e-6)

    def test_less_than_two_raises(self):
        with pytest.raises(ValueError):
            transport_frames([Vec(0, 0, 0)], Vec(0, 0, 1))

    def test_x_rotates_at_90deg_corner(self):
        pts = _make_pts()
        frames = transport_frames(pts, Vec(0, -1, 0), miter_scale=False).frames
        x0 = frames[0].x_axis
        x1 = frames[1].x_axis
        assert not x0.equals(x1, tol=1e-4)

    def test_path_overload(self):
        path = _straight_path()
        frames = transport_frames(path, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) >= 2

    def test_path_overload_arc(self):
        path = _quarter_arc_path()
        frames = transport_frames(path, Vec(0, 0, 1), angle_step_deg=45.0, miter_scale=False).frames
        assert len(frames) == 3  # start, 45°, 90°


class TestFixedRefFrames:
    """fixed_ref_frames — fixed reference direction (Z = tangent, spine convention)."""

    def test_straight_line_two_frames(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) == 2

    def test_straight_line_x_identical(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert frames[0].x_axis.equals(frames[1].x_axis, tol=1e-6)

    def test_z_is_tangent(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        tangent = (pts[1] - pts[0]).normalized()
        for f in frames:
            assert f.z_axis.equals(tangent, tol=1e-6)

    def test_frames_are_orthonormal(self):
        pts = _make_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        for f in frames:
            assert f.x_axis @ f.y_axis == pytest.approx(0.0, abs=1e-6)
            assert f.x_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)
            assert f.y_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)

    def test_less_than_two_raises(self):
        with pytest.raises(ValueError):
            fixed_ref_frames([Vec(0, 0, 0)], Vec(0, 0, 1))

    def test_x_same_as_tp_on_straight(self):
        pts = _straight_pts()
        tp = transport_frames(pts, Vec(0, 0, 1), miter_scale=False)
        fr = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False)
        assert tp.frames[0].x_axis.equals(fr.frames[0].x_axis, tol=1e-6)
        assert tp.frames[1].x_axis.equals(fr.frames[1].x_axis, tol=1e-6)

    def test_path_overload(self):
        path = _straight_path()
        frames = fixed_ref_frames(path, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) >= 2

    def test_path_overload_arc(self):
        """Arc path should be sampled and framed."""
        path = _quarter_arc_path()
        frames = transport_frames(path, Vec(0, 0, 1), angle_step_deg=45.0)
        assert len(frames) == 3  # start, 45°, 90°


class TestFixedRefFrames:
    """fixed_ref_frames — fixed reference direction (Z = tangent, spine convention)."""

    def test_straight_line_two_frames(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert len(frames) == 2

    def test_straight_line_x_identical(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        assert frames[0].x_axis.equals(frames[1].x_axis, tol=1e-6)

    def test_z_is_tangent(self):
        pts = _straight_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        tangent = (pts[1] - pts[0]).normalized()
        for f in frames:
            assert f.z_axis.equals(tangent, tol=1e-6)

    def test_frames_are_orthonormal(self):
        pts = _make_pts()
        frames = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False).frames
        for f in frames:
            assert f.x_axis @ f.y_axis == pytest.approx(0.0, abs=1e-6)
            assert f.x_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)
            assert f.y_axis @ f.z_axis == pytest.approx(0.0, abs=1e-6)

    def test_less_than_two_raises(self):
        with pytest.raises(ValueError):
            fixed_ref_frames([Vec(0, 0, 0)], Vec(0, 0, 1))

    def test_x_same_as_tp_on_straight(self):
        """On a straight line, fixed-ref and transport give the same X."""
        pts = _straight_pts()
        tp = transport_frames(pts, Vec(0, 0, 1), miter_scale=False)
        fr = fixed_ref_frames(pts, Vec(0, 0, 1), miter_scale=False)
        assert tp.frames[0].x_axis.equals(fr.frames[0].x_axis, tol=1e-6)
        assert tp.frames[1].x_axis.equals(fr.frames[1].x_axis, tol=1e-6)

    def test_path_overload(self):
        path = _straight_path()
        result = fixed_ref_frames(path, Vec(0, 0, 1), miter_scale=False)
        assert len(result.frames) >= 2

