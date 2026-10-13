"""Tests for ifckit.geometry.Plane"""

import pytest

from ifckit.geometry import Plane, Vec


def test_world_xy():
    p = Plane.world_xy()
    assert p.origin.equals(Vec(0, 0, 0))
    assert p.x_axis.equals(Vec(1, 0, 0))
    assert p.y_axis.equals(Vec(0, 1, 0))
    assert p.z_axis.equals(Vec(0, 0, 1))


def test_z_axis_is_cross():
    p = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    assert p.z_axis.equals(Vec(0, 0, 1))


def test_axes_are_normalized():
    p = Plane(Vec(0, 0, 0), Vec(3, 0, 0), Vec(0, 4, 0))
    assert abs(p.x_axis) == pytest.approx(1.0)
    assert abs(p.y_axis) == pytest.approx(1.0)


def test_from_origin_and_normal_z():
    p = Plane.from_origin_and_normal(Vec(1, 2, 3), Vec(0, 0, 1))
    assert p.z_axis.equals(Vec(0, 0, 1))
    assert abs(p.x_axis) == pytest.approx(1.0)
    assert abs(p.y_axis) == pytest.approx(1.0)
    assert p.x_axis.dot(p.z_axis) == pytest.approx(0.0)
    assert p.y_axis.dot(p.z_axis) == pytest.approx(0.0)


def test_from_origin_and_normal_x():
    p = Plane.from_origin_and_normal(Vec(0, 0, 0), Vec(1, 0, 0))
    assert p.z_axis.equals(Vec(1, 0, 0))


def test_from_3_pts_basic():
    p0, p1, p2 = Vec(0, 0, 0), Vec(1, 1, 0), Vec(-1, 1, 0)
    p = Plane.from_3_pts(p0, p1, p2)
    assert p.origin.equals(Vec(0, 0, 0))
    assert p.x_axis.equals(Vec(0.707, 0.707, 0).normalized())
    assert p.x_axis.dot(p.y_axis) == pytest.approx(0.0, abs=1e-10)
    assert abs(p.y_axis) == pytest.approx(1.0)


def test_from_3_pts_upright_plane():
    p = Plane.from_3_pts(Vec(1, 0, 0), Vec(1, 1, 0), Vec(1, 0, 1))
    assert p.x_axis.equals(Vec(0, 1, 0))
    assert p.y_axis.equals(Vec(0, 0, 1))
    assert p.z_axis.equals(Vec(1, 0, 0))


def test_from_3_pts_raises_on_p1_equals_p0():
    with pytest.raises(ValueError, match="p1 must differ"):
        Plane.from_3_pts(Vec(1, 2, 3), Vec(1, 2, 3), Vec(4, 5, 6))


# ---------------------------------------------------------------------------
# Plane.tween
# ---------------------------------------------------------------------------


def _rotated_about_y():
    """world_xy slerped 90° about Y: normal +Z -> +X, origin shifted."""
    return Plane(Vec(10, 0, 0), Vec(0, 0, -1), Vec(0, 1, 0))


def test_tween_count_and_spacing():
    p0 = Plane.world_xy()
    p1 = Plane(Vec(10, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    mids = Plane.tween(p0, p1, 3)
    assert len(mids) == 3
    assert [m.origin.x for m in mids] == pytest.approx([2.5, 5.0, 7.5])
    # Endpoints excluded, axes unchanged for pure translation.
    assert all(m.x_axis.equals(Vec(1, 0, 0)) for m in mids)


def test_tween_slews_normal():
    """Perpendicular normals (dot == 0) tween fine — no dot threshold."""
    p0 = Plane.world_xy()
    mids = Plane.tween(p0, _rotated_about_y(), 1)
    assert len(mids) == 1
    (mid,) = mids
    assert (p0.z_axis @ _rotated_about_y().z_axis) == pytest.approx(0.0)
    assert mid.z_axis.equals(Vec(0.707106781, 0, 0.707106781))
    assert mid.origin.equals(Vec(5, 0, 0))
    assert (mid.x_axis**mid.y_axis).equals(mid.z_axis)


def test_tween_twist_about_normal():
    """90° in-plane twist interpolates through 45°."""
    p0 = Plane.world_xy()
    p1 = Plane(Vec(0, 0, 0), Vec(0, 1, 0), Vec(-1, 0, 0))
    (mid,) = Plane.tween(p0, p1, 1)
    assert mid.z_axis.equals(Vec(0, 0, 1))
    assert mid.x_axis.equals(Vec(0.707106781, 0.707106781, 0))


def test_tween_identical_frames():
    p0 = Plane.world_xy()
    same = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    mids = Plane.tween(p0, same, 2)
    assert len(mids) == 2
    assert all(m.z_axis.equals(Vec(0, 0, 1)) for m in mids)


def test_tween_antipodal_normals_raise():
    p0 = Plane.world_xy()
    flipped = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, -1, 0))
    assert (p0.z_axis @ flipped.z_axis) == pytest.approx(-1.0)
    with pytest.raises(ValueError, match="180"):
        Plane.tween(p0, flipped, 1)


