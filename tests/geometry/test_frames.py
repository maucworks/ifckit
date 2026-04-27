"""Tests for parallel_transport_frames (Bishop frame)"""
import math
import pytest
from ifckit.geometry import Vec, Plane, Path, parallel_transport_frames


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


def _half_arc_path() -> Path:
    """180° arc in XY plane, radius 1."""
    return Path().add_arc(
        center=Vec(0, 1, 0),
        normal=Vec(0, 0, 1),
        start=Vec(0, 0, 0),
        angle=math.pi,
    )


class TestParallelTransportFrames:
    def test_straight_path_normals_identical(self):
        """Along a straight line all normals should be identical."""
        path = _straight_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1))
        n0 = frames[0].y_axis
        for f in frames[1:]:
            assert f.y_axis.equals(n0, tol=1e-6)

    def test_straight_path_tangents_identical(self):
        path = _straight_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1))
        t0 = frames[0].x_axis
        for f in frames[1:]:
            assert f.x_axis.equals(t0, tol=1e-6)

    def test_frame_count_matches_samples(self):
        path = _straight_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1), angle_step_deg=10.0)
        # straight line samples to 2 points
        assert len(frames) == 2

    def test_arc_frame_count(self):
        path = _quarter_arc_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1), angle_step_deg=45.0)
        assert len(frames) == 3  # start, 45°, 90°

    def test_frames_are_planes(self):
        path = _straight_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1))
        for f in frames:
            assert isinstance(f, Plane)

    def test_frames_are_orthonormal(self):
        path = _quarter_arc_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1), angle_step_deg=10.0)
        for f in frames:
            assert f.x_axis.dot(f.y_axis) == pytest.approx(0.0, abs=1e-6)
            assert abs(f.x_axis) == pytest.approx(1.0, abs=1e-6)
            assert abs(f.y_axis) == pytest.approx(1.0, abs=1e-6)

    def test_180_arc_no_twist(self):
        """
        180° arc: the normal vector (seed = +Z) should stay in the +Z half-space
        throughout (no axial twist).
        """
        path = _half_arc_path()
        frames = parallel_transport_frames(path, Vec(0, 0, 1), angle_step_deg=10.0)
        for f in frames:
            # z-component of normal should remain positive (no flip)
            assert f.y_axis.z > -0.01

    def test_empty_path_raises(self):
        with pytest.raises(ValueError):
            parallel_transport_frames(Path(), Vec(0, 0, 1))

    def test_seed_normal_orthogonalized(self):
        """seed_normal not orthogonal to tangent must be projected out."""
        path = _straight_path()
        # seed has a component along tangent direction
        frames = parallel_transport_frames(path, Vec(0.5, 0, 0.5))
        for f in frames:
            assert f.x_axis.dot(f.y_axis) == pytest.approx(0.0, abs=1e-6)
