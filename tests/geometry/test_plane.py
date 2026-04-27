"""Tests for ifckit.geometry.Plane"""
import math
import pytest
from ifckit.geometry import Vec, Plane


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