def test_tween_180_apart_with_perpendicular_normals_raise():
    """Relative angle 180° with dot(normals) == 0: still undefined.

    Frame below is world_xy rotated 180° about (1, 0, 1)/√2
    (R = 2·a·aᵀ − I maps z -> x).
    """
    p0 = Plane.world_xy()
    other = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, -1, 0))
    assert other.z_axis.equals(Vec(1, 0, 0))
    assert (p0.z_axis @ other.z_axis) == pytest.approx(0.0, abs=1e-9)
    with pytest.raises(ValueError, match="180"):
        Plane.tween(p0, other, 1)


def test_tween_180_twist_about_normal_raises():
    """Opposite in-plane orientation is a 180° rotation — no shortest arc."""
    p0 = Plane.world_xy()
    twisted = Plane(Vec(0, 0, 0), Vec(-1, 0, 0), Vec(0, -1, 0))
    assert (p0.z_axis @ twisted.z_axis) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="180"):
        Plane.tween(p0, twisted, 3)


def test_tween_num_must_be_positive():
    p0 = Plane.world_xy()
    with pytest.raises(ValueError, match="positive integer"):
        Plane.tween(p0, p0, 0)
    with pytest.raises(ValueError, match="positive integer"):
        Plane.tween(p0, p0, -2)


def test_from_3_pts_raises_on_collinear():
    with pytest.raises(ValueError, match="collinear"):
        Plane.from_3_pts(Vec(0, 0, 0), Vec(1, 0, 0), Vec(3, 0, 0))


def test_from_tangent_basic():
    p = Plane.from_tangent(Vec(0, 0, 0), Vec(1, 0, 0))
    # x_axis = tangent direction
    assert p.x_axis.equals(Vec(1, 0, 0))
    # y_axis should be orthogonal to x
    assert p.x_axis.dot(p.y_axis) == pytest.approx(0.0, abs=1e-6)


def test_from_tangent_vertical():
    # tangent straight up — fallback to +Y
    p = Plane.from_tangent(Vec(0, 0, 0), Vec(0, 0, 1))
    assert p.x_axis.equals(Vec(0, 0, 1))
    assert p.x_axis.dot(p.y_axis) == pytest.approx(0.0, abs=1e-6)


def test_transform_point_roundtrip():
    p = Plane(Vec(1, 2, 3), Vec(1, 0, 0), Vec(0, 1, 0))
    local = Vec(1, 1, 0)
    world = p.transform_point(local)
    back = p.to_local(world)
    assert back.equals(local)


def test_transform_vector_no_translation():
    p = Plane(Vec(100, 100, 100), Vec(1, 0, 0), Vec(0, 1, 0))
    v = p.transform_vector(Vec(1, 0, 0))
    assert v.equals(Vec(1, 0, 0))


def test_closest_point_on_plane():
    p = Plane.world_xy()
    pt = Vec(3, 4, 7)
    closest = p.closest_point(pt)
    assert closest.equals(Vec(3, 4, 0))


def test_to_local():
    p = Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    world_pt = Vec(2, 3, 0)
    local = p.to_local(world_pt)
    # relative to origin (1,0,0): dx=1, dy=3, dz=0
    assert local.equals(Vec(1, 3, 0))


def test_repr():
    p = Plane.world_xy()
    assert "Plane(" in repr(p)


def test_flip_x_negates_x_and_z():
    p = Plane.world_xy()
    f = p.flip_x()
    assert f.origin.equals(Vec(0, 0, 0))
    assert f.x_axis.equals(Vec(-1, 0, 0))
    assert f.y_axis.equals(Vec(0, 1, 0))
    assert f.z_axis.equals(Vec(0, 0, -1))


def test_flip_y_negates_y_and_z():
    p = Plane.world_xy()
    f = p.flip_y()
    assert f.origin.equals(Vec(0, 0, 0))
    assert f.x_axis.equals(Vec(1, 0, 0))
    assert f.y_axis.equals(Vec(0, -1, 0))
    assert f.z_axis.equals(Vec(0, 0, -1))


def test_flip_z_negates_z_only():
    p = Plane.world_xy()
    f = p.flip_z()
    assert f.origin.equals(Vec(0, 0, 0))
    assert f.x_axis.equals(Vec(1, 0, 0))
    assert f.y_axis.equals(Vec(0, -1, 0))
    assert f.z_axis.equals(Vec(0, 0, -1))


def test_flip_z_on_clip_plane_swaps_keep_side():
    """Verify the normal is reversed via flip_z (same as flip_y)."""
    clip = Plane.from_origin_and_normal(Vec(2, 0, 0), Vec(-1, 0, 0))
    flipped = clip.flip_z()
    # flipped normal = +X → keep side is now x < 2 (negative sd along z)
    assert flipped.z_axis.equals(Vec(1, 0, 0))
    assert flipped.origin.equals(Vec(2, 0, 0))
